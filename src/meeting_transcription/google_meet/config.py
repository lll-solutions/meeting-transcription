"""
Google OAuth configuration for Meet integration.

Supports two deployment modes:
- Shared (SaaS): All customers use a single verified OAuth app
- BYOC (self-hosted): Customer provides their own Google Cloud OAuth credentials

Environment variables:
    GOOGLE_OAUTH_CLIENT_ID: OAuth 2.0 client ID
    GOOGLE_OAUTH_CLIENT_SECRET: OAuth 2.0 client secret
    GOOGLE_OAUTH_MODE: "shared" or "byoc" (default: "shared")
    GOOGLE_OAUTH_REDIRECT_URI: OAuth redirect URI (auto-detected if not set)
    GOOGLE_PUBSUB_PROJECT_ID: GCP project for Pub/Sub (defaults to GOOGLE_CLOUD_PROJECT)
    GOOGLE_PUBSUB_TOPIC: Pub/Sub topic for Meet events
    GOOGLE_PUBSUB_SUBSCRIPTION: Pub/Sub subscription name
"""

import os
from enum import Enum


class GoogleOAuthMode(Enum):
    """OAuth deployment mode."""

    SHARED = "shared"  # SaaS: single verified OAuth app for all customers
    BYOC = "byoc"  # Self-hosted: customer provides own OAuth credentials


# OAuth scopes required for Google Meet transcript access
GOOGLE_MEET_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/meetings.space.readonly",
    "https://www.googleapis.com/auth/meetings.space.created",
]


class GoogleOAuthConfig:
    """
    Configuration for Google OAuth and Meet integration.

    Reads from environment variables and validates that required
    settings are present for the selected mode.
    """

    def __init__(self) -> None:
        # OAuth credentials
        self.client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
        self.client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

        # Deployment mode
        mode_str = os.getenv("GOOGLE_OAUTH_MODE", "shared").lower()
        try:
            self.mode = GoogleOAuthMode(mode_str)
        except ValueError:
            self.mode = GoogleOAuthMode.SHARED

        # Redirect URI (auto-detected from SERVICE_URL if not set)
        self.redirect_uri = os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "")
        if not self.redirect_uri:
            service_url = os.getenv("SERVICE_URL", "")
            if service_url:
                self.redirect_uri = f"{service_url.rstrip('/')}/oauth/google/callback"

        # Pub/Sub configuration
        self.pubsub_project_id = os.getenv(
            "GOOGLE_PUBSUB_PROJECT_ID",
            os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        )
        self.pubsub_topic = os.getenv(
            "GOOGLE_PUBSUB_TOPIC", "meet-transcript-events"
        )
        self.pubsub_subscription = os.getenv(
            "GOOGLE_PUBSUB_SUBSCRIPTION", "meet-transcript-push"
        )

        # Scopes
        self.scopes = list(GOOGLE_MEET_SCOPES)

    @property
    def is_configured(self) -> bool:
        """Check if OAuth credentials are configured."""
        return bool(self.client_id and self.client_secret)

    @property
    def pubsub_topic_path(self) -> str:
        """Full Pub/Sub topic path."""
        return f"projects/{self.pubsub_project_id}/topics/{self.pubsub_topic}"

    @property
    def pubsub_subscription_path(self) -> str:
        """Full Pub/Sub subscription path."""
        return (
            f"projects/{self.pubsub_project_id}"
            f"/subscriptions/{self.pubsub_subscription}"
        )

    def validate(self) -> list[str]:
        """
        Validate configuration and return list of errors.

        Returns:
            List of error strings (empty if valid)
        """
        errors = []

        if not self.client_id:
            errors.append("GOOGLE_OAUTH_CLIENT_ID is required")
        if not self.client_secret:
            errors.append("GOOGLE_OAUTH_CLIENT_SECRET is required")
        if not self.redirect_uri:
            errors.append(
                "GOOGLE_OAUTH_REDIRECT_URI or SERVICE_URL is required"
            )
        if not self.pubsub_project_id:
            errors.append(
                "GOOGLE_PUBSUB_PROJECT_ID or GOOGLE_CLOUD_PROJECT is required"
            )

        return errors

    def to_dict(self) -> dict:
        """Return safe (no secrets) configuration summary."""
        return {
            "mode": self.mode.value,
            "configured": self.is_configured,
            "redirect_uri": self.redirect_uri,
            "pubsub_project_id": self.pubsub_project_id,
            "pubsub_topic": self.pubsub_topic,
            "scopes": self.scopes,
        }


# Singleton instance
_config: GoogleOAuthConfig | None = None


def get_google_oauth_config() -> GoogleOAuthConfig:
    """Get the Google OAuth config singleton."""
    global _config
    if _config is None:
        _config = GoogleOAuthConfig()
    return _config
