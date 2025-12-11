"""
Meeting Transcription Service
Flask application that handles meeting bot management and transcription processing.
"""

import os
import time
import json
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, request, jsonify, g, render_template, redirect, url_for, send_from_directory
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import API and pipeline modules
from src.api import recall
from src.api.storage import MeetingStorage
from src.api.auth import (
    init_auth,
    require_auth,
    verify_webhook,
    get_current_user
)
from src.pipeline import (
    combine_transcript_words,
    create_educational_chunks,
    summarize_educational_content,
    create_study_guide,
    markdown_to_pdf
)
from src.api.timezone_utils import format_datetime_for_user, utc_now

app = Flask(__name__, static_folder='static')

# Configure for large file uploads (50MB limit)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Initialize authentication
init_auth(app)

# Add Jinja filter for timezone formatting
@app.template_filter('format_user_time')
def format_user_time_filter(dt_str: str, user_timezone: str = "America/New_York") -> str:
    """
    Jinja filter to format datetime strings for user display.

    Args:
        dt_str: ISO format datetime string (assumed UTC)
        user_timezone: User's timezone (defaults to EST)

    Returns:
        Formatted datetime string in user's timezone
    """
    if not dt_str:
        return 'N/A'

    try:
        # Parse ISO datetime string
        if 'T' in dt_str:
            dt = datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(dt_str)

        # Format for user
        return format_datetime_for_user(dt, user_timezone, fmt="%Y-%m-%d %I:%M %p %Z")
    except Exception:
        # Fallback to original string if parsing fails
        return dt_str[:19].replace('T', ' ') if dt_str else 'N/A'

# =============================================================================
# SECURITY CONFIGURATION
# =============================================================================

# Allowed meeting URL domains (prevent SSRF and abuse)
ALLOWED_MEETING_DOMAINS = [
    'zoom.us',
    'zoomgov.com',
    'meet.google.com',
    'teams.microsoft.com',
    'teams.live.com',
    'webex.com',
    'gotomeeting.com',
    'whereby.com',
    'around.co',
]

