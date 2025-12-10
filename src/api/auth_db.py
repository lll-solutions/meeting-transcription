"""
Database Authentication Module

Handles user management and authentication using Firestore as the backend.
Implements:
- User model
- Password hashing (bcrypt)
- JWT token generation and verification
"""

import os
import time
import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

# Try to import Firestore
try:
    from google.cloud import firestore
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False

# Secret key for JWT signing
# In production, this should be loaded from a secret manager
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-key-change-me")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24 * 7  # 1 week

class User:
    """User model."""
    def __init__(
        self,
        email: str,
        name: str,
        password_hash: str = None,
        id: str = None,
        created_at: str = None,
        provider: str = "db",
        timezone: str = "America/New_York"
    ):
        self.id = id or email
        self.email = email
        self.name = name
        self.password_hash = password_hash
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.provider = provider
        self.timezone = timezone

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses (excludes sensitive data)."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "provider": self.provider,
            "timezone": self.timezone
        }
    
    def to_firestore(self) -> Dict[str, Any]:
        """Convert to dictionary for Firestore storage."""
        return {
            "email": self.email,
            "name": self.name,
            "password_hash": self.password_hash,
            "created_at": self.created_at,
            "provider": self.provider,
            "timezone": self.timezone
        }
    
    def __str__(self):
        return self.email


class AuthService:
    """Authentication service using Firestore."""
    
    def __init__(self):
        self.db = None
        if HAS_FIRESTORE and os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                self.db = firestore.Client()
                print("✅ AuthService connected to Firestore")
            except Exception as e:
                print(f"⚠️ AuthService could not connect to Firestore: {e}")
    
    def create_user(self, email: str, password: str, name: str) -> Tuple[Optional[User], str]:
        """
        Create a new user.
        
        Returns:
            (User, error_message)
        """
        if not self.db:
            return None, "Database not available"
        
        email = email.lower().strip()
        
        # Check if user exists
        doc_ref = self.db.collection("users").document(email)
        if doc_ref.get().exists:
            return None, "User already exists"
        
        # Hash password
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        # Create user object
        user = User(
            email=email,
            name=name,
            password_hash=password_hash
        )
        
        # Save to Firestore
        try:
            doc_ref.set(user.to_firestore())
            return user, ""
        except Exception as e:
            return None, f"Failed to create user: {str(e)}"

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.
        """
        if not self.db:
            return None
        
        email = email.lower().strip()
        
        # Get user
        doc_ref = self.db.collection("users").document(email)
        doc = doc_ref.get()
        
        if not doc.exists:
            return None
        
        data = doc.to_dict()
        stored_hash = data.get("password_hash")
        
        if not stored_hash:
            return None
            
        # Verify password
        if bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8')):
            return User(
                id=doc.id,
                email=data.get("email"),
                name=data.get("name"),
                password_hash=stored_hash,
                created_at=data.get("created_at"),
                timezone=data.get("timezone", "America/New_York")
            )

        return None

    def get_user(self, email: str) -> Optional[User]:
        """
        Get user by email.
        """
        if not self.db:
            return None

        email = email.lower().strip()

        doc_ref = self.db.collection("users").document(email)
        doc = doc_ref.get()

        if not doc.exists:
            return None

        data = doc.to_dict()
        return User(
            id=doc.id,
            email=data.get("email"),
            name=data.get("name"),
            password_hash=data.get("password_hash"),
            created_at=data.get("created_at"),
            timezone=data.get("timezone", "America/New_York"),
            provider=data.get("provider", "db")
        )

    def update_user(self, email: str, updates: Dict[str, Any]) -> Tuple[Optional[User], str]:
        """
        Update user fields.

        Args:
            email: User email
            updates: Dictionary of fields to update (e.g., {"timezone": "America/Los_Angeles"})

        Returns:
            (User, error_message)
        """
        if not self.db:
            return None, "Database not available"

        email = email.lower().strip()

        doc_ref = self.db.collection("users").document(email)
        doc = doc_ref.get()

        if not doc.exists:
            return None, "User not found"

        allowed_fields = {"timezone", "name"}
        filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields}

        if not filtered_updates:
            return None, "No valid fields to update"

        try:
            doc_ref.update(filtered_updates)
            return self.get_user(email), ""
        except Exception as e:
            return None, f"Failed to update user: {str(e)}"

    def create_token(self, user: User) -> str:
        """Generate a JWT token for the user."""
        payload = {
            "sub": user.email,
            "name": user.name,
            "email": user.email,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
        }
        
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    def verify_token(self, token: str) -> Optional[User]:
        """Verify a JWT token."""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            return User(
                id=payload.get("sub"),
                email=payload.get("email"),
                name=payload.get("name"),
                provider="db"
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception as e:
            print(f"Token verification error: {e}")
            return None

# Global instance
_auth_service = None

def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
