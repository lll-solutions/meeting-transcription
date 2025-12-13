"""
Tests for WebhookService recording events.

Test coverage:
- recording.done event handling
- Recording ID updates
- Transcript request triggering
"""

from unittest.mock import MagicMock, patch

import pytest

from src.services.webhook_service import WebhookService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock MeetingStorage instance."""
    return MagicMock()


@pytest.fixture
def mock_recall() -> MagicMock:
    """Mock Recall API client."""
    return MagicMock()


@pytest.fixture
def service(mock_storage: MagicMock, mock_recall: MagicMock) -> WebhookService:
    """WebhookService instance with mocked dependencies."""
    return WebhookService(storage=mock_storage, recall_client=mock_recall)


class TestRecordingDoneEvent:
    """Tests for recording.done event."""

    @patch("time.sleep")
    def test_recording_done_success(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Successfully handle recording.done event."""
        # Arrange
        event_data = {
            "event": "recording.done",
            "data": {"recording": {"id": "rec-123"}, "bot": {"id": "bot-456"}},
        }
        mock_recall.create_async_transcript.return_value = {"id": "trans-789"}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # First update: recording_id
        # Second update: transcript_id and status
        assert mock_storage.update_meeting.call_count == 2

        mock_storage.update_meeting.assert_any_call("bot-456", {"recording_id": "rec-123"})
        mock_storage.update_meeting.assert_any_call(
            "bot-456", {"transcript_id": "trans-789", "status": "transcribing"}
        )

        mock_recall.create_async_transcript.assert_called_once_with("rec-123")
        mock_sleep.assert_called_once_with(5)

    @patch("time.sleep")
    def test_recording_done_without_bot_id(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle recording.done without bot_id."""
        # Arrange
        event_data = {"event": "recording.done", "data": {"recording": {"id": "rec-123"}}}
        mock_recall.create_async_transcript.return_value = {"id": "trans-789"}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # Should not update meeting (no bot_id)
        mock_storage.update_meeting.assert_not_called()

        # But should still request transcript
        mock_recall.create_async_transcript.assert_called_once_with("rec-123")

    @patch("time.sleep")
    def test_recording_done_without_recording_id(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle recording.done without recording_id."""
        # Arrange
        event_data = {"event": "recording.done", "data": {"bot": {"id": "bot-456"}}}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # Should not call transcript request (no recording_id)
        mock_recall.create_async_transcript.assert_not_called()
        mock_storage.update_meeting.assert_not_called()

    @patch("time.sleep")
    def test_recording_done_storage_update_fails(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle storage update failure gracefully."""
        # Arrange
        event_data = {
            "event": "recording.done",
            "data": {"recording": {"id": "rec-123"}, "bot": {"id": "bot-456"}},
        }
        mock_recall.create_async_transcript.return_value = {"id": "trans-789"}
        mock_storage.update_meeting.side_effect = Exception("Storage error")

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert - should not raise exception
        # Should attempt both updates despite first failing
        assert mock_storage.update_meeting.call_count >= 1
        mock_recall.create_async_transcript.assert_called_once()

    @patch("time.sleep")
    def test_recording_done_transcript_request_fails(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle transcript request failure gracefully."""
        # Arrange
        event_data = {
            "event": "recording.done",
            "data": {"recording": {"id": "rec-123"}, "bot": {"id": "bot-456"}},
        }
        mock_recall.create_async_transcript.return_value = None

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # Should still update recording_id
        mock_storage.update_meeting.assert_called_once_with(
            "bot-456", {"recording_id": "rec-123"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