def validate_meeting_url(url: str) -> tuple[bool, str]:
    """
    Validate that a meeting URL is from an allowed domain.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not url:
        return False, "Meeting URL is required"
    
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ('http', 'https'):
            return False, "Meeting URL must use http or https"
        
        domain = parsed.netloc.lower()
        
        # Remove port if present
        if ':' in domain:
            domain = domain.split(':')[0]
        
        # Check against allowed domains (including subdomains)
        is_allowed = any(
            domain == allowed or domain.endswith('.' + allowed)
            for allowed in ALLOWED_MEETING_DOMAINS
        )
        
        if not is_allowed:
            return False, f"Meeting URL domain not supported. Allowed: {', '.join(ALLOWED_MEETING_DOMAINS)}"
        
        return True, ""
        
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

# Configuration
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
OUTPUT_BUCKET = os.getenv("OUTPUT_BUCKET", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "outputs")

# Feature Flags
FEATURES_BOT_JOINING = os.getenv("FEATURES_BOT_JOINING", "true").lower() == "true"

# Firebase configuration (for frontend)
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY", ""),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN", f"{os.getenv('FIREBASE_PROJECT_ID', os.getenv('GOOGLE_CLOUD_PROJECT', ''))}.firebaseapp.com"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT", ""))
}

# Initialize storage (GCS if bucket configured, else local)
storage = MeetingStorage(bucket_name=OUTPUT_BUCKET, local_dir=OUTPUT_DIR)


def join_meeting_for_scheduler(meeting_url: str, bot_name: str, user: str) -> str:
    """
    Helper function for scheduler to join meetings.

    Returns:
        meeting_id if successful, None otherwise
    """
    try:
        # Determine webhook URL
        webhook_url = WEBHOOK_URL
        if not webhook_url:
            # Use SERVICE_URL from environment (set by deployment)
            service_url = os.getenv("SERVICE_URL", "")
            if service_url:
                webhook_url = f"{service_url.rstrip('/')}/webhook/recall"
            else:
                print("⚠️ No WEBHOOK_URL or SERVICE_URL configured for scheduled meeting")
                return None

        # Create bot
        bot_data = recall.create_bot(meeting_url, webhook_url, bot_name)

        if not bot_data:
            return None

        # Store meeting in persistent storage
        meeting_id = bot_data['id']
        storage.create_meeting(
            meeting_id=meeting_id,
            user=user,
            meeting_url=meeting_url,
            bot_name=bot_name
        )

        return meeting_id
    except Exception as e:
        print(f"Error joining meeting for scheduler: {e}")
        return None


# Scheduler is handled by Cloud Scheduler (GCP cron job)
# No background thread needed - Cloud Run scales to zero between requests


@app.before_request
def set_current_user():
    """Set current user in request context using the auth module."""
    g.user = get_current_user()
    # Also set user_info if available (for routes that don't use @require_auth)
    if not hasattr(g, 'user_info'):
        from src.api.auth import authenticate_request
        user, _ = authenticate_request()
        g.user_info = user if user else None


def get_default_bot_name() -> str:
    """
    Get the default bot name based on the current user's name.

    Returns:
        str: Bot name using user's name, or fallback to default
    """
    # Check if we have user info with a name
    if hasattr(g, 'user_info') and g.user_info and g.user_info.name:
        return f"{g.user_info.name}'s Bot"

    # Fallback to default
    return "Meeting Assistant Bot"


def get_user_timezone() -> str:
    """
    Get the current user's timezone preference.

    Returns:
        str: User's timezone, defaults to America/New_York (EST)
    """
    # Check if we have user info with a timezone
    if hasattr(g, 'user_info') and g.user_info and hasattr(g.user_info, 'timezone'):
        return g.user_info.timezone

    # Fallback to EST
    return "America/New_York"


@app.route('/', methods=['GET'])
def index():
    """Landing page with sign-in."""
    return send_from_directory('static', 'index.html')


@app.route('/dashboard', methods=['GET'])
def dashboard():
    """Redirect to main SPA."""
    return redirect('/')


@app.route('/api/config', methods=['GET'])
def get_firebase_config():
    """
    Return Firebase/Identity Platform configuration and feature flags for the frontend.
    This endpoint is public so the frontend can initialize authentication.
    """
    return jsonify({
        **FIREBASE_CONFIG,
        "features": {
            "botJoining": FEATURES_BOT_JOINING
        }
    })


@app.route('/api', methods=['GET'])
def api_info():
    """API info endpoint (JSON)."""
    return jsonify({
        "service": "Meeting Transcription API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "GET /health",
            "create_meeting": "POST /api/meetings",
            "list_meetings": "GET /api/meetings",
            "get_meeting": "GET /api/meetings/{id}",
            "delete_meeting": "DELETE /api/meetings/{id}",
            "get_outputs": "GET /api/meetings/{id}/outputs",
            "webhook": "POST /webhook/recall"
        },
        "authentication": {
            "methods": ["API Key", "Bearer Token (Firebase)", "IAP (GCP)"],
            "api_key_header": "X-API-Key: <your-api-key>",
            "bearer_header": "Authorization: Bearer <token>"
        },
        "docs": "https://github.com/lll-solutions/meeting-transcription",
        "usage": {
            "example": "POST /api/meetings with JSON body: {\"meeting_url\": \"https://zoom.us/j/123456789\"}",
            "auth_example": "curl -H 'X-API-Key: your-key' https://api.example.com/api/meetings"
        }
    })


# =============================================================================
# AUTHENTICATION ROUTES
# =============================================================================

@app.route('/api/auth/login', methods=['POST'])
def login():
    """
    Login with email and password.
    Returns a JWT token.
    """
    try:
        data = request.json
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({"error": "Email and password required"}), 400

        from src.api.auth_db import get_auth_service
        service = get_auth_service()

        user = service.authenticate_user(data['email'], data['password'])
        if not user:
            return jsonify({"error": "Invalid credentials"}), 401

        token = service.create_token(user)

        return jsonify({
            "token": token,
            "user": user.to_dict()
        })
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Login failed: {str(e)}"}), 500


@app.route('/api/auth/setup', methods=['POST'])
def setup_admin():
    """
    Create the initial admin user.
    Requires SETUP_API_KEY in X-Setup-Key header.
    Only works if no users exist yet.
    """
    # Require setup API key for security
    SETUP_API_KEY = os.getenv("SETUP_API_KEY", "").strip()
    provided_key = request.headers.get("X-Setup-Key", "").strip()

    if not SETUP_API_KEY:
        return jsonify({"error": "Setup endpoint is not configured (missing SETUP_API_KEY)"}), 500

    if not provided_key or provided_key != SETUP_API_KEY:
        return jsonify({"error": "Unauthorized - invalid or missing setup key"}), 401

    data = request.json
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"error": "Email and password required"}), 400

    from src.api.auth_db import get_auth_service
    service = get_auth_service()

    # Check if any users exist (security check)
    if service.db:
        users = list(service.db.collection("users").limit(1).stream())
        if len(users) > 0:
            return jsonify({"error": "Setup already completed"}), 403

    user, error = service.create_user(
        email=data['email'],
        password=data['password'],
        name=data.get('name', 'Admin')
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "Admin user created successfully",
        "user": user.to_dict()
    })


# =============================================================================
# UI ROUTES (HTMX)
# =============================================================================

@app.route('/ui/meetings-list', methods=['GET'])
def ui_meetings_list():
    """HTMX partial: Get meeting list HTML."""
    meetings = storage.list_meetings(user=g.user if g.user != 'anonymous' else None)
    user_timezone = get_user_timezone()
    return render_template('partials/meeting_list.html', meetings=meetings, user_timezone=user_timezone)


@app.route('/ui/meetings', methods=['POST'])
def ui_create_meeting():
    """HTMX: Create a meeting and return updated list."""
    # Check if bot joining feature is enabled
    if not FEATURES_BOT_JOINING:
        return '<div class="text-accent-coral p-4">Bot joining feature is disabled. Please use transcript upload instead.</div>', 403

    meeting_url = request.form.get('meeting_url')
    bot_name = request.form.get('bot_name') or get_default_bot_name()

    # Validate meeting URL
    is_valid, error = validate_meeting_url(meeting_url)
    if not is_valid:
        return f'<div class="text-accent-coral p-4">{error}</div>', 400
    
    # Determine webhook URL
    webhook_url = WEBHOOK_URL
    if not webhook_url:
        webhook_url = f"{request.url_root.rstrip('/')}/webhook/recall"
    
    # Create bot
    bot_data = recall.create_bot(meeting_url, webhook_url, bot_name)
    
    if not bot_data:
        return '<div class="text-accent-coral p-4">Failed to create bot</div>', 500
    
    # Store meeting
    meeting_id = bot_data['id']
    storage.create_meeting(
        meeting_id=meeting_id,
        user=g.user,
        meeting_url=meeting_url,
        bot_name=bot_name
    )
    
    # Return updated meeting list
    meetings = storage.list_meetings(user=g.user if g.user != 'anonymous' else None)
    user_timezone = get_user_timezone()
    return render_template('partials/meeting_list.html', meetings=meetings, user_timezone=user_timezone)


@app.route('/ui/meetings/<meeting_id>', methods=['GET'])
def ui_meeting_detail(meeting_id):
    """UI: Meeting detail page."""
    meeting = storage.get_meeting(meeting_id)

    if not meeting:
        # Try from Recall API
        bot_status = recall.get_bot_status(meeting_id)
        if bot_status:
            meeting = bot_status
        else:
            return redirect(url_for('index'))

    user_timezone = get_user_timezone()
    return render_template('meeting_detail.html', meeting=meeting, user=g.user, user_timezone=user_timezone)


@app.route('/ui/meetings/<meeting_id>', methods=['DELETE'])
def ui_delete_meeting(meeting_id):
    """HTMX: Remove bot from meeting and return updated list."""
    success = recall.leave_meeting(meeting_id)
    if success:
        storage.update_meeting(meeting_id, {"status": "leaving"})
    
    # Return updated meeting list
    meetings = storage.list_meetings(user=g.user if g.user != 'anonymous' else None)
    user_timezone = get_user_timezone()
    return render_template('partials/meeting_list.html', meetings=meetings, user_timezone=user_timezone)


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint (no auth required for load balancer)."""
    return jsonify({
        "status": "ok",
        "timestamp": utc_now().isoformat(),
        "storage": "firestore" if storage.db else "local",
        "files": "gcs" if storage.bucket else "local"
    })


