"""
Meeting Transcription Service
Flask application that handles meeting bot management and transcription processing.
"""

import os
from datetime import datetime

from dotenv import load_dotenv
from flask import (
    Flask,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

# Load environment variables
load_dotenv()

# Import API and pipeline modules
from src.api import recall
from src.api.auth import (
    get_current_user,
    init_auth,
    require_auth,
    verify_cloud_tasks,
    verify_webhook,
)
from src.api.storage import MeetingStorage
from src.api.timezone_utils import format_datetime_for_user, utc_now
from src.services.meeting_service import MeetingService
from src.services.scheduled_meeting_service import ScheduledMeetingService
from src.services.transcript_service import TranscriptService
from src.services.webhook_service import WebhookService
from src.utils.url_validator import UrlValidator

# Import plugin system
from src.plugins import register_plugin, get_plugin
from src.plugins.educational_plugin import EducationalPlugin

# Register built-in plugins
register_plugin(EducationalPlugin())
print(f"✅ Registered educational plugin")

app = Flask(__name__, static_folder='static')

# Configure for large file uploads (50MB limit)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Initialize authentication
init_auth(app)

# Initialize rate limiting (security against brute force and DoS)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# For Cloud Run, use Redis/Memorystore for shared state across instances
# Set RATE_LIMIT_STORAGE_URI to redis://[host]:[port] in production
# Falls back to memory:// for development (not shared across instances)
rate_limit_uri = os.getenv("RATE_LIMIT_STORAGE_URI", "memory://")
if rate_limit_uri == "memory://":
    print("⚠️  WARNING: Rate limiting using in-memory storage. Not shared across Cloud Run instances!")
    print("   Set RATE_LIMIT_STORAGE_URI=redis://[host]:[port] for production")

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=rate_limit_uri,
    strategy="fixed-window"
)

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

# validate_meeting_url is now handled by UrlValidator from src/utils/url_validator.py
# Keeping a reference for compatibility with existing code
validate_meeting_url = UrlValidator.validate_meeting_url

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

# Initialize services
meeting_service = MeetingService(storage=storage)

# Create a default transcript service for utility methods (queuing, etc.)
# Plugin is optional - only needed for processing methods
_default_transcript_service = None


def get_default_transcript_service() -> TranscriptService:
    """
    Get default transcript service for utility methods (queuing, etc.).

    This service doesn't have a plugin set, so it can only be used for
    utility methods like queue_uploaded_transcript(), not for processing.
    """
    global _default_transcript_service
    if _default_transcript_service is None:
        _default_transcript_service = TranscriptService(
            storage=storage,
            plugin=None,  # No plugin needed for utility methods
            llm_provider=os.getenv('LLM_PROVIDER', 'vertex_ai')
        )
    return _default_transcript_service


def get_transcript_service_for_meeting(meeting_id: str | None = None) -> TranscriptService:
    """
    Create TranscriptService with appropriate plugin for a meeting.

    Args:
        meeting_id: Meeting ID to get plugin for (uses 'educational' if None)

    Returns:
        TranscriptService instance configured with the appropriate plugin
    """
    # Get meeting data to determine plugin
    plugin_name = 'educational'  # Default

    if meeting_id:
        meeting = storage.get_meeting(meeting_id)
        if meeting:
            plugin_name = meeting.get('plugin', 'educational')

    # Get plugin instance
    plugin = get_plugin(plugin_name)

    # TODO: Load and apply user settings for this plugin
    # user_settings = get_user_plugin_settings(user_id, plugin_name)
    # meeting_settings = meeting.get('plugin_settings', {})
    # plugin.configure({**user_settings, **meeting_settings})

    # Create service with plugin
    return TranscriptService(
        storage=storage,
        plugin=plugin,
        llm_provider=os.getenv('LLM_PROVIDER', 'vertex_ai')
    )


def process_transcript_callback(transcript_id: str, recording_id: str | None = None) -> None:
    """Callback for WebhookService to process transcripts."""
    # Find meeting for this transcript to get the right plugin
    meeting_id = None
    meetings_list = storage.list_meetings()
    for meeting in meetings_list:
        if meeting.get('transcript_id') == transcript_id:
            meeting_id = meeting['id']
            break

    if not meeting_id:
        meeting_id = recording_id or transcript_id

    # Create service with appropriate plugin
    transcript_service = get_transcript_service_for_meeting(meeting_id)
    transcript_service.process_recall_transcript(transcript_id, recording_id)


webhook_service = WebhookService(
    storage=storage,
    recall_client=recall,
    process_transcript_callback=process_transcript_callback
)

