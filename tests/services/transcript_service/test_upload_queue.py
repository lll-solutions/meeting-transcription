"""
Tests for TranscriptService upload and queue operations.

Test coverage:
- queue_uploaded_transcript: Validation, storage, task creation
- fetch_and_process_uploaded: Fetching and processing
- reprocess_transcript: Reprocessing both types
"""

from unittest.mock import MagicMock, patch

import pytest
from meeting_transcription.services.transcript_service import TranscriptService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock meeting storage."""
    storage = MagicMock()
    storage.create_meeting = MagicMock()
    storage.update_meeting = MagicMock()
    storage.get_meeting = MagicMock()
    return storage


@pytest.fixture
def service(mock_storage: MagicMock) -> TranscriptService:
    """TranscriptService instance with mocked dependencies."""
    return TranscriptService(storage=mock_storage, llm_provider="vertex_ai")


@pytest.fixture
def sample_transcript() -> list:
    """Sample transcript data."""
    return [
        {"speaker": "Alice", "words": [{"text": "Hello", "start": 0.0, "end": 0.5}]},
        {"speaker": "Bob", "words": [{"text": "Hi", "start": 1.0, "end": 1.3}]}
    ]


class TestQueueUploadedTranscript:
    """Tests for queue_uploaded_transcript method."""

    def test_queue_rejects_invalid_data_not_list(
        self,
        service: TranscriptService,
    ) -> None:
        """Reject invalid transcript data (not a list)."""
        with pytest.raises(ValueError, match="Invalid transcript format"):
            service.queue_uploaded_transcript(
                user="user@example.com",
                transcript_data="not a list",  # type: ignore[arg-type]
                title="Test",
                plugin=None,
                metadata=None,
                service_url="https://example.com"
            )

    def test_queue_rejects_empty_transcript(
        self,
        service: TranscriptService,
    ) -> None:
        """Reject empty transcript data."""
        with pytest.raises(ValueError, match="Transcript is empty"):
            service.queue_uploaded_transcript(
                user="user@example.com",
                transcript_data=[],
                title="Test",
                plugin=None,
                metadata=None,
                service_url="https://example.com"
            )

    @patch('uuid.uuid4')
    def test_queue_creates_meeting_record(
        self,
        mock_uuid4: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Create meeting record in storage."""
        mock_uuid4.return_value = MagicMock(hex="abc123defgh")

        with patch.object(service, '_store_transcript_in_gcs'), \
             patch.object(service, '_create_upload_cloud_task'):

            meeting_id, title = service.queue_uploaded_transcript(
                user="user@example.com",
                transcript_data=sample_transcript,
                title="Test Meeting",
                plugin=None,
                metadata=None,
                service_url="https://example.com"
            )

            # Verify meeting creation
            mock_storage.create_meeting.assert_called_once()
            assert meeting_id.startswith("upload-")
            assert title == "Test Meeting"

    @patch('uuid.uuid4')
    def test_queue_handles_gcs_storage_failure(
        self,
        mock_uuid4: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Handle GCS storage failure gracefully."""
        mock_uuid4.return_value = MagicMock(hex="abc123defgh")

        with patch.object(service, '_store_transcript_in_gcs') as mock_store:
            mock_store.side_effect = Exception("GCS error")

            with pytest.raises(RuntimeError, match="Failed to store transcript"):
                service.queue_uploaded_transcript(
                    user="user@example.com",
                    transcript_data=sample_transcript,
                    title="Test",
                    plugin=None,
                    metadata=None,
                    service_url="https://example.com"
                )

            # Verify meeting status was updated to failed
            assert mock_storage.update_meeting.called

    @patch('uuid.uuid4')
    def test_queue_handles_cloud_task_failure(
        self,
        mock_uuid4: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Handle Cloud Task creation failure gracefully."""
        mock_uuid4.return_value = MagicMock(hex="abc123defgh")

        with patch.object(service, '_store_transcript_in_gcs'), \
             patch.object(service, '_create_upload_cloud_task') as mock_task:
            mock_task.side_effect = Exception("Cloud Tasks error")

            with pytest.raises(RuntimeError, match="Failed to queue processing"):
                service.queue_uploaded_transcript(
                    user="user@example.com",
                    transcript_data=sample_transcript,
                    title="Test",
                    plugin=None,
                    metadata=None,
                    service_url="https://example.com"
                )


class TestFetchAndProcessUploaded:
    """Tests for fetch_and_process_uploaded method."""

    def test_fetch_raises_error_when_meeting_not_found(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Raise error when meeting not found."""
        mock_storage.get_meeting.return_value = None

        with pytest.raises(RuntimeError, match="Meeting meeting-123 not found"):
            service.fetch_and_process_uploaded("meeting-123")

    def test_fetch_processes_transcript(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Successfully fetch and process uploaded transcript."""
        meeting = {
            "id": "meeting-123",
            "user": "user@example.com",
            "status": "queued",
            "bot_name": "Test Meeting"
        }
        mock_storage.get_meeting.return_value = meeting

        with patch.object(service, '_fetch_transcript_from_gcs') as mock_fetch, \
             patch.object(service, 'process_uploaded_transcript') as mock_process:

            mock_fetch.return_value = sample_transcript

            service.fetch_and_process_uploaded("meeting-123")

            mock_fetch.assert_called_once_with("meeting-123")
            mock_process.assert_called_once_with("meeting-123", sample_transcript, "Test Meeting")

    def test_fetch_uses_custom_title_if_provided(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Use custom title if provided."""
        meeting = {
            "id": "meeting-123",
            "user": "user@example.com",
            "status": "queued",
            "bot_name": "Old Title"
        }
        mock_storage.get_meeting.return_value = meeting

        with patch.object(service, '_fetch_transcript_from_gcs') as mock_fetch, \
             patch.object(service, 'process_uploaded_transcript') as mock_process:

            mock_fetch.return_value = sample_transcript

            service.fetch_and_process_uploaded("meeting-123", "Custom Title")

            mock_process.assert_called_once_with("meeting-123", sample_transcript, "Custom Title")


class TestReprocessTranscript:
    """Tests for reprocess_transcript method."""

    def test_reprocess_raises_error_when_meeting_not_found(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Raise error when meeting not found."""
        mock_storage.get_meeting.return_value = None

        with pytest.raises(RuntimeError, match="Meeting meeting-123 not found"):
            service.reprocess_transcript("meeting-123")

    def test_reprocess_recall_transcript(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Reprocess a Recall transcript."""
        meeting = {
            "id": "meeting-123",
            "transcript_id": "transcript-456",
            "recording_id": "recording-789",
            "status": "failed"
        }
        mock_storage.get_meeting.return_value = meeting

        with patch.object(service, 'process_recall_transcript') as mock_process:
            result = service.reprocess_transcript("meeting-123")

            assert result == "recall"
            mock_process.assert_called_once_with("transcript-456", "recording-789")

    def test_reprocess_uploaded_transcript(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Reprocess an uploaded transcript."""
        meeting = {
            "id": "meeting-123",
            "status": "failed",
            "bot_name": "Test Meeting",
            "outputs": {}
        }
        mock_storage.get_meeting.return_value = meeting

        with patch.object(service, '_fetch_transcript_from_gcs') as mock_fetch, \
             patch.object(service, 'process_uploaded_transcript') as mock_process:

            mock_fetch.return_value = sample_transcript

            result = service.reprocess_transcript("meeting-123")

            assert result == "uploaded"
            mock_fetch.assert_called_once_with("meeting-123")
            mock_process.assert_called_once()

    def test_reprocess_uploaded_falls_back_to_stored_output(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript: list,
    ) -> None:
        """Fallback to stored output if temp doesn't exist."""
        meeting = {
            "id": "meeting-123",
            "status": "completed",
            "bot_name": "Test Meeting",
            "outputs": {
                "transcript_raw": "gs://bucket/meeting-123/transcript_raw.json"
            }
        }
        mock_storage.get_meeting.return_value = meeting

        with patch.object(service, '_fetch_transcript_from_gcs') as mock_fetch_temp, \
             patch.object(service, '_fetch_transcript_from_stored_output') as mock_fetch_stored, \
             patch.object(service, 'process_uploaded_transcript') as mock_process:

            mock_fetch_temp.side_effect = Exception("Not found")
            mock_fetch_stored.return_value = sample_transcript

            result = service.reprocess_transcript("meeting-123")

            assert result == "uploaded"
            mock_fetch_stored.assert_called_once()
            mock_process.assert_called_once()

    def test_reprocess_raises_error_when_no_transcript_data(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Raise error when no transcript data available."""
        meeting = {
            "id": "meeting-123",
            "status": "failed",
            "outputs": {}
        }
        mock_storage.get_meeting.return_value = meeting

        with patch.object(service, '_fetch_transcript_from_gcs') as mock_fetch:
            mock_fetch.side_effect = Exception("Not found")

            with pytest.raises(RuntimeError, match="No transcript data found"):
                service.reprocess_transcript("meeting-123")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