# =============================================================================
# USER PREFERENCES ROUTES
# =============================================================================

@app.route('/api/users/me', methods=['GET'])
@require_auth
def get_current_user_info():
    """Get current user information including preferences."""
    from src.api.auth_db import get_auth_service
    service = get_auth_service()

    user = service.get_user(g.user)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify(user.to_dict())


@app.route('/api/users/me', methods=['PATCH'])
@require_auth
def update_current_user():
    """Update current user preferences."""
    from src.api.auth_db import get_auth_service
    from src.api.timezone_utils import is_valid_timezone

    service = get_auth_service()
    data = request.json

    if not data:
        return jsonify({"error": "No data provided"}), 400

    # Validate timezone if provided
    if 'timezone' in data and not is_valid_timezone(data['timezone']):
        return jsonify({"error": "Invalid timezone"}), 400

    user, error = service.update_user(g.user, data)
    if error:
        return jsonify({"error": error}), 400

    return jsonify(user.to_dict())


# =============================================================================
# SCHEDULED MEETINGS ROUTES
# =============================================================================

@app.route('/api/scheduled-meetings', methods=['POST'])
@require_auth
def create_scheduled_meeting():
    """
    Schedule a bot to join a meeting at a specific time.

    Request body:
    {
        "meeting_url": "https://zoom.us/j/123456789",
        "scheduled_time": "2024-12-10T15:30:00",  # In user's timezone
        "bot_name": "Meeting Assistant" (optional)
    }
    """
    from src.api.scheduled_meetings import ScheduledMeeting, get_scheduled_meeting_storage
    from src.api.timezone_utils import parse_user_datetime
    from src.api.auth_db import get_auth_service

    # Check if bot joining feature is enabled
    if not FEATURES_BOT_JOINING:
        return jsonify({
            "error": "Bot joining feature is disabled",
            "feature": "bot_joining",
            "enabled": False
        }), 403

    data = request.json

    if not data or 'meeting_url' not in data or 'scheduled_time' not in data:
        return jsonify({"error": "meeting_url and scheduled_time are required"}), 400

    meeting_url = data['meeting_url']
    bot_name = data.get('bot_name') or get_default_bot_name()

    # Validate meeting URL
    is_valid, error = validate_meeting_url(meeting_url)
    if not is_valid:
        return jsonify({"error": error}), 400

    # Get user's timezone
    auth_service = get_auth_service()
    user = auth_service.get_user(g.user)
    if not user:
        return jsonify({"error": "User not found"}), 404

    user_timezone = user.timezone

    # Parse scheduled time (convert from user's timezone to UTC)
    scheduled_time_utc = parse_user_datetime(data['scheduled_time'], user_timezone)
    if not scheduled_time_utc:
        return jsonify({"error": "Invalid scheduled_time format. Use ISO format like '2024-12-10T15:30:00'"}), 400

    # Create scheduled meeting
    scheduled_meeting = ScheduledMeeting(
        meeting_url=meeting_url,
        scheduled_time=scheduled_time_utc,
        user=g.user,
        bot_name=bot_name,
        user_timezone=user_timezone
    )

    storage_service = get_scheduled_meeting_storage()
    created_meeting, error = storage_service.create(scheduled_meeting)

    if error:
        return jsonify({"error": error}), 500

    return jsonify(created_meeting.to_dict()), 201


