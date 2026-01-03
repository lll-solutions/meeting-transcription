"""
Authentication module for the Meeting Transcription API.

Supports:
- Firebase Auth - Primary auth method (Google Sign-In)
- API Key - For advanced users / programmatic access (configure via .env)
- Webhook Signature - For Recall.ai webhooks
"""

import os
import hmac
import hashlib
import functools
from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
from flask import request, g, jsonify

from meeting_transcription.api import auth_db

# Try to import Firebase Admin
try:
    import firebase_admin
    from firebase_admin import auth as firebase_auth
    from firebase_admin import credentials
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False


class User:
    """Authenticated user information."""
    
    def __init__(
        self,
        id: str,
        email: Optional[str] = None,
        name: Optional[str] = None,
        picture: Optional[str] = None,
        provider: str = "unknown"
    ):
        self.id = id
        self.email = email
        self.name = name
        self.picture = picture
        self.provider = provider
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "provider": self.provider
        }
    
    def __str__(self) -> str:
        return self.email or self.id


class AuthProvider(ABC):
    """
    Base class for authentication providers.
    
    This abstraction allows swapping auth providers without changing application code.
    """
    
    @abstractmethod
    def verify_token(self, token: str) -> Optional[User]:
        """
        Verify an authentication token.
        
        Args:
            token: The token to verify (usually from Authorization header)
        
        Returns:
            User object if valid, None otherwise
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name for logging/debugging."""
        pass


class DBAuthProvider(AuthProvider):
    """Database Authentication provider (Firestore + JWT)."""
    
    def __init__(self):
        self.service = auth_db.get_auth_service()
    
    @property
    def name(self) -> str:
        return "db"
    
    def verify_token(self, token: str) -> Optional[User]:
        """Verify a JWT token."""
        db_user = self.service.verify_token(token)
        if db_user:
            return User(
                id=db_user.id,
                email=db_user.email,
                name=db_user.name,
                provider="db"
            )
        return None


class FirebaseAuthProvider(AuthProvider):
    """Firebase Authentication provider."""
    
    def __init__(self, project_id: str = None):
        self.project_id = project_id or os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        self._initialized = False
        self._init_firebase()
    
    def _init_firebase(self):
        """Initialize Firebase Admin SDK."""
        if not HAS_FIREBASE:
            print("⚠️ firebase-admin not installed - Firebase Auth disabled")
            return
        
        if self._initialized:
            return
        
        try:
            # Check if already initialized
            firebase_admin.get_app()
            self._initialized = True
        except ValueError:
            # Not initialized, do it now
            try:
                # Use default credentials (works on GCP, or with GOOGLE_APPLICATION_CREDENTIALS)
                firebase_admin.initialize_app()
                self._initialized = True
                print(f"✅ Firebase Auth initialized (project: {self.project_id})")
            except Exception as e:
                print(f"⚠️ Could not initialize Firebase Auth: {e}")
    
    @property
    def name(self) -> str:
        return "firebase"
    
    def verify_token(self, token: str) -> Optional[User]:
        """Verify a Firebase ID token."""
        if not HAS_FIREBASE or not self._initialized:
            return None
        
        try:
            decoded = firebase_auth.verify_id_token(token)
            
            return User(
                id=decoded.get("uid"),
                email=decoded.get("email"),
                name=decoded.get("name"),
                picture=decoded.get("picture"),
                provider="firebase"
            )
        except firebase_auth.InvalidIdTokenError:
            return None
        except firebase_auth.ExpiredIdTokenError:
            return None
        except Exception as e:
            print(f"⚠️ Firebase token verification error: {e}")
            return None


