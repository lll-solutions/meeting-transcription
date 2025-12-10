"""
Scheduled meetings storage and management.

Handles scheduling bots to join meetings at a specific time.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from zoneinfo import ZoneInfo

try:
    from google.cloud import firestore
    HAS_FIRESTORE = True
except ImportError:
    HAS_FIRESTORE = False


class ScheduledMeeting:
    """Model for a scheduled meeting."""

    def __init__(
        self,
        meeting_url: str,
        scheduled_time: datetime,
        user: str,
        bot_name: str = "Meeting Assistant",
        user_timezone: str = "America/New_York",
        id: str = None,
        status: str = "scheduled",
        created_at: datetime = None,
        actual_meeting_id: str = None,
        error: str = None
    ):
        self.id = id or str(uuid.uuid4())
        self.user = user
        self.meeting_url = meeting_url
        self.bot_name = bot_name
        self.scheduled_time = scheduled_time  # Always UTC
        self.user_timezone = user_timezone
        self.status = status  # scheduled, completed, failed, cancelled
        self.created_at = created_at or datetime.now(ZoneInfo("UTC"))
        self.actual_meeting_id = actual_meeting_id
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "user": self.user,
            "meeting_url": self.meeting_url,
            "bot_name": self.bot_name,
            "scheduled_time": self.scheduled_time.isoformat(),
            "user_timezone": self.user_timezone,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "actual_meeting_id": self.actual_meeting_id,
            "error": self.error
        }

    def to_firestore(self) -> Dict[str, Any]:
        """Convert to dictionary for Firestore storage."""
        return {
            "user": self.user,
            "meeting_url": self.meeting_url,
            "bot_name": self.bot_name,
            "scheduled_time": self.scheduled_time,
            "user_timezone": self.user_timezone,
            "status": self.status,
            "created_at": self.created_at,
            "actual_meeting_id": self.actual_meeting_id,
            "error": self.error
        }

    @staticmethod
    def from_firestore(doc_id: str, data: Dict[str, Any]) -> 'ScheduledMeeting':
        """Create from Firestore document."""
        scheduled_time = data.get("scheduled_time")
        if isinstance(scheduled_time, str):
            scheduled_time = datetime.fromisoformat(scheduled_time)

        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)

        return ScheduledMeeting(
            id=doc_id,
            user=data.get("user"),
            meeting_url=data.get("meeting_url"),
            bot_name=data.get("bot_name", "Meeting Assistant"),
            scheduled_time=scheduled_time,
            user_timezone=data.get("user_timezone", "America/New_York"),
            status=data.get("status", "scheduled"),
            created_at=created_at,
            actual_meeting_id=data.get("actual_meeting_id"),
            error=data.get("error")
        )


class ScheduledMeetingStorage:
    """Handles persistence for scheduled meetings."""

    def __init__(self):
        """Initialize storage."""
        self.db = None
        if HAS_FIRESTORE and os.getenv("GOOGLE_CLOUD_PROJECT"):
            try:
                self.db = firestore.Client()
                print("✅ ScheduledMeetingStorage connected to Firestore")
            except Exception as e:
                print(f"⚠️ ScheduledMeetingStorage could not connect to Firestore: {e}")

    def create(self, meeting: ScheduledMeeting) -> Tuple[Optional[ScheduledMeeting], str]:
        """
        Create a scheduled meeting.

        Returns:
            (ScheduledMeeting, error_message)
        """
        if not self.db:
            return None, "Database not available"

        try:
            doc_ref = self.db.collection("scheduled_meetings").document(meeting.id)
            doc_ref.set(meeting.to_firestore())
            return meeting, ""
        except Exception as e:
            return None, f"Failed to create scheduled meeting: {str(e)}"

    def get(self, meeting_id: str) -> Optional[ScheduledMeeting]:
        """Get a scheduled meeting by ID."""
        if not self.db:
            return None

        try:
            doc_ref = self.db.collection("scheduled_meetings").document(meeting_id)
            doc = doc_ref.get()

            if not doc.exists:
                return None

            return ScheduledMeeting.from_firestore(doc.id, doc.to_dict())
        except Exception as e:
            print(f"Error getting scheduled meeting: {e}")
            return None

    def list(self, user: str = None, status: str = None) -> List[ScheduledMeeting]:
        """
        List scheduled meetings.

        Args:
            user: Filter by user email (None = all users)
            status: Filter by status (None = all statuses)

        Returns:
            List of scheduled meetings
        """
        if not self.db:
            return []

        try:
            query = self.db.collection("scheduled_meetings")

            if user:
                query = query.where("user", "==", user)

            if status:
                query = query.where("status", "==", status)

            query = query.order_by("scheduled_time", direction=firestore.Query.DESCENDING)

            docs = query.stream()
            return [ScheduledMeeting.from_firestore(doc.id, doc.to_dict()) for doc in docs]
        except Exception as e:
            print(f"Error listing scheduled meetings: {e}")
            return []

    def get_pending(self, before_time: datetime = None) -> List[ScheduledMeeting]:
        """
        Get scheduled meetings that are ready to be executed.

        Args:
            before_time: Get meetings scheduled before this time (default: now)

        Returns:
            List of scheduled meetings with status='scheduled' and scheduled_time <= before_time
        """
        if not self.db:
            return []

        if before_time is None:
            before_time = datetime.now(ZoneInfo("UTC"))

        try:
            query = self.db.collection("scheduled_meetings") \
                .where("status", "==", "scheduled") \
                .where("scheduled_time", "<=", before_time) \
                .order_by("scheduled_time")

            docs = query.stream()
            return [ScheduledMeeting.from_firestore(doc.id, doc.to_dict()) for doc in docs]
        except Exception as e:
            print(f"Error getting pending scheduled meetings: {e}")
            return []

    def update(self, meeting_id: str, updates: Dict[str, Any]) -> Tuple[Optional[ScheduledMeeting], str]:
        """
        Update a scheduled meeting.

        Args:
            meeting_id: Meeting ID
            updates: Dictionary of fields to update

        Returns:
            (ScheduledMeeting, error_message)
        """
        if not self.db:
            return None, "Database not available"

        try:
            doc_ref = self.db.collection("scheduled_meetings").document(meeting_id)
            doc = doc_ref.get()

            if not doc.exists:
                return None, "Scheduled meeting not found"

            doc_ref.update(updates)
            return self.get(meeting_id), ""
        except Exception as e:
            return None, f"Failed to update scheduled meeting: {str(e)}"

    def delete(self, meeting_id: str) -> Tuple[bool, str]:
        """
        Delete (cancel) a scheduled meeting.

        Returns:
            (success, error_message)
        """
        if not self.db:
            return False, "Database not available"

        try:
            doc_ref = self.db.collection("scheduled_meetings").document(meeting_id)
            doc = doc_ref.get()

            if not doc.exists:
                return False, "Scheduled meeting not found"

            doc_ref.delete()
            return True, ""
        except Exception as e:
            return False, f"Failed to delete scheduled meeting: {str(e)}"


# Global instance
_scheduled_meeting_storage = None


def get_scheduled_meeting_storage() -> ScheduledMeetingStorage:
    """Get or create the global ScheduledMeetingStorage instance."""
    global _scheduled_meeting_storage
    if _scheduled_meeting_storage is None:
        _scheduled_meeting_storage = ScheduledMeetingStorage()
    return _scheduled_meeting_storage