@app.route('/api/scheduled-meetings', methods=['GET'])
@require_auth
def list_scheduled_meetings():
    """List scheduled meetings for the current user."""
    from src.api.scheduled_meetings import get_scheduled_meeting_storage

    storage_service = get_scheduled_meeting_storage()
    user = g.user if g.user != 'anonymous' else None

    status = request.args.get('status')
    meetings = storage_service.list(user=user, status=status)

    return jsonify([m.to_dict() for m in meetings])


@app.route('/api/scheduled-meetings/<meeting_id>', methods=['GET'])
@require_auth
def get_scheduled_meeting(meeting_id):
    """Get a scheduled meeting by ID."""
    from src.api.scheduled_meetings import get_scheduled_meeting_storage

    storage_service = get_scheduled_meeting_storage()
    meeting = storage_service.get(meeting_id)

    if not meeting:
        return jsonify({"error": "Scheduled meeting not found"}), 404

    # Check user owns this scheduled meeting
    if meeting.user != g.user and g.user != 'anonymous':
        return jsonify({"error": "Forbidden"}), 403

    return jsonify(meeting.to_dict())


@app.route('/api/scheduled-meetings/<meeting_id>', methods=['DELETE'])
@require_auth
def delete_scheduled_meeting(meeting_id):
    """Cancel a scheduled meeting."""
    from src.api.scheduled_meetings import get_scheduled_meeting_storage

    storage_service = get_scheduled_meeting_storage()
    meeting = storage_service.get(meeting_id)

    if not meeting:
        return jsonify({"error": "Scheduled meeting not found"}), 404

    # Check user owns this scheduled meeting
    if meeting.user != g.user and g.user != 'anonymous':
        return jsonify({"error": "Forbidden"}), 403

    success, error = storage_service.delete(meeting_id)

    if error:
        return jsonify({"error": error}), 500

    return jsonify({"success": True}), 200


@app.route('/api/scheduled-meetings/execute', methods=['POST'])
def execute_scheduled_meetings():
    """
    Execute pending scheduled meetings.

    This endpoint is called by Cloud Scheduler every 2 minutes.
    It checks for meetings that are ready to be joined and executes them.

    Authentication: Verifies request is from Cloud Scheduler via OIDC token.
    """
    from src.api.scheduled_meetings import get_scheduled_meeting_storage
    from src.api.timezone_utils import utc_now

    # Verify request is from Cloud Scheduler
    # Cloud Scheduler adds Authorization: Bearer <OIDC token> header
    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        return jsonify({"error": "Unauthorized - missing Bearer token"}), 401

    # In production, you should verify the OIDC token
    # For now, we'll accept any Bearer token (Cloud Scheduler will provide valid OIDC)
    # TODO: Add proper OIDC token verification if needed

    storage_service = get_scheduled_meeting_storage()
    now = utc_now()
    pending_meetings = storage_service.get_pending(before_time=now)

    if not pending_meetings:
        return jsonify({
            "message": "No pending meetings to execute",
            "checked_at": now.isoformat(),
            "executed": 0
        })

    print(f"⏰ Cloud Scheduler: Found {len(pending_meetings)} pending meeting(s) to execute")

    results = []
    for scheduled_meeting in pending_meetings:
        try:
            print(f"🤖 Executing scheduled meeting: {scheduled_meeting.id}")
            print(f"   URL: {scheduled_meeting.meeting_url}")
            print(f"   Scheduled for: {scheduled_meeting.scheduled_time}")
            print(f"   User: {scheduled_meeting.user}")

            # Join the meeting
            meeting_id = join_meeting_for_scheduler(
                scheduled_meeting.meeting_url,
                scheduled_meeting.bot_name,
                scheduled_meeting.user
            )

            if meeting_id:
                # Update as completed
                storage_service.update(scheduled_meeting.id, {
                    "status": "completed",
                    "actual_meeting_id": meeting_id
                })
                results.append({
                    "id": scheduled_meeting.id,
                    "status": "completed",
                    "meeting_id": meeting_id
                })
                print(f"✅ Successfully joined meeting: {meeting_id}")
            else:
                # Mark as failed
                storage_service.update(scheduled_meeting.id, {
                    "status": "failed",
                    "error": "Failed to create bot"
                })
                results.append({
                    "id": scheduled_meeting.id,
                    "status": "failed",
                    "error": "Failed to create bot"
                })
                print(f"❌ Failed to join scheduled meeting: {scheduled_meeting.id}")

        except Exception as e:
            error_msg = str(e)
            print(f"❌ Error executing scheduled meeting {scheduled_meeting.id}: {error_msg}")

            # Mark as failed
            try:
                storage_service.update(scheduled_meeting.id, {
                    "status": "failed",
                    "error": error_msg
                })
            except Exception as update_error:
                print(f"❌ Could not update meeting status: {update_error}")

            results.append({
                "id": scheduled_meeting.id,
                "status": "failed",
                "error": error_msg
            })

    return jsonify({
        "message": f"Executed {len(results)} scheduled meeting(s)",
        "checked_at": now.isoformat(),
        "executed": len(results),
        "results": results
    })


