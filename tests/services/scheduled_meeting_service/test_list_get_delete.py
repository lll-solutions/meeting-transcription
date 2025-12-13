"""
Tests for ScheduledMeetingService list/get/delete operations.

Test coverage:
- Listing scheduled meetings with filters
- Getting individual scheduled meetings
- Deleting/canceling scheduled meetings
"""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from src.api.scheduled_meetings import ScheduledMeeting
from src.services.scheduled_meeting_service import ScheduledMeetingService


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


@pytest.fixture
def sample_scheduled_meeting() -> ScheduledMeeting:
    """Sample scheduled meeting."""
    return ScheduledMeeting(
        id="sched-123",
        meeting_url="https://zoom.us/j/123456789",
        scheduled_time=datetime(2024, 12, 15, 20, 30),
        user="user@example.com",
        bot_name="Test Bot",
        user_timezone="America/New_York",
    )


class TestListScheduledMeetings:
    """Tests for list_scheduled_meetings method."""

    def test_list_all_meetings(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """List all scheduled meetings."""
        # Arrange
        meeting2 = ScheduledMeeting(
            id="sched-456",
            meeting_url="https://meet.google.com/abc-defg-hij",
            scheduled_time=datetime(2024, 12, 16, 15, 0),
            user="user2@example.com",
            bot_name="Bot 2",
            user_timezone="America/Los_Angeles",
        )
        mock_storage.list.return_value = [sample_scheduled_meeting, meeting2]

        # Act
        meetings = service.list_scheduled_meetings()

        # Assert
        assert len(meetings) == 2
        assert meetings[0].id == "sched-123"
        assert meetings[1].id == "sched-456"
        mock_storage.list.assert_called_once_with(user=None, status=None)

    def test_list_meetings_filtered_by_user(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """List meetings filtered by user."""
        # Arrange
        mock_storage.list.return_value = [sample_scheduled_meeting]

        # Act
        meetings = service.list_scheduled_meetings(user="user@example.com")

        # Assert
        assert len(meetings) == 1
        assert meetings[0].user == "user@example.com"
        mock_storage.list.assert_called_once_with(
            user="user@example.com", status=None
        )

    def test_list_meetings_filtered_by_status(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """List meetings filtered by status."""
        # Arrange
        mock_storage.list.return_value = [sample_scheduled_meeting]

        # Act
        meetings = service.list_scheduled_meetings(status="scheduled")

        # Assert
        assert len(meetings) == 1
        assert meetings[0].status == "scheduled"
        mock_storage.list.assert_called_once_with(user=None, status="scheduled")

    def test_list_meetings_empty(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """List meetings when none exist."""
        # Arrange
        mock_storage.list.return_value = []

        # Act
        meetings = service.list_scheduled_meetings()

        # Assert
        assert meetings == []


class TestGetScheduledMeeting:
    """Tests for get_scheduled_meeting method."""

    def test_get_meeting_success(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """Successfully get a scheduled meeting."""
        # Arrange
        mock_storage.get.return_value = sample_scheduled_meeting

        # Act
        meeting = service.get_scheduled_meeting("sched-123")

        # Assert
        assert meeting is not None
        assert meeting.id == "sched-123"
        assert meeting.meeting_url == "https://zoom.us/j/123456789"
        mock_storage.get.assert_called_once_with("sched-123")

    def test_get_meeting_not_found(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """Return None when meeting not found."""
        # Arrange
        mock_storage.get.return_value = None

        # Act
        meeting = service.get_scheduled_meeting("sched-999")

        # Assert
        assert meeting is None
        mock_storage.get.assert_called_once_with("sched-999")


class TestDeleteScheduledMeeting:
    """Tests for delete_scheduled_meeting method."""

    def test_delete_meeting_success(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """Successfully delete a scheduled meeting."""
        # Arrange
        mock_storage.delete.return_value = (True, None)

        # Act
        success, error = service.delete_scheduled_meeting("sched-123")

        # Assert
        assert success is True
        assert error is None
        mock_storage.delete.assert_called_once_with("sched-123")

    def test_delete_meeting_not_found(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """Handle deleting non-existent meeting."""
        # Arrange
        mock_storage.delete.return_value = (False, "Meeting not found")

        # Act
        success, error = service.delete_scheduled_meeting("sched-999")

        # Assert
        assert success is False
        assert error == "Meeting not found"

    def test_delete_meeting_storage_error(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """Handle storage error during deletion."""
        # Arrange
        mock_storage.delete.return_value = (False, "Database error")

        # Act
        success, error = service.delete_scheduled_meeting("sched-123")

        # Assert
        assert success is False
        assert error == "Database error"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
