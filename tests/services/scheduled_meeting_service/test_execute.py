"""
Tests for ScheduledMeetingService execution operations.

Test coverage:
- Executing pending scheduled meetings
- Success and failure scenarios
- Storage updates after execution
- Error handling
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


class TestExecutePendingMeetings:
    """Tests for execute_pending_meetings method."""

    def test_execute_no_pending_meetings(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """Handle case with no pending meetings."""
        # Arrange
        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = []

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert
        assert result["executed"] == 0
        assert result["message"] == "No pending meetings to execute"
        assert len(result["results"]) == 0
        mock_storage.get_pending.assert_called_once_with(before_time=before_time)

    def test_execute_single_meeting_success(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_meeting_service: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """Successfully execute a single pending meeting."""
        # Arrange
        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = [sample_scheduled_meeting]
        mock_meeting_service.join_meeting_for_scheduler.return_value = "meeting-456"

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert
        assert result["executed"] == 1
        assert len(result["results"]) == 1
        assert result["results"][0]["status"] == "completed"
        assert result["results"][0]["meeting_id"] == "meeting-456"

        # Verify meeting service was called
        mock_meeting_service.join_meeting_for_scheduler.assert_called_once_with(
            meeting_url="https://zoom.us/j/123456789",
            user="user@example.com",
            webhook_url="",
            bot_name="Test Bot",
            instructor_name=None,
        )

        # Verify storage was updated
        mock_storage.update.assert_called_once_with(
            "sched-123", {"status": "completed", "actual_meeting_id": "meeting-456"}
        )

    def test_execute_multiple_meetings_success(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_meeting_service: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """Execute multiple pending meetings."""
        # Arrange
        meeting2 = ScheduledMeeting(
            id="sched-789",
            meeting_url="https://meet.google.com/abc-defg-hij",
            scheduled_time=datetime(2024, 12, 15, 20, 45),
            user="user2@example.com",
            bot_name="Bot 2",
            user_timezone="America/Los_Angeles",
        )

        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = [sample_scheduled_meeting, meeting2]
        mock_meeting_service.join_meeting_for_scheduler.side_effect = [
            "meeting-456",
            "meeting-789",
        ]

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert
        assert result["executed"] == 2
        assert len(result["results"]) == 2
        assert all(r["status"] == "completed" for r in result["results"])

        # Verify both meetings were joined
        assert mock_meeting_service.join_meeting_for_scheduler.call_count == 2

    def test_execute_meeting_join_failure(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_meeting_service: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """Handle meeting join failure."""
        # Arrange
        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = [sample_scheduled_meeting]
        mock_meeting_service.join_meeting_for_scheduler.return_value = None

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert
        assert result["executed"] == 1
        assert result["results"][0]["status"] == "failed"
        assert result["results"][0]["error"] == "Failed to create bot"

        # Verify storage was updated with failure
        mock_storage.update.assert_called_once_with(
            "sched-123", {"status": "failed", "error": "Failed to create bot"}
        )

    def test_execute_meeting_exception_handling(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_meeting_service: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """Handle exception during meeting execution."""
        # Arrange
        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = [sample_scheduled_meeting]
        mock_meeting_service.join_meeting_for_scheduler.side_effect = Exception(
            "Network error"
        )

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert
        assert result["executed"] == 1
        assert result["results"][0]["status"] == "failed"
        assert "Network error" in result["results"][0]["error"]

        # Verify storage was updated with error
        mock_storage.update.assert_called_once_with(
            "sched-123", {"status": "failed", "error": "Network error"}
        )

    def test_execute_meeting_storage_update_fails(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_meeting_service: MagicMock,
        sample_scheduled_meeting: ScheduledMeeting,
    ) -> None:
        """Handle storage update failure gracefully."""
        # Arrange
        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = [sample_scheduled_meeting]
        mock_meeting_service.join_meeting_for_scheduler.side_effect = Exception(
            "Join error"
        )
        mock_storage.update.side_effect = Exception("Storage error")

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert - should not crash
        assert result["executed"] == 1
        assert result["results"][0]["status"] == "failed"

    def test_execute_uses_current_time_by_default(
        self, service: ScheduledMeetingService, mock_storage: MagicMock
    ) -> None:
        """Use current time when before_time not provided."""
        # Arrange
        mock_storage.get_pending.return_value = []

        # Act
        _result = service.execute_pending_meetings()

        # Assert
        # Should have called get_pending with some datetime
        assert mock_storage.get_pending.called
        call_args = mock_storage.get_pending.call_args[1]
        assert "before_time" in call_args
        assert isinstance(call_args["before_time"], datetime)

    def test_execute_with_instructor_name(
        self,
        service: ScheduledMeetingService,
        mock_storage: MagicMock,
        mock_meeting_service: MagicMock,
    ) -> None:
        """Execute meeting with instructor name."""
        # Arrange
        meeting_with_instructor = ScheduledMeeting(
            id="sched-999",
            meeting_url="https://zoom.us/j/987654321",
            scheduled_time=datetime(2024, 12, 15, 20, 30),
            user="user@example.com",
            bot_name="Test Bot",
            user_timezone="America/New_York",
            instructor_name="Dr. Smith",
        )

        before_time = datetime(2024, 12, 15, 21, 0)
        mock_storage.get_pending.return_value = [meeting_with_instructor]
        mock_meeting_service.join_meeting_for_scheduler.return_value = "meeting-111"

        # Act
        result = service.execute_pending_meetings(before_time=before_time)

        # Assert
        assert result["executed"] == 1
        assert result["results"][0]["status"] == "completed"

        # Verify instructor name was passed
        mock_meeting_service.join_meeting_for_scheduler.assert_called_once_with(
            meeting_url="https://zoom.us/j/987654321",
            user="user@example.com",
            webhook_url="",
            bot_name="Test Bot",
            instructor_name="Dr. Smith",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