# =============================================================================
# MEETING ROUTES
# =============================================================================

@app.route('/api/meetings', methods=['POST'])
@require_auth
def create_meeting():
    """
    Create a bot to join a meeting.

    Request body:
    {
        "meeting_url": "https://zoom.us/j/123456789",
        "bot_name": "Meeting Assistant" (optional),
        "join_at": "now" or ISO timestamp (optional)
    }
    """
    # Check if bot joining feature is enabled
    if not FEATURES_BOT_JOINING:
        return jsonify({
            "error": "Bot joining feature is disabled. Please use transcript upload instead.",
            "feature": "bot_joining",
            "enabled": False
        }), 403

    data = request.json

    if not data or 'meeting_url' not in data:
        return jsonify({"error": "meeting_url is required"}), 400
    
    meeting_url = data['meeting_url']
    bot_name = data.get('bot_name') or get_default_bot_name()
    
    # Validate meeting URL
    is_valid, error = validate_meeting_url(meeting_url)
    if not is_valid:
        return jsonify({"error": error}), 400
    
    # Determine webhook URL
    webhook_url = WEBHOOK_URL
    if not webhook_url:
        # Try to construct from request
        webhook_url = f"{request.url_root.rstrip('/')}/webhook/recall"
    
    # Create bot
    bot_data = recall.create_bot(meeting_url, webhook_url, bot_name)
    
    if not bot_data:
        return jsonify({"error": "Failed to create bot"}), 500
    
    # Store meeting in persistent storage
    meeting_id = bot_data['id']
    meeting = storage.create_meeting(
        meeting_id=meeting_id,
        user=g.user,
        meeting_url=meeting_url,
        bot_name=bot_name
    )
    
    return jsonify(meeting), 201


@app.route('/api/meetings', methods=['GET'])
@require_auth
def list_meetings():
    """List meetings for the current user."""
    user = g.user if g.user != 'anonymous' else None
    meetings = storage.list_meetings(user=user)
    return jsonify(meetings)


@app.route('/api/meetings/<meeting_id>', methods=['GET'])
@require_auth
def get_meeting(meeting_id):
    """Get status of a specific meeting."""
    meeting = storage.get_meeting(meeting_id)
    
    if not meeting:
        # Try to get from Recall API as fallback
        bot_status = recall.get_bot_status(meeting_id)
        if bot_status:
            return jsonify(bot_status)
        return jsonify({"error": "Meeting not found"}), 404
    
    return jsonify(meeting)


@app.route('/api/meetings/<meeting_id>', methods=['DELETE'])
@require_auth
def remove_meeting(meeting_id):
    """Remove bot from meeting."""
    success = recall.leave_meeting(meeting_id)
    if success:
        storage.update_meeting(meeting_id, {"status": "leaving"})
        return jsonify({"status": "leaving"})
    return jsonify({"error": "Failed to remove bot"}), 500