class APIKeyProvider(AuthProvider):
    """API Key authentication provider for programmatic access."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("API_KEY", "")
    
    @property
    def name(self) -> str:
        return "api_key"
    
    def verify_token(self, token: str) -> Optional[User]:
        """Verify an API key."""
        if not self.api_key:
            return None
        
        if hmac.compare_digest(token, self.api_key):
            # Get user info from headers if available (trusted because API key is valid)
            user_name = request.headers.get("X-User-Name", "API User")
            user_email = request.headers.get("X-User-Email")
            
            return User(
                id=user_email or "api-user",
                email=user_email,
                name=user_name,
                provider="api_key"
            )
        
        return None


class AuthConfig:
    """Authentication configuration."""
    
    def __init__(self):
        # Primary auth provider
        self.auth_provider = os.getenv("AUTH_PROVIDER", "db")
        
        # Firebase settings
        self.firebase_project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
        
        # API Key (advanced users)
        self.api_key = os.getenv("API_KEY", "")
        
        # Webhook verification
        self.recall_webhook_secret = os.getenv("RECALL_WEBHOOK_SECRET", "")
        
        # Public endpoints (no auth required)
        self.public_endpoints = [
            "/",
            "/health",
            "/api/config",
            "/webhook/recall",
            "/api/auth/login",  # New login endpoint
            "/api/auth/setup",  # New setup endpoint
            "/api/scheduled-meetings/execute"  # Cloud Scheduler endpoint
        ]
        
        # Development mode
        self.allow_anonymous = os.getenv("AUTH_ALLOW_ANONYMOUS", "false").lower() == "true"


# Global instances
_config: Optional[AuthConfig] = None
_providers: Dict[str, AuthProvider] = {}


def init_auth(app=None) -> AuthConfig:
    """
    Initialize authentication.
    
    Call this at application startup.
    """
    global _config, _providers
    
    _config = AuthConfig()
    
    # Initialize providers based on config
    if _config.auth_provider == "db":
        _providers["db"] = DBAuthProvider()
        
    elif _config.auth_provider == "firebase":
        if HAS_FIREBASE:
            _providers["firebase"] = FirebaseAuthProvider(_config.firebase_project_id)
        else:
            print("⚠️ Firebase Auth requested but firebase-admin not installed")
    
    # API Key is always available if configured
    if _config.api_key:
        _providers["api_key"] = APIKeyProvider(_config.api_key)
    
    # Report configuration
    provider_names = list(_providers.keys())
    if _config.allow_anonymous:
        provider_names.append("anonymous")
    
    print(f"🔐 Auth providers: {', '.join(provider_names) or 'None'}")
    if _config.recall_webhook_secret:
        print(f"🔐 Webhook verification: enabled")
    
    return _config


def get_config() -> AuthConfig:
    """Get auth config, initializing if needed."""
    global _config
    if _config is None:
        _config = init_auth()
    return _config


def authenticate_request() -> Tuple[Optional[User], Optional[str]]:
    """
    Authenticate the current request using available providers.

    Checks (in order):
    1. httpOnly cookie (most secure)
    2. Authorization header (for API clients)
    3. API key header/query param

    Returns:
        tuple: (User, provider_name) or (None, None) if not authenticated
    """
    config = get_config()

    # Get token from httpOnly cookie (preferred - XSS protection)
    token = request.cookies.get("auth_token")

    # Fallback to Authorization header (for API clients, backward compatibility)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]

    # Try DB Auth (if configured)
    if token and "db" in _providers:
        user = _providers["db"].verify_token(token)
        if user:
            return user, "db"

    # Try Firebase Auth (if configured)
    if token and "firebase" in _providers:
        user = _providers["firebase"].verify_token(token)
        if user:
            return user, "firebase"

    # Try API Key
    api_key = request.headers.get("X-API-Key") or request.args.get("api_key")
    if api_key and "api_key" in _providers:
        user = _providers["api_key"].verify_token(api_key)
        if user:
            return user, "api_key"

    return None, None


def get_current_user() -> str:
    """
    Get the current authenticated user identifier.
    
    Returns:
        str: User email/id or 'anonymous'
    """
    user, _ = authenticate_request()
    
    if user:
        return str(user)
    
    config = get_config()
    if config.allow_anonymous:
        return "anonymous"
    
    return "anonymous"


def require_auth(f):
    """
    Decorator to require authentication on a route.
    
    Usage:
        @app.route('/api/meetings')
        @require_auth
        def list_meetings():
            user = g.user  # User email/id string
            user_info = g.user_info  # Full User object
            ...
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        config = get_config()
        
        # Check if this is a public endpoint
        if request.path in config.public_endpoints:
            g.user = get_current_user()
            g.user_info = None
            return f(*args, **kwargs)
        
        user, provider = authenticate_request()
        
        if user:
            g.user = str(user)
            g.user_info = user
            g.auth_provider = provider
            return f(*args, **kwargs)
        
        if config.allow_anonymous:
            g.user = "anonymous"
            g.user_info = None
            g.auth_provider = None
            return f(*args, **kwargs)
        
        return jsonify({
            "error": "Authentication required",
            "message": "Please sign in to access this resource."
        }), 401
    
    return decorated


