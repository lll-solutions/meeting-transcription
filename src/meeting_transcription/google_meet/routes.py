"""
Flask routes for Google Meet OAuth and settings.

Provides:
- /oauth/google/authorize - Start OAuth flow
- /oauth/google/callback - Handle OAuth callback
- /settings - Settings page with Google Meet integration
- /settings/google-meet/disconnect - Disconnect Google account
- /settings/google-meet/subscribe - Enable transcript event subscription
- /webhook/google-meet - Pub/Sub push endpoint
"""

import logging
import os

from flask import Blueprint, g, jsonify, redirect, render_template, request

from .config import get_google_oauth_config
from .oauth import GoogleOAuthFlow, delete_google_tokens, get_google_tokens, is_google_connected
from .session_handler import MeetSessionHandler
from .webhook_handler import MeetWebhookHandler
from .workspace_events import WorkspaceEventsManager

logger = logging.getLogger(__name__)

google_meet_bp = Blueprint("google_meet", __name__)


# ---------------------------------------------------------------------------
# OAuth flow
# ---------------------------------------------------------------------------


@google_meet_bp.route("/oauth/google/authorize")
def google_authorize():
    """Start the Google OAuth authorization flow."""
    config = get_google_oauth_config()
    if not config.is_configured:
        return jsonify({"error": "Google OAuth is not configured"}), 500

    user_id = getattr(g, "user", None)
    if not user_id or user_id == "anonymous":
        return redirect("/")

    flow = GoogleOAuthFlow()
    auth_url, _state = flow.get_authorization_url(user_id)
    return redirect(auth_url)


@google_meet_bp.route("/oauth/google/callback")
def google_callback():
    """Handle the Google OAuth callback."""
    code = request.args.get("code")
    state = request.args.get("state")
    error = request.args.get("error")

    if error:
        logger.warning("Google OAuth error: %s", error)
        return redirect("/settings?error=oauth_denied")

    if not code or not state:
        return redirect("/settings?error=missing_params")

    flow = GoogleOAuthFlow()
    try:
        flow.handle_callback(code, state)

        # Auto-create Workspace Events subscription
        user_id = getattr(g, "user", None)
        if user_id and user_id != "anonymous":
            try:
                manager = WorkspaceEventsManager()
                manager.create_subscription(user_id)
            except Exception as e:
                print(f"Warning: Could not auto-subscribe: {e}")

        return redirect("/settings?connected=true")
    except ValueError as e:
        logger.warning("OAuth callback failed: %s", e)
        return redirect("/settings?error=oauth_failed")


# ---------------------------------------------------------------------------
# Settings page
# ---------------------------------------------------------------------------


@google_meet_bp.route("/settings")
def settings_page():
    """Render the settings page."""
    user_id = getattr(g, "user", None)
    if not user_id or user_id == "anonymous":
        return redirect("/")

    config = get_google_oauth_config()

    # Check Google connection status
    connected = is_google_connected(user_id)
    google_email = ""
    subscribed = False

    if connected:
        tokens = get_google_tokens(user_id)
        google_email = tokens.get("google_email", "") if tokens else ""

        manager = WorkspaceEventsManager()
        subscribed = manager.is_subscribed(user_id)

    return render_template(
        "settings.html",
        user=user_id,
        google_connected=connected,
        google_email=google_email,
        google_subscribed=subscribed,
        oauth_mode=config.mode.value,
        oauth_config=config,
        oauth_configured=config.is_configured,
    )


# ---------------------------------------------------------------------------
# Google Meet management
# ---------------------------------------------------------------------------


@google_meet_bp.route("/settings/google-meet/disconnect", methods=["POST"])
def google_disconnect():
    """Disconnect Google Meet integration."""
    user_id = getattr(g, "user", None)
    if not user_id or user_id == "anonymous":
        return redirect("/")

    # Delete Workspace Events subscription
    manager = WorkspaceEventsManager()
    manager.delete_subscription(user_id)

    # Delete stored tokens
    delete_google_tokens(user_id)

    return redirect("/settings?disconnected=true")