@app.route('/webhook/recall', methods=['POST'])
@verify_webhook
def handle_webhook():
    """
    Handle webhook events from Recall.ai.

    Key events:
    - bot.joining_call: Bot joining/joined the meeting
    - bot.done / bot.call_ended: Meeting ended
    - recording.done: Recording completed
    - transcript.done: Transcript ready
    """
    try:
        data = request.json
        event = data.get('event')
        
        print(f"\n📨 Received event: {event}")
        
        # Handle bot joining call
        if event == 'bot.joining_call':
            bot_id = data.get('data', {}).get('bot', {}).get('id') or data.get('bot_id')
            print(f"👋 Bot joining the call! ID: {bot_id}")
            if bot_id:
                storage.update_meeting(bot_id, {"status": "in_meeting"})

        # Handle bot done / meeting ended
        elif event in ['bot.done', 'bot.call_ended']:
            bot_id = data.get('data', {}).get('bot', {}).get('id') or data.get('bot_id')
            recording_id = (
                data.get('data', {}).get('recording', {}).get('id') or
                data.get('data', {}).get('recording_id')
            )
            
            print(f"👋 Bot left the call. Recording ID: {recording_id}")
            
            # Update meeting in storage
            if bot_id:
                storage.update_meeting(bot_id, {
                    "status": "ended",
                    "recording_id": recording_id
                })
            
            # Request async transcript
            if recording_id:
                print(f"📝 Requesting async transcript for recording {recording_id}")
                time.sleep(5)  # Wait for recording to finalize
                transcript_result = recall.create_async_transcript(recording_id)
                if transcript_result and bot_id:
                    storage.update_meeting(bot_id, {
                        "transcript_id": transcript_result['id'],
                        "status": "transcribing"
                    })
        
        # Handle recording completion
        elif event == 'recording.done':
            recording_id = data.get('data', {}).get('recording', {}).get('id')
            print(f"🎬 Recording completed! ID: {recording_id}")
            
            if recording_id:
                print(f"📝 Requesting async transcript for recording {recording_id}")
                time.sleep(5)
                recall.create_async_transcript(recording_id)
        
        # Handle transcript completion - TRIGGER THE PIPELINE
        elif event == 'transcript.done':
            transcript_id = data.get('data', {}).get('transcript', {}).get('id')
            recording_id = data.get('data', {}).get('recording', {}).get('id')
            
            print(f"✅ Transcript ready! ID: {transcript_id}")
            
            if transcript_id:
                # Process the transcript through the pipeline
                process_transcript(transcript_id, recording_id)
        
        # Handle transcript failure
        elif event == 'transcript.failed':
            print(f"❌ Transcript failed")
            print(data)
        
        else:
            print(f"ℹ️ Unhandled event: {event}")
        
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        print(f"❌ Error handling webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


def process_transcript(transcript_id: str, recording_id: str = None):
    """
    Process transcript through the summarization pipeline.
    
    Steps:
    1. Download transcript
    2. Combine words into sentences
    3. Create educational chunks
    4. Summarize with LLM
    5. Generate study guide (Markdown)
    6. Convert to PDF
    7. Upload to storage
    """
    # Find the meeting ID associated with this transcript
    meeting_id = None
    meetings_list = storage.list_meetings()
    for m in meetings_list:
        if m.get('transcript_id') == transcript_id:
            meeting_id = m['id']
            break
    
    if not meeting_id:
        meeting_id = recording_id or transcript_id
    
    try:
        print(f"\n🔄 Starting pipeline for transcript {transcript_id}")
        
        # Update status
        storage.update_meeting(meeting_id, {"status": "processing"})
        
        # Create temporary local directory for processing
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            
            # Step 1: Download transcript
            print("📥 Step 1: Downloading transcript...")
            transcript_file = os.path.join(temp_dir, "transcript_raw.json")
            result = recall.download_transcript(transcript_id, transcript_file)
            if not result:
                print("❌ Failed to download transcript")
                storage.update_meeting(meeting_id, {
                    "status": "failed",
                    "error": "Failed to download transcript"
                })
                return
            
            # Step 2: Combine words
            print("📝 Step 2: Combining words into sentences...")
            combined_file = os.path.join(temp_dir, "transcript_combined.json")
            combine_transcript_words.combine_transcript_words(transcript_file, combined_file)
            
            # Step 3: Create chunks
            print("📦 Step 3: Creating educational chunks...")
            chunks_file = os.path.join(temp_dir, "transcript_chunks.json")
            create_educational_chunks.create_educational_content_chunks(combined_file, chunks_file, chunk_minutes=10)
            
            # Step 4: LLM Summarization
            print("🤖 Step 4: Generating AI summary...")
            summary_file = os.path.join(temp_dir, "summary.json")
            summarize_educational_content.summarize_educational_content(
                chunks_file, 
                summary_file,
                provider=os.getenv('LLM_PROVIDER', 'vertex_ai')
            )
            
            # Step 5: Create study guide
            print("📚 Step 5: Creating study guide...")
            study_guide_file = os.path.join(temp_dir, "study_guide.md")
            create_study_guide.create_markdown_study_guide(summary_file, study_guide_file)
            
            # Step 6: Convert to PDF
            print("📄 Step 6: Generating PDF...")
            pdf_file = os.path.join(temp_dir, "study_guide.pdf")
            markdown_to_pdf.convert_markdown_to_pdf(study_guide_file, pdf_file)
            
            # Step 7: Upload all files to storage
            print("☁️ Step 7: Uploading to storage...")
            outputs = {}
            
            for name, local_path in [
                ("transcript", transcript_file),
                ("summary", summary_file),
                ("study_guide_md", study_guide_file),
                ("study_guide_pdf", pdf_file)
            ]:
                filename = os.path.basename(local_path)
                stored_path = storage.save_file_from_path(meeting_id, filename, local_path)
                outputs[name] = stored_path
                print(f"   ✅ Uploaded: {filename}")
            
            # Update meeting with completed status and output paths
            storage.update_meeting(meeting_id, {
                "status": "completed",
                "outputs": outputs,
                "completed_at": utc_now().isoformat()
            })
            
            print(f"\n✅ Pipeline complete!")
            print(f"   Meeting ID: {meeting_id}")
            for name, path in outputs.items():
                print(f"   - {name}: {path}")
        
    except Exception as e:
        print(f"❌ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        
        # Update meeting with error
        storage.update_meeting(meeting_id, {
            "status": "failed",
            "error": str(e)
        })


@app.route('/api/meetings/<meeting_id>/outputs', methods=['GET'])
@require_auth
def get_meeting_outputs(meeting_id):
    """Get the output files for a completed meeting."""
    meeting = storage.get_meeting(meeting_id)
    
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404
    
    if meeting['status'] != 'completed':
        return jsonify({
            "status": meeting['status'],
            "message": "Meeting not yet completed or still processing"
        })
    
    # Get download URLs for outputs
    outputs = {}
    for name, path in meeting.get('outputs', {}).items():
        filename = os.path.basename(path)
        url = storage.get_download_url(meeting_id, filename)
        outputs[name] = url
    
    return jsonify(outputs)


@app.route('/api/meetings/<meeting_id>/outputs/<filename>', methods=['GET'])
@require_auth
def download_output(meeting_id, filename):
    """
    Download a specific output file.

    For GCS storage, this generates a signed URL and redirects to it.
    For local storage, this serves the file directly.
    """
    # Check if file exists
    meeting = storage.get_meeting(meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    # Get signed URL (for GCS) or local path
    download_url = storage.get_download_url(meeting_id, filename)

    if not download_url:
        return jsonify({"error": "File not found"}), 404

    # If using GCS (URL starts with https://), redirect to the signed URL
    if download_url.startswith('https://'):
        return redirect(download_url)

    # For local storage, serve the file directly
    content = storage.get_file(meeting_id, filename)
    if not content:
        return jsonify({"error": "File not found"}), 404

    # Determine content type
    content_type = "application/octet-stream"
    if filename.endswith(".json"):
        content_type = "application/json"
    elif filename.endswith(".md"):
        content_type = "text/markdown"
    elif filename.endswith(".pdf"):
        content_type = "application/pdf"
    elif filename.endswith(".txt"):
        content_type = "text/plain"

    from flask import Response
    return Response(content, mimetype=content_type)


@app.route('/api/transcripts/upload', methods=['POST'])
@require_auth
def upload_transcript():
    """
    Upload a transcript JSON file and process it through the LLM pipeline.

    Processing is done asynchronously via Cloud Tasks - the endpoint returns immediately
    with a meeting_id that can be polled for status.

    Request body:
    {
        "transcript": [...],  // The transcript JSON data
        "title": "Meeting Title"  // Optional title
    }
    """
    import uuid
    import json as json_lib
    from google.cloud import tasks_v2

    data = request.json

    if not data or 'transcript' not in data:
        return jsonify({"error": "transcript data is required"}), 400

    transcript_data = data['transcript']
    title = data.get('title', f'Uploaded Transcript {utc_now().strftime("%Y-%m-%d %H:%M")}')

    # Validate transcript format
    if not isinstance(transcript_data, list):
        return jsonify({"error": "Invalid transcript format - expected array"}), 400

    if len(transcript_data) == 0:
        return jsonify({"error": "Transcript is empty"}), 400

    # Generate a unique meeting ID for this upload
    meeting_id = f"upload-{uuid.uuid4().hex[:8]}"

    # Create meeting record with initial status
    meeting = storage.create_meeting(
        meeting_id=meeting_id,
        user=g.user,
        meeting_url=None,
        bot_name=title
    )
    storage.update_meeting(meeting_id, {"status": "queued"})

    # Store transcript temporarily in GCS (Cloud Tasks has 100KB payload limit)
    try:
        bucket_name = os.getenv("OUTPUT_BUCKET")
        blob_name = f"temp/{meeting_id}/transcript_upload.json"

        from google.cloud import storage as gcs_storage
        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(json_lib.dumps(transcript_data), content_type='application/json')

        print(f"✅ Transcript stored temporarily: gs://{bucket_name}/{blob_name}")
    except Exception as e:
        print(f"❌ Failed to store transcript: {e}")
        storage.update_meeting(meeting_id, {
            "status": "failed",
            "error": f"Failed to store transcript: {str(e)}"
        })
        return jsonify({"error": f"Failed to store transcript: {str(e)}"}), 500

    # Create Cloud Task for background processing
    try:
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GCP_REGION", "us-central1")
        queue = "transcript-processing"

        # Get the service URL
        service_url = os.getenv("SERVICE_URL") or request.host_url.rstrip('/')
        url = f"{service_url}/api/transcripts/process/{meeting_id}"

        # Create Cloud Tasks client
        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project_id, location, queue)

        # Prepare task payload (only metadata, not transcript)
        payload = {
            "meeting_id": meeting_id,
            "title": title
        }

        # Create the task
        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json_lib.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": f"{os.getenv('PROJECT_NUMBER', '')}-compute@developer.gserviceaccount.com"
                }
            }
        }

        # Enqueue the task
        response = client.create_task(request={"parent": parent, "task": task})
        print(f"✅ Cloud Task created: {response.name}")

    except Exception as e:
        print(f"❌ Failed to create Cloud Task: {e}")
        import traceback
        traceback.print_exc()
        storage.update_meeting(meeting_id, {
            "status": "failed",
            "error": f"Failed to queue processing: {str(e)}"
        })
        return jsonify({"error": f"Failed to queue processing: {str(e)}"}), 500

    # Return immediately with meeting_id for polling
    return jsonify({
        "status": "queued",
        "meeting_id": meeting_id,
        "title": title,
        "message": "Processing queued. Poll /api/meetings/{meeting_id} for status."
    }), 202


