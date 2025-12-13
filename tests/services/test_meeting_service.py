"""
Tests for MeetingService.

Test coverage:
- Happy path: All CRUD operations
- Edge cases: Invalid URLs, API failures, missing data
- Integration: Storage and Recall API interaction
"""

from unittest.mock import MagicMock, patch

import pytest

from src.models.meeting import Meeting
from src.services.meeting_service import MeetingService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock MeetingStorage instance."""
    return MagicMock()


@pytest.fixture
def service(mock_storage: MagicMock) -> MeetingService:
    """MeetingService instance with mocked storage."""
    return MeetingService(storage=mock_storage)


@pytest.fixture
def sample_meeting_dict() -> dict:
    """Sample meeting data as returned from storage."""
    return {
        "id": "bot-123",
        "user": "user@example.com",
        "meeting_url": "https://zoom.us/j/123456789",
        "bot_name": "Test Bot",
        "status": "in_meeting",
        "created_at": "2024-12-13T10:00:00Z",
        "instructor_name": "Dr. Smith",
        "recording_id": None,
        "transcript_id": None,
        "outputs": {},
        "completed_at": None,
        "error": None,
    }


class TestCreateMeeting:
    """Tests for create_meeting method."""

    @patch("src.services.meeting_service.create_bot")
    def test_create_meeting_success(
        self,
        mock_create_bot: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Successfully create a meeting with valid inputs."""
        # Arrange
        mock_create_bot.return_value = {"id": "bot-123", "status": "joining"}
        mock_storage.create_meeting.return_value = sample_meeting_dict

        # Act
        meeting = service.create_meeting(
            meeting_url="https://zoom.us/j/123456789",
            user="user@example.com",
            webhook_url="https://example.com/webhook",
            bot_name="Test Bot",
            instructor_name="Dr. Smith",
        )

        # Assert
        assert isinstance(meeting, Meeting)
        assert meeting.id == "bot-123"
        assert meeting.user == "user@example.com"
        assert meeting.bot_name == "Test Bot"
        assert meeting.instructor_name == "Dr. Smith"

        mock_create_bot.assert_called_once_with(
            "https://zoom.us/j/123456789", "https://example.com/webhook", "Test Bot"
        )
        mock_storage.create_meeting.assert_called_once()

    @patch("src.services.meeting_service.create_bot")
    def test_create_meeting_default_bot_name(
        self,
        mock_create_bot: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Use default bot name when none provided."""
        # Arrange
        mock_create_bot.return_value = {"id": "bot-123"}
        mock_storage.create_meeting.return_value = sample_meeting_dict

        # Act
        _meeting = service.create_meeting(
            meeting_url="https://zoom.us/j/123456789",
            user="user@example.com",
            webhook_url="https://example.com/webhook",
        )

        # Assert
        mock_create_bot.assert_called_once_with(
            "https://zoom.us/j/123456789",
            "https://example.com/webhook",
            "Meeting Assistant Bot",
        )

    def test_create_meeting_invalid_url(self, service: MeetingService) -> None:
        """Raise ValueError for invalid meeting URL."""
        # Act & Assert
        with pytest.raises(ValueError, match="not supported"):
            service.create_meeting(
                meeting_url="https://evil.com/fake",
                user="user@example.com",
                webhook_url="https://example.com/webhook",
            )

    def test_create_meeting_empty_url(self, service: MeetingService) -> None:
        """Raise ValueError for empty meeting URL."""
        # Act & Assert
        with pytest.raises(ValueError, match="required"):
            service.create_meeting(
                meeting_url="",
                user="user@example.com",
                webhook_url="https://example.com/webhook",
            )

    @patch("src.services.meeting_service.create_bot")
    def test_create_meeting_api_returns_none(
        self,
        mock_create_bot: MagicMock,
        service: MeetingService,
    ) -> None:
        """Raise RuntimeError when Recall API returns None."""
        # Arrange
        mock_create_bot.return_value = None

        # Act & Assert
        with pytest.raises(RuntimeError, match="Failed to create bot"):
            service.create_meeting(
                meeting_url="https://zoom.us/j/123456789",
                user="user@example.com",
                webhook_url="https://example.com/webhook",
            )


class TestListMeetings:
    """Tests for list_meetings method."""

    def test_list_meetings_all(
        self,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """List all meetings when no user filter provided."""
        # Arrange
        mock_storage.list_meetings.return_value = [
            sample_meeting_dict,
            {**sample_meeting_dict, "id": "bot-456"},
        ]

        # Act
        meetings = service.list_meetings()

        # Assert
        assert len(meetings) == 2
        assert all(isinstance(m, Meeting) for m in meetings)
        assert meetings[0].id == "bot-123"
        assert meetings[1].id == "bot-456"
        mock_storage.list_meetings.assert_called_once_with(user=None)

    def test_list_meetings_filtered_by_user(
        self,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """List meetings filtered by user."""
        # Arrange
        mock_storage.list_meetings.return_value = [sample_meeting_dict]

        # Act
        meetings = service.list_meetings(user="user@example.com")

        # Assert
        assert len(meetings) == 1
        assert meetings[0].user == "user@example.com"
        mock_storage.list_meetings.assert_called_once_with(user="user@example.com")

    def test_list_meetings_empty(
        self,
        service: MeetingService,
        mock_storage: MagicMock,
    ) -> None:
        """Return empty list when no meetings exist."""
        # Arrange
        mock_storage.list_meetings.return_value = []

        # Act
        meetings = service.list_meetings()

        # Assert
        assert meetings == []


class TestGetMeeting:
    """Tests for get_meeting method."""

    def test_get_meeting_from_storage(
        self,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Get meeting from storage when it exists."""
        # Arrange
        mock_storage.get_meeting.return_value = sample_meeting_dict

        # Act
        meeting = service.get_meeting("bot-123")

        # Assert
        assert meeting is not None
        assert isinstance(meeting, Meeting)
        assert meeting.id == "bot-123"
        mock_storage.get_meeting.assert_called_once_with("bot-123")

    @patch("src.services.meeting_service.get_bot_status")
    def test_get_meeting_from_api_fallback(
        self,
        mock_get_bot_status: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Fallback to Recall API when not in storage."""
        # Arrange
        mock_storage.get_meeting.return_value = None
        mock_get_bot_status.return_value = sample_meeting_dict

        # Act
        meeting = service.get_meeting("bot-123")

        # Assert
        assert meeting is not None
        assert isinstance(meeting, Meeting)
        assert meeting.id == "bot-123"
        mock_get_bot_status.assert_called_once_with("bot-123")

    @patch("src.services.meeting_service.get_bot_status")
    def test_get_meeting_not_found(
        self,
        mock_get_bot_status: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
    ) -> None:
        """Return None when meeting not found anywhere."""
        # Arrange
        mock_storage.get_meeting.return_value = None
        mock_get_bot_status.return_value = None

        # Act
        meeting = service.get_meeting("bot-999")

        # Assert
        assert meeting is None


class TestDeleteMeeting:
    """Tests for delete_meeting method."""

    @patch("src.services.meeting_service.leave_meeting")
    def test_delete_meeting_success(
        self,
        mock_leave_meeting: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
    ) -> None:
        """Successfully delete meeting and update status."""
        # Arrange
        mock_leave_meeting.return_value = True

        # Act
        result = service.delete_meeting("bot-123")

        # Assert
        assert result is True
        mock_leave_meeting.assert_called_once_with("bot-123")
        mock_storage.update_meeting.assert_called_once_with(
            "bot-123", {"status": "leaving"}
        )

    @patch("src.services.meeting_service.leave_meeting")
    def test_delete_meeting_failure(
        self,
        mock_leave_meeting: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
    ) -> None:
        """Return False when API fails to remove bot."""
        # Arrange
        mock_leave_meeting.return_value = False

        # Act
        result = service.delete_meeting("bot-123")

        # Assert
        assert result is False
        mock_storage.update_meeting.assert_not_called()


class TestJoinMeetingForScheduler:
    """Tests for join_meeting_for_scheduler method."""

    @patch("src.services.meeting_service.create_bot")
    def test_join_meeting_for_scheduler_success(
        self,
        mock_create_bot: MagicMock,
        service: MeetingService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Successfully join meeting for scheduler."""
        # Arrange
        mock_create_bot.return_value = {"id": "bot-123"}
        mock_storage.create_meeting.return_value = sample_meeting_dict

        # Act
        meeting_id = service.join_meeting_for_scheduler(
            meeting_url="https://zoom.us/j/123456789",
            user="scheduler@system",
            webhook_url="https://example.com/webhook",
            bot_name="Scheduled Bot",
        )

        # Assert
        assert meeting_id == "bot-123"

    def test_join_meeting_for_scheduler_invalid_url(
        self, service: MeetingService
    ) -> None:
        """Return None when URL is invalid."""
        # Act
        meeting_id = service.join_meeting_for_scheduler(
            meeting_url="https://evil.com/fake",
            user="scheduler@system",
            webhook_url="https://example.com/webhook",
        )

        # Assert
        assert meeting_id is None

    @patch("src.services.meeting_service.create_bot")
    def test_join_meeting_for_scheduler_api_failure(
        self,
        mock_create_bot: MagicMock,
        service: MeetingService,
    ) -> None:
        """Return None when Recall API fails."""
        # Arrange
        mock_create_bot.return_value = None

        # Act
        meeting_id = service.join_meeting_for_scheduler(
            meeting_url="https://zoom.us/j/123456789",
            user="scheduler@system",
            webhook_url="https://example.com/webhook",
        )

        # Assert
        assert meeting_id is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