@google_meet_bp.route("/settings/google-meet/subscribe", methods=["POST"])
def google_subscribe():
    """Enable transcript event subscription."""
    user_id = getattr(g, "user", None)
    if not user_id or user_id == "anonymous":
        return redirect("/")

    if not is_google_connected(user_id):
        return redirect("/settings?error=not_connected")

    manager = WorkspaceEventsManager()
    try:
        manager.create_subscription(user_id)
        return redirect("/settings?subscribed=true")
    except ValueError as e:
        logger.warning("Subscription creation failed: %s", e)
        return redirect("/settings?error=subscription_failed")


# ---------------------------------------------------------------------------
# Pub/Sub webhook
# ---------------------------------------------------------------------------


@google_meet_bp.route("/webhook/google-meet", methods=["POST"])
def google_meet_webhook():
    """
    Handle Pub/Sub push messages for Google Meet transcript events.

    This endpoint receives messages from Cloud Pub/Sub when a
    transcript becomes available.
    """
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400

    # Initialize session handler with storage
    from meeting_transcription.api.storage import MeetingStorage

    bucket_name = os.getenv("OUTPUT_BUCKET", "")
    storage = MeetingStorage(bucket_name=bucket_name)
    service_url = os.getenv("SERVICE_URL", "")

    session_handler = MeetSessionHandler(storage=storage, service_url=service_url)

    # Create webhook handler with session creation callback
    def on_transcript_ready(
        user_id: str, transcript_name: str, event_data: dict
    ) -> None:
        try:
            session_handler.handle_transcript_ready(
                user_id, transcript_name, event_data
            )
        except Exception as e:
            print(f"Error handling transcript: {e}")

    handler = MeetWebhookHandler(on_transcript_ready=on_transcript_ready)

    try:
        result = handler.handle_push_message(data)
        return jsonify(result), 200
    except ValueError as e:
        logger.error("Webhook error: %s", e)
        return jsonify({"error": "Invalid webhook payload"}), 400


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------


@google_meet_bp.route("/api/google-meet/status")
def google_meet_status():
    """Get Google Meet integration status for the current user."""
    user_id = getattr(g, "user", None)
    if not user_id or user_id == "anonymous":
        return jsonify({"connected": False}), 200

    config = get_google_oauth_config()
    connected = is_google_connected(user_id)

    result = {
        "configured": config.is_configured,
        "connected": connected,
        "mode": config.mode.value,
    }

    if connected:
        tokens = get_google_tokens(user_id)
        result["google_email"] = tokens.get("google_email", "") if tokens else ""

        manager = WorkspaceEventsManager()
        result["subscribed"] = manager.is_subscribed(user_id)

    return jsonify(result)


@google_meet_bp.route("/ui/google-meet/transcripts")
def google_meet_transcripts_partial():
    """HTMX partial: Google Meet transcript status panel."""
    user_id = getattr(g, "user", None)
    if not user_id or user_id == "anonymous":
        return ""

    from meeting_transcription.api.storage import MeetingStorage

    bucket_name = os.getenv("OUTPUT_BUCKET", "")
    storage = MeetingStorage(bucket_name=bucket_name)

    # Get all meetings from Google Meet provider
    all_meetings = storage.list_meetings(user=user_id)
    google_meet_meetings = [
        m for m in all_meetings if m.get("provider") == "google_meet"
    ]

    # Sort: pending/processing first, then by creation date
    status_order = {"queued": 0, "processing": 1, "failed": 2, "completed": 3}
    google_meet_meetings.sort(
        key=lambda m: (status_order.get(m.get("status", ""), 99), m.get("created_at", ""))
    )

    user_timezone = "America/New_York"

    return render_template(
        "partials/google_meet_status.html",
        google_meet_meetings=google_meet_meetings,
        user_timezone=user_timezone,
    )