@app.route('/api/transcripts/process/<meeting_id>', methods=['POST'])
def process_transcript_task(meeting_id: str):
    """
    Process endpoint called by Cloud Tasks.
    Processes the uploaded transcript that was queued.

    This endpoint is called by Cloud Tasks, not directly by users.
    """
    import json as json_lib

    print(f"📥 Cloud Task received for {meeting_id}", flush=True)

    # Get the meeting to retrieve metadata
    meeting = storage.get_meeting(meeting_id)
    if not meeting:
        print(f"❌ Meeting {meeting_id} not found", flush=True)
        return jsonify({"error": "Meeting not found"}), 404

    # Get metadata from request body
    data = request.json or {}
    title = data.get('title', meeting.get('bot_name', 'Uploaded Transcript'))

    # Fetch transcript from GCS temp storage
    try:
        bucket_name = os.getenv("OUTPUT_BUCKET")
        blob_name = f"temp/{meeting_id}/transcript_upload.json"

        from google.cloud import storage as gcs_storage
        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        transcript_json = blob.download_as_text()
        transcript_data = json_lib.loads(transcript_json)

        print(f"✅ Transcript fetched from GCS: {len(transcript_data)} segments")
    except Exception as e:
        print(f"❌ Failed to fetch transcript from GCS: {e}")
        storage.update_meeting(meeting_id, {
            "status": "failed",
            "error": f"Failed to fetch transcript: {str(e)}"
        })
        return jsonify({"error": f"Failed to fetch transcript: {str(e)}"}), 500

    print(f"🔄 Starting processing for {meeting_id}", flush=True)

    # Process the transcript (this will run until completion)
    try:
        process_uploaded_transcript(meeting_id, transcript_data, title)
        print(f"✅ Processing completed for {meeting_id}", flush=True)

        # Clean up temp file
        try:
            blob.delete()
            print(f"🗑️ Temp transcript deleted")
        except:
            pass

        return jsonify({"status": "completed", "meeting_id": meeting_id}), 200
    except Exception as e:
        print(f"❌ Processing failed for {meeting_id}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        storage.update_meeting(meeting_id, {
            "status": "failed",
            "error": str(e)
        })
        return jsonify({"status": "failed", "error": str(e)}), 500


