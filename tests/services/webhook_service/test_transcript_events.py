"""
Tests for WebhookService transcript events.

Test coverage:
- transcript.done event handling
- Cloud Tasks creation and fallback
- transcript.failed event handling
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
    """Mock Recall API client."""
    return MagicMock()


@pytest.fixture
def mock_process_callback() -> MagicMock:
    """Mock process transcript callback."""
    return MagicMock()


@pytest.fixture
def service(
    mock_storage: MagicMock, mock_recall: MagicMock, mock_process_callback: MagicMock
) -> WebhookService:
    """WebhookService instance with mocked dependencies."""
    return WebhookService(
        storage=mock_storage,
        recall_client=mock_recall,
        process_transcript_callback=mock_process_callback,
    )


class TestTranscriptDoneEvent:
    """Tests for transcript.done event."""

    @patch("google.cloud.tasks_v2.CloudTasksClient")
    @patch("os.getenv")
    def test_transcript_done_with_cloud_tasks_success(
        self,
        mock_getenv: MagicMock,
        mock_tasks_client: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
    ) -> None:
        """Successfully handle transcript.done with Cloud Tasks."""
        # Arrange
        event_data = {
            "event": "transcript.done",
            "data": {"transcript": {"id": "trans-123"}, "recording": {"id": "rec-456"}},
        }

        mock_getenv.side_effect = lambda key, default=None: {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GCP_REGION": "us-central1",
            "PROJECT_NUMBER": "123456",
        }.get(key, default)

        mock_storage.list_meetings.return_value = [
            {"id": "meeting-789", "transcript_id": "trans-123"}
        ]

        mock_client = MagicMock()
        mock_client.queue_path.return_value = "projects/test/locations/us-central1/queues/transcript-processing"
        mock_client.create_task.return_value = MagicMock(name="task-name")
        mock_tasks_client.return_value = mock_client

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        mock_client.create_task.assert_called_once()
        mock_storage.update_meeting.assert_called_once_with(
            "meeting-789", {"status": "queued"}
        )

    @patch("google.cloud.tasks_v2.CloudTasksClient")
    def test_transcript_done_cloud_tasks_fails_fallback_to_sync(
        self,
        mock_tasks_client: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_process_callback: MagicMock,
    ) -> None:
        """Fallback to sync processing when Cloud Tasks fails."""
        # Arrange
        event_data = {
            "event": "transcript.done",
            "data": {"transcript": {"id": "trans-123"}, "recording": {"id": "rec-456"}},
        }

        mock_storage.list_meetings.return_value = [
            {"id": "meeting-789", "transcript_id": "trans-123"}
        ]

        # Mock Cloud Tasks failure
        mock_tasks_client.side_effect = Exception("Cloud Tasks error")

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # Should fallback to sync processing
        mock_process_callback.assert_called_once_with("trans-123", "rec-456")

        # Should not update status to queued (Cloud Tasks failed)
        mock_storage.update_meeting.assert_not_called()

    def test_transcript_done_without_transcript_id(
        self,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_process_callback: MagicMock,
    ) -> None:
        """Handle transcript.done without transcript_id."""
        # Arrange
        event_data = {"event": "transcript.done", "data": {}}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        mock_storage.list_meetings.assert_not_called()
        mock_process_callback.assert_not_called()

    @patch("google.cloud.tasks_v2.CloudTasksClient")
    @patch("os.getenv")
    def test_transcript_done_meeting_not_found_uses_fallback_id(
        self,
        mock_getenv: MagicMock,
        mock_tasks_client: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
    ) -> None:
        """Use recording_id as meeting_id when meeting not found."""
        # Arrange
        event_data = {
            "event": "transcript.done",
            "data": {"transcript": {"id": "trans-123"}, "recording": {"id": "rec-456"}},
        }

        mock_getenv.side_effect = lambda key, default=None: {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GCP_REGION": "us-central1",
            "PROJECT_NUMBER": "123456",
        }.get(key, default)

        mock_storage.list_meetings.return_value = []  # No meetings found

        mock_client = MagicMock()
        mock_client.queue_path.return_value = "queue-path"
        mock_client.create_task.return_value = MagicMock(name="task-name")
        mock_tasks_client.return_value = mock_client

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert
        # Should use recording_id as meeting_id
        mock_storage.update_meeting.assert_called_once_with(
            "rec-456", {"status": "queued"}
        )


class TestTranscriptFailedEvent:
    """Tests for transcript.failed event."""

    def test_transcript_failed(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Handle transcript.failed event."""
        # Arrange
        event_data = {
            "event": "transcript.failed",
            "data": {"transcript": {"id": "trans-123"}, "error": "Processing failed"},
        }

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert - should not crash, just log
        mock_storage.update_meeting.assert_not_called()


class TestEventRouting:
    """Tests for event routing."""

    def test_handle_unknown_event(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Handle unknown event type gracefully."""
        # Arrange
        event_data = {"event": "unknown.event", "data": {}}

        # Act
        service.handle_event(event_data, "https://example.com")

        # Assert - should not crash
        mock_storage.update_meeting.assert_not_called()

    def test_handle_missing_event_type(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Raise error when event type is missing."""
        # Arrange
        event_data = {"data": {}}

        # Act & Assert
        with pytest.raises(ValueError, match="Missing event type"):
            service.handle_event(event_data, "https://example.com")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
