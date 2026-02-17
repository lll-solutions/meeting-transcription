"""
Tests for WebhookService bot lifecycle events.

Test coverage:
- bot.joining_call event handling
- bot.done / bot.call_ended event handling
- Status updates and transcript requests
"""

from unittest.mock import MagicMock, patch

import pytest
from meeting_transcription.services.webhook_service import WebhookService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock MeetingStorage instance."""
    return MagicMock()


@pytest.fixture
def mock_recall() -> MagicMock:
    """Mock Recall API client (legacy)."""
    mock = MagicMock()
    mock.create_async_transcript = MagicMock()
    return mock


@pytest.fixture
def mock_provider() -> MagicMock:
    """Mock TranscriptProvider that is NOT a RecallProvider."""
    provider = MagicMock()
    provider.provider_type = MagicMock()
    provider.provider_type.value = "test"
    return provider


@pytest.fixture
def service(mock_storage: MagicMock, mock_recall: MagicMock, mock_provider: MagicMock) -> WebhookService:
    """WebhookService instance with mocked dependencies."""
    return WebhookService(storage=mock_storage, recall_client=mock_recall, provider=mock_provider)


class TestBotJoiningEvent:
    """Tests for bot.joining_call event."""

    def test_bot_joining_success(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Successfully handle bot joining event."""
        # Arrange
        event_data = {
            "event": "bot.joining_call",
            "data": {"bot": {"id": "bot-123"}},
        }

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        mock_storage.update_meeting.assert_called_once_with(
            "bot-123", {"status": "in_meeting"}
        )

    def test_bot_joining_with_bot_id_field(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Handle bot joining with bot_id field (fallback)."""
        # Arrange
        event_data = {"event": "bot.joining_call", "bot_id": "bot-456"}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        mock_storage.update_meeting.assert_called_once_with(
            "bot-456", {"status": "in_meeting"}
        )

    def test_bot_joining_without_bot_id(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Handle bot joining without bot_id (should not crash)."""
        # Arrange
        event_data = {"event": "bot.joining_call", "data": {}}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        mock_storage.update_meeting.assert_not_called()


class TestBotEndedEvent:
    """Tests for bot.done / bot.call_ended events."""

    @patch("time.sleep")
    def test_bot_done_success(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Successfully handle bot.done event."""
        # Arrange
        event_data = {
            "event": "bot.done",
            "data": {"bot": {"id": "bot-123"}, "recording": {"id": "rec-456"}},
        }
        mock_recall.create_async_transcript.return_value = {"id": "trans-789"}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # First update: status ended with recording_id
        assert mock_storage.update_meeting.call_count == 2
        mock_storage.update_meeting.assert_any_call(
            "bot-123", {"status": "ended", "recording_id": "rec-456"}
        )

        # Second update: transcript_id and status transcribing
        mock_storage.update_meeting.assert_any_call(
            "bot-123", {"transcript_id": "trans-789", "status": "transcribing"}
        )

        # Verify transcript request
        mock_recall.create_async_transcript.assert_called_once_with("rec-456")
        mock_sleep.assert_called_once_with(5)

    @patch("time.sleep")
    def test_bot_call_ended_success(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Successfully handle bot.call_ended event."""
        # Arrange
        event_data = {
            "event": "bot.call_ended",
            "data": {"bot": {"id": "bot-999"}, "recording_id": "rec-888"},
        }
        mock_recall.create_async_transcript.return_value = {"id": "trans-777"}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        assert mock_storage.update_meeting.call_count == 2
        mock_storage.update_meeting.assert_any_call(
            "bot-999", {"status": "ended", "recording_id": "rec-888"}
        )

    @patch("time.sleep")
    def test_bot_ended_without_recording_id(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle bot.done without recording_id."""
        # Arrange
        event_data = {"event": "bot.done", "data": {"bot": {"id": "bot-123"}}}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        mock_storage.update_meeting.assert_called_once_with(
            "bot-123", {"status": "ended", "recording_id": None}
        )
        mock_recall.create_async_transcript.assert_not_called()

    @patch("time.sleep")
    def test_bot_ended_transcript_request_fails(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle transcript request failure gracefully."""
        # Arrange
        event_data = {
            "event": "bot.done",
            "data": {"bot": {"id": "bot-123"}, "recording": {"id": "rec-456"}},
        }
        mock_recall.create_async_transcript.return_value = None

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # Should still update meeting status
        mock_storage.update_meeting.assert_called_once_with(
            "bot-123", {"status": "ended", "recording_id": "rec-456"}
        )

    @patch("time.sleep")
    def test_bot_ended_storage_update_fails(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle storage update failure gracefully."""
        # Arrange
        event_data = {
            "event": "bot.done",
            "data": {"bot": {"id": "bot-123"}, "recording": {"id": "rec-456"}},
        }
        mock_recall.create_async_transcript.return_value = {"id": "trans-789"}
        mock_storage.update_meeting.side_effect = [
            None,  # First call succeeds
            Exception("Storage error"),  # Second call fails
        ]

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert - should not raise exception
        assert mock_storage.update_meeting.call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
