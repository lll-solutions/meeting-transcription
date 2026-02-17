"""
Google Workspace Events API subscription manager.

Subscribes to Meet transcript events so the app is notified
when a transcript becomes available after a meeting.

Uses the Workspace Events API v1:
https://developers.google.com/workspace/events
"""

import logging
from datetime import UTC, datetime
from typing import Any

import requests

from .config import get_google_oauth_config
from .oauth import GoogleOAuthFlow

logger = logging.getLogger(__name__)

# Workspace Events API base URL
WORKSPACE_EVENTS_API = "https://workspaceevents.googleapis.com/v1"

# Event type for transcript file generation
TRANSCRIPT_EVENT_TYPE = "google.workspace.meet.transcript.v2.fileGenerated"

# Subscription lasts up to 7 days and must be renewed
SUBSCRIPTION_TTL_HOURS = 168  # 7 days


class WorkspaceEventsManager:
    """Manages Workspace Events API subscriptions for Meet transcript events."""

    def __init__(self) -> None:
        self.config = get_google_oauth_config()
        self.oauth = GoogleOAuthFlow()

    def create_subscription(
        self,
        user_id: str,
        target_resource: str = "//meet.googleapis.com/spaces/-",
    ) -> dict[str, Any]:
        """
        Create a Workspace Events subscription for a user.

        Subscribes to transcript events for all of the user's Meet spaces.

        Args:
            user_id: App user ID (must have connected Google account)
            target_resource: The resource to watch. Use "//meet.googleapis.com/spaces/-"
                for all spaces the user organizes.

        Returns:
            Subscription resource dict from the API

        Raises:
            ValueError: If user hasn't connected Google or API call fails
        """
        access_token = self.oauth.get_valid_access_token(user_id)
        if not access_token:
            raise ValueError(
                "User has not connected their Google account"
            )

        payload = {
            "targetResource": target_resource,
            "eventTypes": [TRANSCRIPT_EVENT_TYPE],
            "notificationEndpoint": {
                "pubsubTopic": self.config.pubsub_topic_path,
            },
            "payloadOptions": {
                "includeResource": True,
            },
        }

        resp = requests.post(
            f"{WORKSPACE_EVENTS_API}/subscriptions",
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        if resp.status_code == 401:
            # Token expired, try refresh
            access_token = self.oauth.refresh_access_token(user_id)
            if not access_token:
                raise ValueError("Failed to refresh Google access token")

            resp = requests.post(
                f"{WORKSPACE_EVENTS_API}/subscriptions",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

        if resp.status_code not in (200, 201):
            raise ValueError(
                f"Failed to create subscription: {resp.status_code} {resp.text}"
            )

        subscription = resp.json()

        # Store subscription ID for management
        _store_subscription(user_id, subscription)

        return subscription

    def get_subscription(self, user_id: str) -> dict[str, Any] | None:
        """
        Get the current subscription for a user.

        Args:
            user_id: App user ID

        Returns:
            Subscription dict or None if not subscribed
        """
        return _get_stored_subscription(user_id)

    def delete_subscription(self, user_id: str) -> bool:
        """
        Delete a user's Workspace Events subscription.

        Args:
            user_id: App user ID

        Returns:
            True if deleted successfully
        """
        sub = _get_stored_subscription(user_id)
        if not sub or "name" not in sub:
            _delete_stored_subscription(user_id)
            return True

        access_token = self.oauth.get_valid_access_token(user_id)
        if not access_token:
            # Can't delete remotely, just clear local
            _delete_stored_subscription(user_id)
            return True

        resp = requests.delete(
            f"{WORKSPACE_EVENTS_API}/{sub['name']}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        _delete_stored_subscription(user_id)

        # 404 means already deleted, which is fine
        return resp.status_code in (200, 204, 404)

    def renew_subscription(self, user_id: str) -> dict[str, Any] | None:
        """
        Renew an expiring subscription.

        Subscriptions last 7 days. Call this periodically to keep
        the subscription active.

        Args:
            user_id: App user ID

        Returns:
            Updated subscription or None if renewal failed
        """
        sub = _get_stored_subscription(user_id)
        if not sub or "name" not in sub:
            # No existing subscription, create new
            return self.create_subscription(user_id)

        access_token = self.oauth.get_valid_access_token(user_id)
        if not access_token:
            return None

        resp = requests.patch(
            f"{WORKSPACE_EVENTS_API}/{sub['name']}",
            json={
                "eventTypes": [TRANSCRIPT_EVENT_TYPE],
            },
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            params={"updateMask": "eventTypes"},
            timeout=30,
        )

        if resp.status_code == 404:
            # Subscription expired, create new
            return self.create_subscription(user_id)

        if resp.status_code not in (200, 201):
            print(f"Subscription renewal failed: {resp.status_code} {resp.text}")
            return None

        subscription = resp.json()
        _store_subscription(user_id, subscription)
        return subscription

    def is_subscribed(self, user_id: str) -> bool:
        """Check if a user has an active subscription."""
        sub = _get_stored_subscription(user_id)
        if not sub:
            return False

        # Check if subscription has expired
        expire_time = sub.get("expireTime", "")
        if expire_time:
            try:
                expires = datetime.fromisoformat(expire_time.replace("Z", "+00:00"))
                if expires < datetime.now(UTC):
                    return False
            except (ValueError, TypeError):
                logger.debug("Failed to parse subscription expireTime: %s", expire_time, exc_info=True)

        return True


# ---------------------------------------------------------------------------
# Subscription storage (Firestore-backed)
# ---------------------------------------------------------------------------

_in_memory_subs: dict[str, dict] = {}


def _store_subscription(user_id: str, subscription: dict[str, Any]) -> None:
    """Store a subscription record."""
    import os

    try:
        from google.cloud import firestore

        if os.getenv("GOOGLE_CLOUD_PROJECT"):
            db = firestore.Client()
            db.collection("google_meet_subscriptions").document(user_id).set(
                {
                    **subscription,
                    "stored_at": datetime.now(UTC).isoformat(),
                },
                merge=True,
            )
            return
    except ImportError:
        logger.debug("google-cloud-firestore not installed, using in-memory storage for store", exc_info=True)

    _in_memory_subs[user_id] = subscription


def _get_stored_subscription(user_id: str) -> dict[str, Any] | None:
    """Get stored subscription for a user."""
    import os

    try:
        from google.cloud import firestore

        if os.getenv("GOOGLE_CLOUD_PROJECT"):
            db = firestore.Client()
            doc = (
                db.collection("google_meet_subscriptions")
                .document(user_id)
                .get()
            )
            return doc.to_dict() if doc.exists else None
    except ImportError:
        logger.debug("google-cloud-firestore not installed, using in-memory storage for get", exc_info=True)

    return _in_memory_subs.get(user_id)


def _delete_stored_subscription(user_id: str) -> None:
    """Delete stored subscription."""
    import os

    try:
        from google.cloud import firestore

        if os.getenv("GOOGLE_CLOUD_PROJECT"):
            db = firestore.Client()
            db.collection("google_meet_subscriptions").document(user_id).delete()
            return
    except ImportError:
        logger.debug("google-cloud-firestore not installed, using in-memory storage for delete", exc_info=True)

    _in_memory_subs.pop(user_id, None)
