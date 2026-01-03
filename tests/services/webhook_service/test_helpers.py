"""
Tests for WebhookService internal helper methods.

Test coverage:
- Meeting lookup by transcript/recording ID
- Cloud Task creation
- Transcript request handling
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
def service(mock_storage: MagicMock, mock_recall: MagicMock) -> WebhookService:
    """WebhookService instance with mocked dependencies."""
    return WebhookService(storage=mock_storage, recall_client=mock_recall)


class TestFindMeetingByTranscript:
    """Tests for _find_meeting_by_transcript method."""

    def test_find_by_transcript_id(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Find meeting by transcript_id."""
        # Arrange
        mock_storage.list_meetings.return_value = [
            {"id": "meeting-123", "transcript_id": "trans-456"},
            {"id": "meeting-789", "transcript_id": "trans-999"},
        ]

        # Act
        meeting_id = service._find_meeting_by_transcript("trans-456", None)

        # Assert
        assert meeting_id == "meeting-123"

    def test_find_by_recording_id(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Find meeting by recording_id when transcript_id not found."""
        # Arrange
        mock_storage.list_meetings.return_value = [
            {"id": "meeting-123", "recording_id": "rec-456"},
            {"id": "meeting-789", "recording_id": "rec-999"},
        ]

        # Act
        meeting_id = service._find_meeting_by_transcript("trans-unknown", "rec-456")

        # Assert
        assert meeting_id == "meeting-123"

    def test_fallback_to_recording_id(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Use recording_id as meeting_id when no match found."""
        # Arrange
        mock_storage.list_meetings.return_value = []

        # Act
        meeting_id = service._find_meeting_by_transcript("trans-123", "rec-456")

        # Assert
        assert meeting_id == "rec-456"

    def test_fallback_to_transcript_id_when_no_recording_id(
        self, service: WebhookService, mock_storage: MagicMock
    ) -> None:
        """Use transcript_id as meeting_id when no recording_id available."""
        # Arrange
        mock_storage.list_meetings.return_value = []

        # Act
        meeting_id = service._find_meeting_by_transcript("trans-123", None)

        # Assert
        assert meeting_id == "trans-123"


class TestCreateCloudTask:
    """Tests for _create_cloud_task method."""

    @patch("google.cloud.tasks_v2.CloudTasksClient")
    @patch("os.getenv")
    def test_create_cloud_task_success(
        self,
        mock_getenv: MagicMock,
        mock_tasks_client: MagicMock,
        service: WebhookService,
    ) -> None:
        """Successfully create Cloud Task."""
        # Arrange
        mock_getenv.side_effect = lambda key, default=None: {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GCP_REGION": "us-west1",
            "PROJECT_NUMBER": "987654",
        }.get(key, default)

        mock_client = MagicMock()
        mock_client.queue_path.return_value = "queue-path"
        mock_client.create_task.return_value = MagicMock(name="task-12345")
        mock_tasks_client.return_value = mock_client

        # Act
        result = service._create_cloud_task(
            "meeting-123", "trans-456", "rec-789", "https://example.com"
        )

        # Assert
        assert result is True
        mock_client.queue_path.assert_called_once_with(
            "test-project", "us-west1", "transcript-processing"
        )
        mock_client.create_task.assert_called_once()

        # Verify task payload
        task_request = mock_client.create_task.call_args[1]["request"]
        assert task_request["parent"] == "queue-path"
        assert "task" in task_request

    @patch("google.cloud.tasks_v2.CloudTasksClient")
    def test_create_cloud_task_failure(
        self, mock_tasks_client: MagicMock, service: WebhookService
    ) -> None:
        """Handle Cloud Task creation failure."""
        # Arrange
        mock_tasks_client.side_effect = Exception("Failed to create task")

        # Act
        result = service._create_cloud_task(
            "meeting-123", "trans-456", "rec-789", "https://example.com"
        )

        # Assert
        assert result is False

    @patch("google.cloud.tasks_v2.CloudTasksClient")
    @patch("os.getenv")
    def test_create_cloud_task_with_correct_url(
        self,
        mock_getenv: MagicMock,
        mock_tasks_client: MagicMock,
        service: WebhookService,
    ) -> None:
        """Verify Cloud Task URL is correctly formed."""
        # Arrange
        mock_getenv.side_effect = lambda key, default=None: {
            "GOOGLE_CLOUD_PROJECT": "test-project",
            "GCP_REGION": "us-central1",
            "PROJECT_NUMBER": "123456",
        }.get(key, default)

        mock_client = MagicMock()
        mock_client.queue_path.return_value = "queue-path"
        mock_client.create_task.return_value = MagicMock(name="task-name")
        mock_tasks_client.return_value = mock_client

        # Act
        service._create_cloud_task(
            "meeting-999", "trans-888", "rec-777", "https://api.example.com"
        )

        # Assert
        task_request = mock_client.create_task.call_args[1]["request"]
        http_request = task_request["task"]["http_request"]
        assert http_request["url"] == "https://api.example.com/api/transcripts/process-recall/meeting-999"


class TestRequestTranscript:
    """Tests for _request_transcript method."""

    @patch("time.sleep")
    def test_request_transcript_success(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Successfully request transcript."""
        # Arrange
        mock_recall.create_async_transcript.return_value = {"id": "trans-123"}

        # Act
        service._request_transcript("bot-456", "rec-789")

        # Assert
        mock_recall.create_async_transcript.assert_called_once_with("rec-789")
        mock_sleep.assert_called_once_with(5)
        mock_storage.update_meeting.assert_called_once_with(
            "bot-456", {"transcript_id": "trans-123", "status": "transcribing"}
        )

    @patch("time.sleep")
    def test_request_transcript_without_recording_id(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_recall: MagicMock,
    ) -> None:
        """Handle missing recording_id."""
        # Act
        service._request_transcript("bot-456", None)

        # Assert
        mock_recall.create_async_transcript.assert_not_called()
        mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_request_transcript_api_returns_none(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle Recall API returning None."""
        # Arrange
        mock_recall.create_async_transcript.return_value = None

        # Act
        service._request_transcript("bot-456", "rec-789")

        # Assert
        mock_recall.create_async_transcript.assert_called_once()
        mock_storage.update_meeting.assert_not_called()

    @patch("time.sleep")
    def test_request_transcript_without_bot_id(
        self,
        mock_sleep: MagicMock,
        service: WebhookService,
        mock_storage: MagicMock,
        mock_recall: MagicMock,
    ) -> None:
        """Handle missing bot_id."""
        # Arrange
        mock_recall.create_async_transcript.return_value = {"id": "trans-123"}

        # Act
        service._request_transcript(None, "rec-789")

        # Assert
        mock_recall.create_async_transcript.assert_called_once()
        mock_storage.update_meeting.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
