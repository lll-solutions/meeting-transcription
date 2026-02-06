"""
Pub/Sub push handler for Google Meet transcript events.

Receives push messages from Cloud Pub/Sub when a Meet transcript
becomes available, validates them, and triggers transcript fetching.
"""

import base64
import json
from collections.abc import Callable
from typing import Any

from .config import get_google_oauth_config


class MeetWebhookHandler:
    """
    Handles incoming Pub/Sub push messages for Meet transcript events.

    The push message format from Pub/Sub:
    {
        "message": {
            "data": "<base64-encoded JSON>",
            "messageId": "...",
            "publishTime": "..."
        },
        "subscription": "projects/.../subscriptions/..."
    }

    The decoded data contains the Workspace Events notification:
    {
        "subscriptionId": "...",
        "targetResource": "//meet.googleapis.com/spaces/...",
        "eventType": "google.workspace.meet.transcript.v2.fileGenerated",
        "event": {
            "transcript": {
                "name": "conferenceRecords/.../transcripts/...",
                ...
            }
        }
    }
    """

    def __init__(
        self,
        on_transcript_ready: Callable[[str, str, dict[str, Any]], None] | None = None,
    ) -> None:
        """
        Args:
            on_transcript_ready: Callback when a transcript is ready.
                Called with (user_id, transcript_name, event_data).
        """
        self.config = get_google_oauth_config()
        self._on_transcript_ready = on_transcript_ready

    def handle_push_message(self, request_data: dict[str, Any]) -> dict[str, str]:
        """
        Process a Pub/Sub push message.

        Args:
            request_data: The raw request JSON from Pub/Sub push

        Returns:
            Dict with processing result

        Raises:
            ValueError: If message format is invalid
        """
        # Validate subscription matches our expected subscription
        subscription = request_data.get("subscription", "")
        if (
            subscription
            and self.config.pubsub_subscription
            and self.config.pubsub_subscription not in subscription
        ):
            raise ValueError(
                f"Unexpected subscription: {subscription}"
            )

        message = request_data.get("message")
        if message is None:
            raise ValueError("Missing 'message' in push data")

        # Decode the base64-encoded data
        raw_data = message.get("data", "")
        if not raw_data:
            raise ValueError("Missing 'data' in message")

        try:
            decoded = base64.b64decode(raw_data)
            event_data = json.loads(decoded)
        except (base64.binascii.Error, json.JSONDecodeError) as e:
            raise ValueError(f"Failed to decode message data: {e}") from e

        message_id = message.get("messageId", "unknown")
        event_type = event_data.get("eventType", "")

        print(f"Received Meet event: {event_type} (msg: {message_id})")

        # Route by event type
        if event_type == "google.workspace.meet.transcript.v2.fileGenerated":
            return self._handle_transcript_generated(event_data, message_id)

        # Unknown event type — acknowledge but skip
        return {"status": "skipped", "reason": f"Unhandled event type: {event_type}"}

    def _handle_transcript_generated(
        self, event_data: dict[str, Any], message_id: str
    ) -> dict[str, str]:
        """Handle a transcript.fileGenerated event."""
        event = event_data.get("event", {})
        transcript_info = event.get("transcript", {})
        transcript_name = transcript_info.get("name", "")

        if not transcript_name:
            return {"status": "error", "reason": "No transcript name in event"}

        # Extract conference record ID from transcript name
        # Format: conferenceRecords/{id}/transcripts/{id}
        parts = transcript_name.split("/")
        conference_record_id = parts[1] if len(parts) >= 2 else ""

        # Look up which user this subscription belongs to
        subscription_id = event_data.get("subscriptionId", "")
        user_id = self._resolve_user_from_subscription(subscription_id)

        print(
            f"Transcript ready: {transcript_name} "
            f"(conference: {conference_record_id}, user: {user_id})"
        )

        # Trigger transcript fetching
        if self._on_transcript_ready and user_id:
            self._on_transcript_ready(user_id, transcript_name, event_data)

        return {
            "status": "processed",
            "transcript_name": transcript_name,
            "conference_record_id": conference_record_id,
            "user_id": user_id or "unknown",
        }

    def _resolve_user_from_subscription(self, subscription_id: str) -> str | None:
        """
        Find the app user associated with a Workspace Events subscription.

        Looks up the subscription ID in our stored subscriptions to find
        the user who created it.
        """
        import os

        try:
            from google.cloud import firestore

            if os.getenv("GOOGLE_CLOUD_PROJECT"):
                db = firestore.Client()
                # Query subscriptions collection for matching subscription ID
                docs = (
                    db.collection("google_meet_subscriptions")
                    .where("name", "==", subscription_id)
                    .limit(1)
                    .stream()
                )
                for doc in docs:
                    return doc.id  # Document ID is the user_id
        except ImportError:
            pass

        return None
