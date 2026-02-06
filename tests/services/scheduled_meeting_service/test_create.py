"""
Tests for ScheduledMeetingService creation operations.

Test coverage:
- Creating scheduled meetings with valid inputs
- URL validation
- Timezone conversion
- Error handling
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from meeting_transcription.api.scheduled_meetings import ScheduledMeeting
from meeting_transcription.services.scheduled_meeting_service import ScheduledMeetingService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock scheduled meeting storage."""
    return MagicMock()


@pytest.fixture
def mock_meeting_service() -> MagicMock:
    """Mock MeetingService."""
    return MagicMock()


@pytest.fixture
def mock_timezone_parser() -> MagicMock:
    """Mock timezone parser."""
    return MagicMock()


@pytest.fixture
def service(
    mock_storage: MagicMock,
    mock_meeting_service: MagicMock,
    mock_timezone_parser: MagicMock,
) -> ScheduledMeetingService:
    """ScheduledMeetingService instance with mocked dependencies."""
    return ScheduledMeetingService(
        storage=mock_storage,
        meeting_service=mock_meeting_service,
        timezone_parser=mock_timezone_parser,
    )


class TestCreateScheduledMeeting:
    """Tests for create_scheduled_meeting method."""

    def test_create_scheduled_meeting_success(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_timezone_parser: MagicMock,
    ) -> None:
        """Successfully create a scheduled meeting."""
        # Arrange
        scheduled_time_utc = datetime(2024, 12, 15, 20, 30)  # UTC
        mock_timezone_parser.parse_user_datetime.return_value = scheduled_time_utc

        created_meeting = ScheduledMeeting(
            id="sched-123",
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time=scheduled_time_utc,
            user="user@example.com",
            bot_name="Test Bot",
            user_timezone="America/New_York",
        )
        mock_storage.create.return_value = (created_meeting, None)

        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time_str="2024-12-15T15:30:00",
            user="user@example.com",
            user_timezone="America/New_York",
            bot_name="Test Bot",
        )

        # Assert
        assert meeting is not None
        assert error is None
        assert meeting.id == "sched-123"
        assert meeting.meeting_url == "https://zoom.us/j/123456789"

        mock_timezone_parser.parse_user_datetime.assert_called_once_with(
            "2024-12-15T15:30:00", "America/New_York"
        )
        mock_storage.create.assert_called_once()

    def test_create_scheduled_meeting_with_default_bot_name(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_timezone_parser: MagicMock,
    ) -> None:
        """Use default bot name when none provided."""
        # Arrange
        scheduled_time_utc = datetime(2024, 12, 15, 20, 30)
        mock_timezone_parser.parse_user_datetime.return_value = scheduled_time_utc

        created_meeting = ScheduledMeeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time=scheduled_time_utc,
            user="user@example.com",
            bot_name="Meeting Assistant Bot",
            user_timezone="America/New_York",
        )
        mock_storage.create.return_value = (created_meeting, None)

        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time_str="2024-12-15T15:30:00",
            user="user@example.com",
            user_timezone="America/New_York",
        )

        # Assert
        assert meeting is not None
        assert meeting.bot_name == "Meeting Assistant Bot"

    def test_create_scheduled_meeting_invalid_url(
        self, service: ScheduledMeetingService
    ) -> None:
        """Reject invalid meeting URL."""
        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="https://evil.com/fake",
            scheduled_time_str="2024-12-15T15:30:00",
            user="user@example.com",
            user_timezone="America/New_York",
        )

        # Assert
        assert meeting is None
        assert error is not None
        assert "not supported" in error

    def test_create_scheduled_meeting_empty_url(
        self, service: ScheduledMeetingService
    ) -> None:
        """Reject empty meeting URL."""
        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="",
            scheduled_time_str="2024-12-15T15:30:00",
            user="user@example.com",
            user_timezone="America/New_York",
        )

        # Assert
        assert meeting is None
        assert error is not None
        assert "required" in error

    def test_create_scheduled_meeting_invalid_time_format(
        self,
        service: ScheduledMeetingService,
        mock_timezone_parser: MagicMock,
    ) -> None:
        """Reject invalid time format."""
        # Arrange
        mock_timezone_parser.parse_user_datetime.return_value = None

        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time_str="invalid-time",
            user="user@example.com",
            user_timezone="America/New_York",
        )

        # Assert
        assert meeting is None
        assert error is not None
        assert "Invalid scheduled_time format" in error

    def test_create_scheduled_meeting_with_instructor_name(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_timezone_parser: MagicMock,
    ) -> None:
        """Create scheduled meeting with instructor name."""
        # Arrange
        scheduled_time_utc = datetime(2024, 12, 15, 20, 30)
        mock_timezone_parser.parse_user_datetime.return_value = scheduled_time_utc

        created_meeting = ScheduledMeeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time=scheduled_time_utc,
            user="user@example.com",
            bot_name="Test Bot",
            user_timezone="America/New_York",
            instructor_name="Dr. Smith",
        )
        mock_storage.create.return_value = (created_meeting, None)

        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time_str="2024-12-15T15:30:00",
            user="user@example.com",
            user_timezone="America/New_York",
            bot_name="Test Bot",
            instructor_name="Dr. Smith",
        )

        # Assert
        assert meeting is not None
        assert meeting.instructor_name == "Dr. Smith"

    def test_create_scheduled_meeting_storage_error(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_timezone_parser: MagicMock,
    ) -> None:
        """Handle storage error during creation."""
        # Arrange
        scheduled_time_utc = datetime(2024, 12, 15, 20, 30)
        mock_timezone_parser.parse_user_datetime.return_value = scheduled_time_utc
        mock_storage.create.return_value = (None, "Database error")

        # Act
        meeting, error = service.create_scheduled_meeting(
            meeting_url="https://zoom.us/j/123456789",
            scheduled_time_str="2024-12-15T15:30:00",
            user="user@example.com",
            user_timezone="America/New_York",
        )

        # Assert
        assert meeting is None
        assert error == "Database error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