def require_auth_optional(f):
    """
    Decorator that attempts authentication but allows anonymous access.
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        user, provider = authenticate_request()
        
        g.user = str(user) if user else "anonymous"
        g.user_info = user
        g.auth_provider = provider
        return f(*args, **kwargs)
    
    return decorated


def verify_recall_webhook_signature(payload: bytes, headers: dict) -> bool:
    """
    Verify Recall.ai webhook signature using Svix.

    Recall.ai uses Svix for webhook delivery, which requires specific
    signature verification with multiple headers (id, timestamp, signature).

    Args:
        payload: Raw request body
        headers: Request headers (must include svix-id, svix-timestamp, svix-signature)

    Returns:
        bool: True if signature is valid
    """
    config = get_config()

    if not config.recall_webhook_secret:
        return True  # No secret configured, skip verification

    try:
        from svix.webhooks import Webhook

        # Svix requires these three headers
        svix_id = headers.get('svix-id') or headers.get('Svix-Id')
        svix_timestamp = headers.get('svix-timestamp') or headers.get('Svix-Timestamp')
        svix_signature = headers.get('svix-signature') or headers.get('Svix-Signature')

        if not all([svix_id, svix_timestamp, svix_signature]):
            print(f"⚠️ Missing Svix headers: id={bool(svix_id)}, ts={bool(svix_timestamp)}, sig={bool(svix_signature)}")
            return False

        # Create Svix webhook verifier
        wh = Webhook(config.recall_webhook_secret)

        # Verify signature
        wh.verify(payload, {
            'svix-id': svix_id,
            'svix-timestamp': svix_timestamp,
            'svix-signature': svix_signature
        })

        return True
    except Exception as e:
        print(f"❌ Webhook signature verification failed: {e}")
        return False


def verify_webhook(f):
    """
    Decorator to verify Recall.ai webhook signatures.

    In production, webhook signature verification is REQUIRED.
    Uses Svix signature verification (Recall.ai's webhook provider).
    """
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        config = get_config()
        is_development = os.getenv("ENV", "").lower() == "development"

        if not config.recall_webhook_secret:
            if not is_development:
                # In production (default), require webhook verification
                print("❌ RECALL_WEBHOOK_SECRET not set - rejecting webhook in production")
                return jsonify({"error": "Webhook verification not configured"}), 500
            else:
                # In development, allow but warn
                print("⚠️ RECALL_WEBHOOK_SECRET not set - skipping verification (dev mode)")
                g.user = "webhook"
                return f(*args, **kwargs)

        # Get raw payload and headers for Svix verification
        payload = request.get_data()
        headers = dict(request.headers)

        # Verify using Svix format
        if not verify_recall_webhook_signature(payload, headers):
            print("❌ Invalid webhook signature")
            return jsonify({"error": "Invalid webhook signature"}), 401

        g.user = "webhook"
        return f(*args, **kwargs)

    return decorated


def verify_oidc_token(token: str, expected_audience: str) -> bool:
    """Verify OIDC token from Google Cloud Tasks matches our service account."""
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        request_adapter = google_requests.Request()
        claims = id_token.verify_oauth2_token(token, request_adapter, audience=expected_audience)

        if claims.get('iss') not in ['https://accounts.google.com', 'accounts.google.com']:
            print(f"❌ Invalid token issuer: {claims.get('iss')}")
            return False

        email = claims.get('email', '')
        if not email.endswith('.gserviceaccount.com'):
            print(f"❌ Token not from service account: {email}")
            return False

        # Verify it's OUR project's service account (not any random Google SA)
        project_number = os.getenv("GCP_PROJECT_NUMBER")
        if project_number:
            expected_email = f"{project_number}-compute@developer.gserviceaccount.com"
            if email != expected_email:
                print(f"❌ Token from wrong service account")
                print(f"   Expected: {expected_email}")
                print(f"   Got: {email}")
                return False

        print(f"✅ Valid OIDC token from: {email}")
        return True

    except ValueError as e:
        print(f"❌ Token verification failed: {e}")
        return False
    except Exception as e:
        print(f"❌ OIDC verification error: {e}")
        return False


def verify_cloud_tasks(f):
    """Verify requests come from Google Cloud Tasks via OIDC token."""
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        is_development = os.getenv("ENV", "").lower() == "development"
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            if not is_development:
                print("❌ Missing Cloud Tasks OIDC token - rejecting")
                return jsonify({"error": "Unauthorized - missing OIDC token"}), 401
            print("⚠️ Missing Cloud Tasks OIDC token - allowing in dev mode")
            g.user = "cloud-tasks"
            return f(*args, **kwargs)

        token = auth_header[7:]
        service_url = os.getenv("SERVICE_URL") or f"{request.scheme}://{request.host}"

        if not verify_oidc_token(token, service_url):
            if not is_development:
                print("❌ Invalid Cloud Tasks OIDC token - rejecting")
                return jsonify({"error": "Unauthorized - invalid OIDC token"}), 401
            print("⚠️ Invalid OIDC token - allowing in dev mode")

        task_name = request.headers.get("X-CloudTasks-TaskName")
        g.user = "cloud-tasks"
        print(f"✅ Cloud Tasks request verified: {task_name or 'unknown task'}")
        return f(*args, **kwargs)

    return decorated
