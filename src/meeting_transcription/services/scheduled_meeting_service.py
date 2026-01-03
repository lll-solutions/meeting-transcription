"""
Scheduled meeting service.

Handles business logic for scheduling bots to join meetings:
- Creating scheduled meetings with timezone conversion
- Listing and managing scheduled meetings
- Executing pending scheduled meetings via Cloud Scheduler
"""

from datetime import UTC, datetime
from typing import Any

from meeting_transcription.api.scheduled_meetings import ScheduledMeeting
from meeting_transcription.utils.url_validator import UrlValidator


class ScheduledMeetingService:
    """Service for managing scheduled meeting bots."""

    def __init__(
        self,
        storage: Any,
        meeting_service: Any,
        timezone_parser: Any,
        auth_service: Any | None = None,
    ) -> None:
        """
        Initialize the scheduled meeting service.

        Args:
            storage: Scheduled meeting storage instance
            meeting_service: MeetingService instance for joining meetings
            timezone_parser: Timezone utility for parsing user datetimes
            auth_service: Optional auth service for getting user timezone
        """
        self.storage = storage
        self.meeting_service = meeting_service
        self.timezone_parser = timezone_parser
        self.auth_service = auth_service

    def create_scheduled_meeting(
        self,
        meeting_url: str,
        scheduled_time_str: str,
        user: str,
        user_timezone: str,
        bot_name: str | None = None,
        instructor_name: str | None = None,
    ) -> tuple[ScheduledMeeting | None, str | None]:
        """
        Create a scheduled meeting.

        Args:
            meeting_url: Meeting URL to join
            scheduled_time_str: Scheduled time in user's timezone (ISO format)
            user: User ID creating the scheduled meeting
            user_timezone: User's timezone
            bot_name: Optional custom bot name
            instructor_name: Optional instructor name

        Returns:
            tuple: (ScheduledMeeting or None, error message or None)
        """
        # Validate meeting URL
        is_valid, error = UrlValidator.validate_meeting_url(meeting_url)
        if not is_valid:
            return None, error

        # Parse scheduled time (convert from user's timezone to UTC)
        scheduled_time_utc = self.timezone_parser.parse_user_datetime(
            scheduled_time_str, user_timezone
        )
        if not scheduled_time_utc:
            return None, "Invalid scheduled_time format. Use ISO format like '2024-12-10T15:30:00'"

        # Use default bot name if not provided
        if not bot_name:
            bot_name = "Meeting Assistant Bot"

        # Create scheduled meeting
        scheduled_meeting = ScheduledMeeting(
            meeting_url=meeting_url,
            scheduled_time=scheduled_time_utc,
            user=user,
            bot_name=bot_name,
            user_timezone=user_timezone,
            instructor_name=instructor_name,  # type: ignore[arg-type]
        )

        # Store in database
        created_meeting, error = self.storage.create(scheduled_meeting)

        return created_meeting, error

    def list_scheduled_meetings(
        self, user: str | None = None, status: str | None = None
    ) -> list[ScheduledMeeting]:
        """
        List scheduled meetings with optional filters.

        Args:
            user: Filter by user ID (None = all users)
            status: Filter by status (None = all statuses)

        Returns:
            List of ScheduledMeeting instances
        """
        return self.storage.list(user=user, status=status)  # type: ignore[no-any-return]

    def get_scheduled_meeting(self, meeting_id: str) -> ScheduledMeeting | None:
        """
        Get a scheduled meeting by ID.

        Args:
            meeting_id: Scheduled meeting ID

        Returns:
            ScheduledMeeting instance or None if not found
        """
        return self.storage.get(meeting_id)  # type: ignore[no-any-return]

    def delete_scheduled_meeting(
        self, meeting_id: str
    ) -> tuple[bool, str | None]:
        """
        Cancel/delete a scheduled meeting.

        Args:
            meeting_id: Scheduled meeting ID

        Returns:
            tuple: (success, error message or None)
        """
        return self.storage.delete(meeting_id)  # type: ignore[no-any-return]

    def execute_pending_meetings(
        self, before_time: datetime | None = None
    ) -> dict[str, Any]:
        """
        Execute all pending scheduled meetings.

        Finds meetings scheduled before the given time and joins them.

        Args:
            before_time: Execute meetings scheduled before this time (default: now)

        Returns:
            dict: Execution results with counts and details
        """
        if before_time is None:
            before_time = datetime.now(UTC)

        # Get pending meetings
        pending_meetings = self.storage.get_pending(before_time=before_time)

        if not pending_meetings:
            return {
                "message": "No pending meetings to execute",
                "checked_at": before_time.isoformat(),
                "executed": 0,
                "results": [],
            }

        print(
            f"⏰ Cloud Scheduler: Found {len(pending_meetings)} pending meeting(s) to execute"
        )

        results = []
        for scheduled_meeting in pending_meetings:
            result = self._execute_single_meeting(scheduled_meeting)
            results.append(result)

        return {
            "message": f"Executed {len(results)} scheduled meeting(s)",
            "checked_at": before_time.isoformat(),
            "executed": len(results),
            "results": results,
        }

    def _execute_single_meeting(
        self, scheduled_meeting: ScheduledMeeting
    ) -> dict[str, Any]:
        """
        Execute a single scheduled meeting.

        Args:
            scheduled_meeting: The scheduled meeting to execute

        Returns:
            dict: Execution result
        """
        try:
            print(f"🤖 Executing scheduled meeting: {scheduled_meeting.id}")
            print(f"   URL: {scheduled_meeting.meeting_url}")
            print(f"   Scheduled for: {scheduled_meeting.scheduled_time}")
            print(f"   User: {scheduled_meeting.user}")

            # Join the meeting using MeetingService
            meeting_id = self.meeting_service.join_meeting_for_scheduler(
                meeting_url=scheduled_meeting.meeting_url,
                user=scheduled_meeting.user,
                webhook_url="",  # Will be determined by MeetingService
                bot_name=scheduled_meeting.bot_name,
                instructor_name=scheduled_meeting.instructor_name,
            )

            if meeting_id:
                # Update as completed
                self.storage.update(
                    scheduled_meeting.id,
                    {"status": "completed", "actual_meeting_id": meeting_id},
                )
                print(f"✅ Successfully joined meeting: {meeting_id}")
                return {
                    "id": scheduled_meeting.id,
                    "status": "completed",
                    "meeting_id": meeting_id,
                }
            else:
                # Mark as failed
                self.storage.update(
                    scheduled_meeting.id,
                    {"status": "failed", "error": "Failed to create bot"},
                )
                print(f"❌ Failed to join scheduled meeting: {scheduled_meeting.id}")
                return {
                    "id": scheduled_meeting.id,
                    "status": "failed",
                    "error": "Failed to create bot",
                }

        except Exception as e:
            error_msg = str(e)
            print(
                f"❌ Error executing scheduled meeting {scheduled_meeting.id}: {error_msg}"
            )

            # Mark as failed
            try:
                self.storage.update(
                    scheduled_meeting.id, {"status": "failed", "error": error_msg}
                )
            except Exception as update_error:
                print(f"❌ Could not update meeting status: {update_error}")

            return {
                "id": scheduled_meeting.id,
                "status": "failed",
                "error": error_msg,
            }
