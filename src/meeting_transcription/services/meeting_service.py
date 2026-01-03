"""
Meeting management service.

Handles business logic for meeting bot operations:
- Creating bots to join meetings
- Listing meetings
- Getting meeting details
- Removing bots from meetings
"""


from meeting_transcription.api.recall import create_bot, get_bot_status, leave_meeting
from meeting_transcription.api.storage import MeetingStorage
from meeting_transcription.models.meeting import Meeting
from meeting_transcription.utils.url_validator import UrlValidator


class MeetingService:
    """Service for managing meeting bots and their lifecycle."""

    def __init__(self, storage: MeetingStorage) -> None:
        """
        Initialize the meeting service.

        Args:
            storage: Meeting storage instance for persistence
        """
        self.storage = storage

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

        # Create bot via Recall API
        bot_data = create_bot(meeting_url, webhook_url, bot_name)

        if not bot_data:
            raise RuntimeError("Failed to create bot - Recall API returned no data")

        # Store meeting in persistent storage
        meeting_id = bot_data["id"]
        meeting_dict = self.storage.create_meeting(
            meeting_id=meeting_id,
            user=user,
            meeting_url=meeting_url,
            bot_name=bot_name,
            instructor_name=instructor_name,
        )

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

        Tries storage first, falls back to Recall API if not found.

        Args:
            meeting_id: The meeting/bot ID

        Returns:
            Meeting instance, or None if not found
        """
        # Try storage first
        meeting_dict = self.storage.get_meeting(meeting_id)

        if meeting_dict:
            return Meeting.from_dict(meeting_dict)

        # Fallback to Recall API
        bot_status = get_bot_status(meeting_id)
        if bot_status:
            return Meeting.from_dict(bot_status)

        return None

    def delete_meeting(self, meeting_id: str) -> bool:
        """
        Remove bot from meeting.

        Args:
            meeting_id: The meeting/bot ID to remove

        Returns:
            True if successful, False otherwise
        """
        success = leave_meeting(meeting_id)

        if success:
            # Update status in storage
            self.storage.update_meeting(meeting_id, {"status": "leaving"})

        return success

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