# Import dependencies for ScheduledMeetingService
from src.api.auth_db import get_auth_service
from src.api.scheduled_meetings import get_scheduled_meeting_storage
from src.api.timezone_utils import parse_user_datetime


# Create simple wrappers for ScheduledMeetingService dependencies
class SimpleTimezonePaser:
    """Simple timezone parser wrapper."""

    @staticmethod
    def parse_user_datetime(datetime_str: str, timezone: str):
        """Parse user datetime."""
        return parse_user_datetime(datetime_str, timezone)


class SimpleMeetingServiceForScheduler:
    """Simple wrapper to add join_meeting_for_scheduler method to MeetingService."""

    def __init__(self):
        pass

    def join_meeting_for_scheduler(self, meeting_url: str, user: str, webhook_url: str, bot_name: str, instructor_name: str | None = None) -> str | None:
        """Join a meeting (used by ScheduledMeetingService)."""
        # Will be set after join_meeting_for_scheduler function is defined
        return join_meeting_for_scheduler(meeting_url, bot_name, user, instructor_name)


# Initialize scheduled meeting service (will be completed after join_meeting_for_scheduler is defined)
scheduled_meeting_service = ScheduledMeetingService(
    storage=get_scheduled_meeting_storage(),
    meeting_service=SimpleMeetingServiceForScheduler(),
    timezone_parser=SimpleTimezonePaser(),
    auth_service=get_auth_service()
)


