"""
Google OAuth flow for Meet integration.

Handles:
- Authorization URL generation with Meet scopes
- OAuth callback and token exchange
- Token storage in Firestore (encrypted at rest)
- Token refresh
"""

import os
import secrets
from datetime import UTC, datetime
from typing import Any

import requests

from .config import get_google_oauth_config

# Firestore (optional, falls back to in-memory for dev)
try:
    from google.cloud import firestore

    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False


GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class GoogleOAuthFlow:
    """Manages the Google OAuth 2.0 authorization flow for Meet scopes."""

    def __init__(self) -> None:
        self.config = get_google_oauth_config()

    def get_authorization_url(self, user_id: str) -> tuple[str, str]:
        """
        Generate the Google OAuth authorization URL.

        Args:
            user_id: The app user ID initiating the flow

        Returns:
            Tuple of (authorization_url, state_token)
        """
        state = secrets.token_urlsafe(32)

        # Store state -> user_id mapping for callback validation
        _store_oauth_state(state, user_id)

        params = {
            "client_id": self.config.client_id,
            "redirect_uri": self.config.redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.config.scopes),
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Always show consent to get refresh token
            "state": state,
        }

        query = "&".join(f"{k}={requests.utils.quote(str(v))}" for k, v in params.items())
        return f"{GOOGLE_AUTH_URL}?{query}", state

    def handle_callback(self, code: str, state: str) -> dict[str, Any]:
        """
        Handle the OAuth callback: exchange code for tokens and store them.

        Args:
            code: Authorization code from Google
            state: State parameter for CSRF validation

        Returns:
            Dict with user's Google profile info

        Raises:
            ValueError: If state is invalid or token exchange fails
        """
        # Validate state
        user_id = _get_oauth_state(state)
        if not user_id:
            raise ValueError("Invalid or expired OAuth state")

        # Exchange code for tokens
        token_data = self._exchange_code(code)

        # Get user profile from Google
        profile = self._get_user_profile(token_data["access_token"])

        # Store tokens associated with our app user
        store_google_tokens(
            user_id=user_id,
            tokens={
                "access_token": token_data["access_token"],
                "refresh_token": token_data.get("refresh_token", ""),
                "token_type": token_data.get("token_type", "Bearer"),
                "expires_in": token_data.get("expires_in", 3600),
                "scope": token_data.get("scope", ""),
                "google_email": profile.get("email", ""),
                "google_name": profile.get("name", ""),
                "connected_at": datetime.now(UTC).isoformat(),
            },
        )

        # Clean up state
        _delete_oauth_state(state)

        return profile

    def _exchange_code(self, code: str) -> dict[str, Any]:
        """Exchange authorization code for access and refresh tokens."""
        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "redirect_uri": self.config.redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=30,
        )

        if resp.status_code != 200:
            raise ValueError(f"Token exchange failed: {resp.text}")

        return resp.json()

    def _get_user_profile(self, access_token: str) -> dict[str, Any]:
        """Fetch the user's Google profile."""
        resp = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

        if resp.status_code != 200:
            return {}

        return resp.json()

    def refresh_access_token(self, user_id: str) -> str | None:
        """
        Refresh the access token for a user.

        Args:
            user_id: App user ID

        Returns:
            New access token, or None if refresh fails
        """
        tokens = get_google_tokens(user_id)
        if not tokens or not tokens.get("refresh_token"):
            return None

        resp = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self.config.client_id,
                "client_secret": self.config.client_secret,
                "refresh_token": tokens["refresh_token"],
                "grant_type": "refresh_token",
            },
            timeout=30,
        )

        if resp.status_code != 200:
            print(f"Token refresh failed for user {user_id}: {resp.text}")
            return None

        data = resp.json()
        new_access_token = data["access_token"]

        # Update stored tokens (refresh_token stays the same)
        store_google_tokens(
            user_id=user_id,
            tokens={
                **tokens,
                "access_token": new_access_token,
                "expires_in": data.get("expires_in", 3600),
                "refreshed_at": datetime.now(UTC).isoformat(),
            },
        )

        return new_access_token

    def get_valid_access_token(self, user_id: str) -> str | None:
        """
        Get a valid access token, refreshing if needed.

        Args:
            user_id: App user ID

        Returns:
            Valid access token, or None if user hasn't connected
        """
        tokens = get_google_tokens(user_id)
        if not tokens:
            return None

        # Try the stored token first (simple check — no expiry tracking)
        # If it fails at the API level, the caller can retry with refresh
        return tokens.get("access_token") or self.refresh_access_token(user_id)


# ---------------------------------------------------------------------------
# Token storage (Firestore-backed)
# ---------------------------------------------------------------------------

_firestore_client: Any = None


def _get_db() -> Any:
    """Get Firestore client."""
    global _firestore_client
    if _firestore_client is None and HAS_FIRESTORE and os.getenv("GOOGLE_CLOUD_PROJECT"):
        _firestore_client = firestore.Client()
    return _firestore_client


def store_google_tokens(user_id: str, tokens: dict[str, Any]) -> None:
    """Store Google OAuth tokens for a user in Firestore."""
    db = _get_db()
    if db:
        db.collection("google_oauth_tokens").document(user_id).set(
            tokens, merge=True
        )
    else:
        # Fallback: in-memory (dev only)
        _in_memory_tokens[user_id] = tokens


def get_google_tokens(user_id: str) -> dict[str, Any] | None:
    """Get stored Google OAuth tokens for a user."""
    db = _get_db()
    if db:
        doc = db.collection("google_oauth_tokens").document(user_id).get()
        return doc.to_dict() if doc.exists else None
    return _in_memory_tokens.get(user_id)


def delete_google_tokens(user_id: str) -> None:
    """Delete stored Google OAuth tokens (disconnect)."""
    db = _get_db()
    if db:
        db.collection("google_oauth_tokens").document(user_id).delete()
    else:
        _in_memory_tokens.pop(user_id, None)


def is_google_connected(user_id: str) -> bool:
    """Check if a user has connected their Google account."""
    tokens = get_google_tokens(user_id)
    return bool(tokens and tokens.get("refresh_token"))


# ---------------------------------------------------------------------------
# OAuth state storage (short-lived, for CSRF protection)
# ---------------------------------------------------------------------------

_in_memory_tokens: dict[str, dict] = {}
_in_memory_states: dict[str, str] = {}


def _store_oauth_state(state: str, user_id: str) -> None:
    """Store OAuth state for callback validation."""
    db = _get_db()
    if db:
        db.collection("google_oauth_states").document(state).set(
            {
                "user_id": user_id,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
    else:
        _in_memory_states[state] = user_id


def _get_oauth_state(state: str) -> str | None:
    """Get user_id for an OAuth state token."""
    db = _get_db()
    if db:
        doc = db.collection("google_oauth_states").document(state).get()
        if doc.exists:
            return doc.to_dict().get("user_id")
        return None
    return _in_memory_states.get(state)


def _delete_oauth_state(state: str) -> None:
    """Clean up OAuth state after use."""
    db = _get_db()
    if db:
        db.collection("google_oauth_states").document(state).delete()
    else:
        _in_memory_states.pop(state, None)