def process_uploaded_transcript(meeting_id: str, transcript_data: list, title: str = None) -> dict:
    """
    Process an uploaded transcript through the summarization pipeline.
    
    Args:
        meeting_id: Unique ID for this upload
        transcript_data: The transcript JSON data (list of segments)
        title: Optional title for the transcript
    
    Returns:
        dict: Processing results including output paths
    """
    import tempfile
    
    print(f"\n🔄 Starting pipeline for uploaded transcript {meeting_id}")
    storage.update_meeting(meeting_id, {"status": "processing"})
    
    with tempfile.TemporaryDirectory() as temp_dir:
        
        # Step 1: Save the uploaded transcript
        print("📥 Step 1: Saving uploaded transcript...")
        transcript_file = os.path.join(temp_dir, "transcript_raw.json")
        with open(transcript_file, 'w') as f:
            json.dump(transcript_data, f, indent=2)
        
        # Step 2: Combine words
        print("📝 Step 2: Combining words into sentences...")
        combined_file = os.path.join(temp_dir, "transcript_combined.json")
        combine_transcript_words.combine_transcript_words(transcript_file, combined_file)
        
        # Step 3: Create chunks
        print("📦 Step 3: Creating educational chunks...")
        chunks_file = os.path.join(temp_dir, "transcript_chunks.json")
        create_educational_chunks.create_educational_content_chunks(combined_file, chunks_file, chunk_minutes=10)
        
        # Step 4: LLM Summarization
        print("🤖 Step 4: Generating AI summary...")
        summary_file = os.path.join(temp_dir, "summary.json")
        summarize_educational_content.summarize_educational_content(
            chunks_file, 
            summary_file,
            provider=os.getenv('LLM_PROVIDER', 'vertex_ai')
        )
        
        # Step 5: Create study guide
        print("📚 Step 5: Creating study guide...")
        study_guide_file = os.path.join(temp_dir, "study_guide.md")
        create_study_guide.create_markdown_study_guide(summary_file, study_guide_file)
        
        # Step 6: Convert to PDF
        print("📄 Step 6: Generating PDF...")
        pdf_file = os.path.join(temp_dir, "study_guide.pdf")
        try:
            markdown_to_pdf.convert_markdown_to_pdf(study_guide_file, pdf_file)
        except Exception as e:
            print(f"⚠️ PDF generation failed (non-fatal): {e}")
            pdf_file = None
        
        # Step 7: Upload all files to storage
        print("☁️ Step 7: Uploading to storage...")
        outputs = {}
        
        files_to_upload = [
            ("transcript_raw", transcript_file),
            ("transcript_combined", combined_file),
            ("transcript_chunks", chunks_file),
            ("summary", summary_file),
            ("study_guide_md", study_guide_file),
        ]
        
        if pdf_file and os.path.exists(pdf_file):
            files_to_upload.append(("study_guide_pdf", pdf_file))
        
        for name, local_path in files_to_upload:
            if os.path.exists(local_path):
                filename = os.path.basename(local_path)
                stored_path = storage.save_file_from_path(meeting_id, filename, local_path)
                outputs[name] = stored_path
                print(f"   ✅ Uploaded: {filename}")
        
        # Update meeting with completed status
        storage.update_meeting(meeting_id, {
            "status": "completed",
            "outputs": outputs,
            "completed_at": utc_now().isoformat(),
            "title": title
        })
        
        print(f"\n✅ Pipeline complete!")
        print(f"   Meeting ID: {meeting_id}")
        for name, path in outputs.items():
            print(f"   - {name}: {path}")
        
        return {"outputs": outputs}


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "false").lower() == "true"
    
    print(f"🚀 Starting Meeting Transcription Service on port {port}")
    print(f"📡 Webhook URL: {WEBHOOK_URL or 'auto-detect'}")
    
    app.run(host='0.0.0.0', port=port, debug=debug)