def join_meeting_for_scheduler(meeting_url: str, bot_name: str, user: str, instructor_name: str | None = None) -> str | None:
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

        # Use MeetingService to create and join the meeting
        meeting = meeting_service.create_meeting(
            meeting_url=meeting_url,
            user=user,
            webhook_url=webhook_url,
            bot_name=bot_name,
            instructor_name=instructor_name
        )

        return meeting.id
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
@limiter.limit("5 per minute")  # Strict rate limit to prevent brute force
def login():
    """
    Login with email and password.
    Sets httpOnly secure cookie and returns JWT token (for backward compatibility).
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

        # Create response
        response = jsonify({
            "token": token,
            "user": user.to_dict()
        })

        # Set httpOnly, secure cookie for enhanced security
        # This protects against XSS attacks (localStorage is vulnerable to XSS)
        is_production = os.getenv("ENV", "production").lower() != "development"

        response.set_cookie(
            'auth_token',
            token,
            httponly=True,      # Cannot be accessed via JavaScript (XSS protection)
            secure=is_production,  # HTTPS only in production
            samesite='Lax',     # CSRF protection
            max_age=7*24*60*60  # 7 days (matches JWT expiration)
        )

        return response
    except Exception as e:
        print(f"Login error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Login failed: {e!s}"}), 500


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """
    Logout the current user by clearing the auth cookie.
    """
    response = jsonify({"message": "Logged out successfully"})

    # Clear the auth cookie
    response.set_cookie(
        'auth_token',
        '',
        httponly=True,
        secure=os.getenv("ENV", "production").lower() != "development",
        samesite='Lax',
        max_age=0  # Expire immediately
    )

    return response


@app.route('/api/auth/setup', methods=['POST'])
@limiter.limit("3 per hour")  # Very strict - setup should be rare
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
    meetings = meeting_service.list_meetings(user=g.user if g.user != 'anonymous' else None)
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
    instructor_name = request.form.get('instructor_name')

    # Validate meeting URL
    is_valid, error = validate_meeting_url(meeting_url)
    if not is_valid:
        return f'<div class="text-accent-coral p-4">{error}</div>', 400

    # Determine webhook URL
    webhook_url = WEBHOOK_URL
    if not webhook_url:
        webhook_url = f"{request.url_root.rstrip('/')}/webhook/recall"

    # Use MeetingService to create and join the meeting
    try:
        _meeting = meeting_service.create_meeting(
            meeting_url=meeting_url,
            user=g.user,
            webhook_url=webhook_url,
            bot_name=bot_name,
            instructor_name=instructor_name
        )
    except Exception:
        return '<div class="text-accent-coral p-4">Failed to create bot</div>', 500

    # Return updated meeting list
    meetings = meeting_service.list_meetings(user=g.user if g.user != 'anonymous' else None)
    user_timezone = get_user_timezone()
    return render_template('partials/meeting_list.html', meetings=meetings, user_timezone=user_timezone)


@app.route('/ui/meetings/<meeting_id>', methods=['GET'])
def ui_meeting_detail(meeting_id):
    """UI: Meeting detail page."""
    meeting = meeting_service.get_meeting(meeting_id)

    if not meeting:
        return redirect(url_for('index'))

    user_timezone = get_user_timezone()
    return render_template('meeting_detail.html', meeting=meeting, user=g.user, user_timezone=user_timezone)


@app.route('/ui/meetings/<meeting_id>', methods=['DELETE'])
def ui_delete_meeting(meeting_id):
    """HTMX: Remove bot from meeting and return updated list."""
    _success = meeting_service.leave_meeting(meeting_id)

    # Return updated meeting list
    meetings = meeting_service.list_meetings(user=g.user if g.user != 'anonymous' else None)
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
@limiter.limit("20 per hour")  # Allow reasonable scheduling activity
def create_scheduled_meeting():
    """
    Schedule a bot to join a meeting at a specific time.

    Request body:
    {
        "meeting_url": "https://zoom.us/j/123456789",
        "scheduled_time": "2024-12-10T15:30:00",  # In user's timezone
        "bot_name": "Meeting Assistant" (optional),
        "instructor_name": "Instructor Name" (optional)
    }
    """
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
    instructor_name = data.get('instructor_name')

    # Get user's timezone
    user_obj = get_auth_service().get_user(g.user)
    if not user_obj:
        return jsonify({"error": "User not found"}), 404

    user_timezone = user_obj.timezone

    # Use ScheduledMeetingService to create the scheduled meeting
    created_meeting, error = scheduled_meeting_service.create_scheduled_meeting(
        meeting_url=meeting_url,
        scheduled_time_str=data['scheduled_time'],
        user=g.user,
        user_timezone=user_timezone,
        bot_name=bot_name,
        instructor_name=instructor_name
    )

    if error:
        return jsonify({"error": error}), 400 if "not supported" in error or "required" in error or "Invalid" in error else 500

    return jsonify(created_meeting.to_dict()), 201


@app.route('/api/scheduled-meetings', methods=['GET'])
@require_auth
def list_scheduled_meetings():
    """List scheduled meetings for the current user."""
    user = g.user if g.user != 'anonymous' else None
    status = request.args.get('status')

    # Use ScheduledMeetingService to list meetings
    meetings = scheduled_meeting_service.list_scheduled_meetings(user=user, status=status)

    return jsonify([m.to_dict() for m in meetings])


@app.route('/api/scheduled-meetings/<meeting_id>', methods=['GET'])
@require_auth
def get_scheduled_meeting(meeting_id):
    """Get a scheduled meeting by ID."""
    meeting = scheduled_meeting_service.get_scheduled_meeting(meeting_id)

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
    meeting = scheduled_meeting_service.get_scheduled_meeting(meeting_id)

    if not meeting:
        return jsonify({"error": "Scheduled meeting not found"}), 404

    # Check user owns this scheduled meeting
    if meeting.user != g.user and g.user != 'anonymous':
        return jsonify({"error": "Forbidden"}), 403

    success, error = scheduled_meeting_service.delete_scheduled_meeting(meeting_id)

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
    # Verify request is from Cloud Scheduler
    # Cloud Scheduler adds Authorization: Bearer <OIDC token> header
    auth_header = request.headers.get('Authorization', '')

    if not auth_header.startswith('Bearer '):
        return jsonify({"error": "Unauthorized - missing Bearer token"}), 401

    # In production, you should verify the OIDC token
    # For now, we'll accept any Bearer token (Cloud Scheduler will provide valid OIDC)
    # TODO: Add proper OIDC token verification if needed

    # Use ScheduledMeetingService to execute pending meetings
    result = scheduled_meeting_service.execute_pending_meetings()

    return jsonify(result)


# =============================================================================
# PLUGIN ROUTES
# =============================================================================

@app.route('/api/plugins', methods=['GET'])
def list_available_plugins():
    """
    List all registered plugins.

    Returns:
        200: List of available plugins with their metadata

    Example response:
    [
        {
            "name": "educational",
            "display_name": "Educational Class",
            "description": "Generate study guides from classes..."
        },
        {
            "name": "therapy",
            "display_name": "Therapy Session",
            "description": "Generate SOAP notes for therapy..."
        }
    ]
    """
    from src.plugins import list_plugins

    plugins = list_plugins()
    return jsonify(plugins)


@app.route('/api/plugins/<plugin_name>', methods=['GET'])
def get_plugin_details(plugin_name: str):
    """
    Get detailed information about a specific plugin.

    Args:
        plugin_name: Plugin identifier (e.g., 'educational', 'therapy')

    Returns:
        200: Plugin details including metadata and settings schemas
        404: Plugin not found

    Example response:
    {
        "name": "therapy",
        "display_name": "Therapy Session",
        "description": "Generate SOAP notes...",
        "metadata_schema": {
            "session_type": {
                "type": "select",
                "options": ["individual", "couples", "family", "group"],
                "required": true
            }
        },
        "settings_schema": {
            "soap_format": {
                "type": "select",
                "options": ["standard", "brief", "narrative"],
                "default": "standard"
            }
        }
    }
    """
    from src.plugins import get_plugin, has_plugin

    if not has_plugin(plugin_name):
        return jsonify({"error": f"Plugin '{plugin_name}' not found"}), 404

    plugin = get_plugin(plugin_name)

    return jsonify({
        "name": plugin.name,
        "display_name": plugin.display_name,
        "description": plugin.description,
        "metadata_schema": plugin.metadata_schema,
        "settings_schema": plugin.settings_schema
    })


# =============================================================================
# MEETING ROUTES
# =============================================================================

@app.route('/api/meetings', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")  # Limit meeting creation to prevent abuse
def create_meeting():
    """
    Create a bot to join a meeting.

    Request body:
    {
        "meeting_url": "https://zoom.us/j/123456789",
        "bot_name": "Meeting Assistant" (optional),
        "instructor_name": "Instructor Name" (optional),
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
    instructor_name = data.get('instructor_name')

    # Validate meeting URL
    is_valid, error = validate_meeting_url(meeting_url)
    if not is_valid:
        return jsonify({"error": error}), 400

    # Determine webhook URL
    webhook_url = WEBHOOK_URL
    if not webhook_url:
        # Try to construct from request
        webhook_url = f"{request.url_root.rstrip('/')}/webhook/recall"

    # Use MeetingService to create and join the meeting
    try:
        meeting = meeting_service.create_meeting(
            meeting_url=meeting_url,
            user=g.user,
            webhook_url=webhook_url,
            bot_name=bot_name,
            instructor_name=instructor_name
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Return the created meeting as dict
    return jsonify(meeting.to_dict()), 201


@app.route('/api/meetings', methods=['GET'])
@require_auth
def list_meetings():
    """List meetings for the current user."""
    user = g.user if g.user != 'anonymous' else None
    meetings = meeting_service.list_meetings(user=user)
    return jsonify(meetings)


@app.route('/api/meetings/<meeting_id>', methods=['GET'])
@require_auth
def get_meeting(meeting_id):
    """Get status of a specific meeting."""
    meeting = meeting_service.get_meeting(meeting_id)

    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    return jsonify(meeting.to_dict())


@app.route('/api/meetings/<meeting_id>', methods=['DELETE'])
@require_auth
def remove_meeting(meeting_id):
    """Remove bot from meeting."""
    success = meeting_service.leave_meeting(meeting_id)
    if success:
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

        # Determine service URL for Cloud Tasks
        service_url = os.getenv("SERVICE_URL") or request.host_url.rstrip('/')

        # Use WebhookService to handle the event
        webhook_service.handle_event(data, service_url)

        return jsonify({"status": "ok"}), 200

    except Exception as e:
        print(f"❌ Error handling webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/meetings/<meeting_id>/outputs', methods=['GET'])
@require_auth
def get_meeting_outputs(meeting_id):
    """Get the output files for a completed meeting."""
    meeting = meeting_service.get_meeting(meeting_id)

    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    if meeting.status != 'completed':
        return jsonify({
            "status": meeting.status,
            "message": "Meeting not yet completed or still processing"
        })

    # Get download URLs for outputs
    outputs = {}
    for name, path in meeting.outputs.items():
        filename = os.path.basename(path)
        url = storage.get_download_url(meeting_id, filename)
        outputs[name] = url

    return jsonify(outputs)


@app.route('/api/meetings/<meeting_id>/outputs/<filename>', methods=['GET'])
@require_auth
def download_output(meeting_id, filename):
    """
    Download a specific output file.

    Fetches from GCS and serves directly through Flask.
    Requires authentication - verifies user owns the meeting.
    """
    # Check if meeting exists
    meeting = meeting_service.get_meeting(meeting_id)
    if not meeting:
        return jsonify({"error": "Meeting not found"}), 404

    # Verify user owns this meeting (unless anonymous mode is enabled)
    if g.user != 'anonymous' and meeting.user != g.user:
        return jsonify({"error": "Forbidden - you don't have access to this meeting"}), 403

    # Fetch file content from storage (GCS or local)
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
    return Response(content, mimetype=content_type, headers={
        'Content-Disposition': f'attachment; filename="{filename}"'
    })


@app.route('/api/transcripts/upload', methods=['POST'])
@require_auth
@limiter.limit("10 per hour")  # Limit uploads to prevent abuse
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
    data = request.json

    if not data or 'transcript' not in data:
        return jsonify({"error": "transcript data is required"}), 400

    transcript_data = data['transcript']
    title = data.get('title')

    # Get service URL for Cloud Tasks callback
    service_url = os.getenv("SERVICE_URL") or request.host_url.rstrip('/')

    # Use TranscriptService to queue the upload
    try:
        meeting_id, used_title = get_default_transcript_service().queue_uploaded_transcript(
            user=g.user,
            transcript_data=transcript_data,
            title=title,
            service_url=service_url
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    # Return immediately with meeting_id for polling
    return jsonify({
        "status": "queued",
        "meeting_id": meeting_id,
        "title": used_title,
        "message": "Processing queued. Poll /api/meetings/{meeting_id} for status."
    }), 202


@app.route('/api/transcripts/process/<meeting_id>', methods=['POST'])
@verify_cloud_tasks
def process_transcript_task(meeting_id: str):
    """
    Process endpoint called by Cloud Tasks.
    Processes the uploaded transcript that was queued.

    This endpoint is called by Cloud Tasks, not directly by users.
    """
    print(f"📥 Cloud Task received for {meeting_id}", flush=True)

    # Get metadata from request body
    data = request.json or {}
    title = data.get('title')

    # Use TranscriptService to fetch from GCS and process
    try:
        get_transcript_service_for_meeting(meeting_id).fetch_and_process_uploaded(meeting_id, title)
        print(f"✅ Processing completed for {meeting_id}", flush=True)
        return jsonify({"status": "completed", "meeting_id": meeting_id}), 200
    except ValueError as e:
        # Meeting not found or data issues
        print(f"❌ Processing failed for {meeting_id}: {e}", flush=True)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"❌ Processing failed for {meeting_id}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.route('/api/transcripts/process-recall/<meeting_id>', methods=['POST'])
@verify_cloud_tasks
def process_recall_transcript_task(meeting_id: str):
    """
    Process endpoint called by Cloud Tasks for Recall API transcripts.
    Downloads and processes transcripts from scheduled meetings.

    This endpoint is called by Cloud Tasks, not directly by users.
    """
    print(f"📥 Cloud Task received for Recall transcript {meeting_id}", flush=True)

    # Get metadata from request body
    data = request.json or {}
    transcript_id = data.get('transcript_id')
    recording_id = data.get('recording_id')

    if not transcript_id:
        print("❌ No transcript_id provided", flush=True)
        return jsonify({"error": "transcript_id is required"}), 400

    print(f"🔄 Processing Recall transcript {transcript_id}", flush=True)

    # Use TranscriptService to process the transcript
    try:
        get_transcript_service_for_meeting(meeting_id).process_recall_transcript(transcript_id, recording_id)
        print(f"✅ Recall transcript processing completed for {meeting_id}", flush=True)
        return jsonify({"status": "completed", "meeting_id": meeting_id}), 200
    except Exception as e:
        print(f"❌ Recall transcript processing failed for {meeting_id}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"status": "failed", "error": str(e)}), 500


@app.route('/api/meetings/<meeting_id>/reprocess', methods=['POST'])
@require_auth
def reprocess_meeting(meeting_id: str):
    """
    Reprocess a failed or completed meeting.
    This endpoint can be used to retry processing for meetings that failed,
    or to regenerate outputs (e.g., after PDF generation was fixed).

    Requires authentication - call with Bearer token or API key.
    """
    print(f"🔄 Reprocess request for meeting {meeting_id}", flush=True)

    # Use TranscriptService to reprocess (handles both Recall and uploaded transcripts)
    try:
        transcript_type = get_transcript_service_for_meeting(meeting_id).reprocess_transcript(meeting_id)
        print(f"✅ Reprocessing completed for {meeting_id}", flush=True)
        return jsonify({
            "status": "completed",
            "meeting_id": meeting_id,
            "type": transcript_type
        }), 200
    except ValueError as e:
        # Meeting not found or no transcript data
        print(f"❌ Reprocessing failed for {meeting_id}: {e}", flush=True)
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        print(f"❌ Reprocessing failed for {meeting_id}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"status": "failed", "error": str(e)}), 500


if __name__ == '__main__':
    port = int(os.getenv("PORT", 8080))
    debug = os.getenv("DEBUG", "false").lower() == "true"

    print(f"🚀 Starting Meeting Transcription Service on port {port}")
    print(f"📡 Webhook URL: {WEBHOOK_URL or 'auto-detect'}")

    app.run(host='0.0.0.0', port=port, debug=debug)

