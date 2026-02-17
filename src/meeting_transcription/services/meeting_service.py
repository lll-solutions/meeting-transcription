"""
Meeting management service.

Handles business logic for meeting bot operations:
- Creating bots to join meetings
- Listing meetings
- Getting meeting details
- Removing bots from meetings
"""

import asyncio
from collections.abc import Coroutine
from typing import Any

from meeting_transcription.api.storage import MeetingStorage
from meeting_transcription.models.meeting import Meeting
from meeting_transcription.providers import TranscriptProvider, get_provider
from meeting_transcription.utils.url_validator import UrlValidator


class MeetingService:
    """Service for managing meeting bots and their lifecycle."""

    def __init__(
        self,
        storage: MeetingStorage,
        provider: TranscriptProvider | None = None
    ) -> None:
        """
        Initialize the meeting service.

        Args:
            storage: Meeting storage instance for persistence
            provider: Transcript provider instance (defaults to env-configured provider)
        """
        self.storage = storage
        self._provider = provider

    @property
    def provider(self) -> TranscriptProvider:
        """Get the transcript provider (lazy initialization)."""
        if self._provider is None:
            self._provider = get_provider()
        return self._provider

    @staticmethod
    def _run_async(coro: Coroutine) -> Any:
        """Run an async coroutine synchronously (Python 3.12+ safe)."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # Already in an async context — create a task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        else:
            return asyncio.run(coro)

    def create_meeting(
        self,
        meeting_url: str,
        user: str,
        webhook_url: str,
        bot_name: str | None = None,
        instructor_name: str | None = None,
    ) -> Meeting:
        """
        Create a bot to join a meeting.

        Args:
            meeting_url: The meeting URL to join
            user: User ID creating the meeting
            webhook_url: Webhook URL for bot events
            bot_name: Optional custom bot name
            instructor_name: Optional instructor name for the meeting

        Returns:
            Meeting instance with bot details

        Raises:
            ValueError: If meeting_url is invalid or required fields missing
            RuntimeError: If bot creation fails
        """
        # Validate meeting URL
        is_valid, error = UrlValidator.validate_meeting_url(meeting_url)
        if not is_valid:
            raise ValueError(error)

        # Use default bot name if not provided
        if not bot_name:
            bot_name = "Meeting Assistant Bot"

        # Create meeting via provider (async -> sync bridge)
        meeting_id = self._run_async(
            self.provider.create_meeting(
                meeting_url,
                webhook_url=webhook_url,
                bot_name=bot_name,
            )
        )

        if not meeting_id:
            raise RuntimeError(f"Failed to create meeting - {self.provider.name} returned no data")

        # Store meeting in persistent storage
        meeting_dict = self.storage.create_meeting(
            meeting_id=meeting_id,
            user=user,
            meeting_url=meeting_url,
            bot_name=bot_name,
            instructor_name=instructor_name,
        )

        # Store provider type for later reference
        self.storage.update_meeting(meeting_id, {
            "provider": self.provider.provider_type.value
        })

        return Meeting.from_dict(meeting_dict)

    def list_meetings(self, user: str | None = None) -> list[Meeting]:
        """
        List meetings with optional user filter.

        Args:
            user: Filter by user ID (None = all meetings)

        Returns:
            List of Meeting instances
        """
        meetings_data = self.storage.list_meetings(user=user)
        return [Meeting.from_dict(m) for m in meetings_data]

    def get_meeting(self, meeting_id: str) -> Meeting | None:
        """
        Get meeting details by ID.

        Tries storage first, falls back to provider API if not found.

        Args:
            meeting_id: The meeting/bot ID

        Returns:
            Meeting instance, or None if not found
        """
        # Try storage first
        meeting_dict = self.storage.get_meeting(meeting_id)

        if meeting_dict:
            return Meeting.from_dict(meeting_dict)

        # Fallback to provider API for status
        try:
            status = self._run_async(self.provider.get_status(meeting_id))
            if status and status != "error":
                return Meeting.from_dict({
                    "id": meeting_id,
                    "status": status,
                    "user": "",
                    "meeting_url": "",
                    "bot_name": "",
                    "created_at": "",
                })
        except Exception:
            pass

        return None

    def delete_meeting(self, meeting_id: str) -> bool:
        """
        Remove bot from meeting.

        Args:
            meeting_id: The meeting/bot ID to remove

        Returns:
            True if successful, False otherwise
        """
        # Leave meeting via provider
        success = self._run_async(self.provider.leave_meeting(meeting_id))

        if success:
            # Update status in storage
            self.storage.update_meeting(meeting_id, {"status": "leaving"})

        return success

    def leave_meeting(self, meeting_id: str) -> bool:
        """
        Alias for delete_meeting for backward compatibility.

        Args:
            meeting_id: The meeting/bot ID to remove

        Returns:
            True if successful, False otherwise
        """
        return self.delete_meeting(meeting_id)

    def join_meeting_for_scheduler(
        self,
        meeting_url: str,
        user: str,
        webhook_url: str,
        bot_name: str | None = None,
        instructor_name: str | None = None,
    ) -> str | None:
        """
        Join a meeting for scheduled meeting execution.

        This is a helper method used by the scheduler service.
        Returns meeting_id on success, None on failure.

        Args:
            meeting_url: The meeting URL to join
            user: User ID scheduling the meeting
            webhook_url: Webhook URL for bot events
            bot_name: Optional custom bot name
            instructor_name: Optional instructor name

        Returns:
            Meeting ID if successful, None otherwise
        """
        try:
            meeting = self.create_meeting(
                meeting_url=meeting_url,
                user=user,
                webhook_url=webhook_url,
                bot_name=bot_name,
                instructor_name=instructor_name,
            )
            return meeting.id
        except (ValueError, RuntimeError) as e:
            print(f"Error joining meeting for scheduler: {e}")
            return None
