"""
Tests for TranscriptService - Recall transcript processing.

Test coverage:
- Happy path: Recall transcript processing
- Edge cases: Download failures, pipeline failures, missing metadata
- Integration: Storage and pipeline module interaction
"""

from unittest.mock import MagicMock, patch

import pytest
from meeting_transcription.services.transcript_service import TranscriptService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock MeetingStorage instance."""
    return MagicMock()


@pytest.fixture
def mock_plugin() -> MagicMock:
    """Mock plugin instance."""
    plugin = MagicMock()
    plugin.display_name = "Test Plugin"
    plugin.process_transcript.return_value = {
        "summary": "/tmp/summary.json",
        "study_guide_md": "/tmp/guide.md",
        "study_guide_pdf": "/tmp/guide.pdf",
        "chunks": "/tmp/chunks.json",
    }
    return plugin


@pytest.fixture
def service(mock_storage: MagicMock, mock_plugin: MagicMock) -> TranscriptService:
    """TranscriptService instance with mocked storage and plugin."""
    return TranscriptService(storage=mock_storage, plugin=mock_plugin, llm_provider="test_provider")


@pytest.fixture
def sample_meeting_dict() -> dict:
    """Sample meeting data."""
    return {
        "id": "meeting-123",
        "user": "user@example.com",
        "meeting_url": "https://zoom.us/j/123456789",
        "bot_name": "Test Bot",
        "status": "in_meeting",
        "created_at": "2024-12-13T10:00:00Z",
        "instructor_name": "Dr. Smith",
        "transcript_id": "transcript-456",
        "recording_id": "recording-789",
    }


class TestProcessRecallTranscript:
    """Tests for process_recall_transcript method."""

    @patch("os.path.exists")
    @patch("meeting_transcription.pipeline.combine_transcript_words.combine_transcript_words")
    def test_process_recall_transcript_success(
        self,
        mock_combine: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        mock_plugin: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Successfully process a Recall API transcript."""
        mock_exists.return_value = True
        mock_storage.list_meetings.return_value = [sample_meeting_dict]
        mock_storage.save_file_from_path.side_effect = lambda mid, fname, fpath: (
            f"gs://bucket/{mid}/{fname}"
        )

        with patch.object(service, "_download_transcript", return_value="/tmp/transcript.json"):
            service.process_recall_transcript("transcript-456", "recording-789")

        mock_combine.assert_called_once()
        mock_plugin.process_transcript.assert_called_once()

        assert mock_storage.update_meeting.call_count >= 2
        mock_storage.update_meeting.assert_any_call(
            "meeting-123", {"status": "processing"}
        )

        final_call = mock_storage.update_meeting.call_args_list[-1]
        assert final_call[0][0] == "meeting-123"
        assert final_call[0][1]["status"] == "completed"
        assert "outputs" in final_call[0][1]
        assert "completed_at" in final_call[0][1]

    def test_process_recall_transcript_download_failure(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Handle download failure from Recall API."""
        mock_storage.list_meetings.return_value = [sample_meeting_dict]

        with patch.object(service, "_download_transcript", return_value=None):
            with pytest.raises(RuntimeError, match="Failed to download transcript"):
                service.process_recall_transcript("transcript-456")

        error_calls = [
            c for c in mock_storage.update_meeting.call_args_list if "error" in c[0][1]
        ]
        assert len(error_calls) > 0
        assert error_calls[0][0][0] == "meeting-123"
        assert error_calls[0][0][1]["status"] == "failed"
        assert "error" in error_calls[0][0][1]

    @patch("meeting_transcription.pipeline.combine_transcript_words.combine_transcript_words")
    def test_process_recall_transcript_pipeline_failure(
        self,
        mock_combine: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Handle pipeline processing failure."""
        mock_combine.side_effect = Exception("Pipeline error")
        mock_storage.list_meetings.return_value = [sample_meeting_dict]

        with patch.object(service, "_download_transcript", return_value="/tmp/transcript.json"):
            with pytest.raises(Exception, match="Pipeline error"):
                service.process_recall_transcript("transcript-456")

        error_calls = [
            c for c in mock_storage.update_meeting.call_args_list if "error" in c[0][1]
        ]
        assert len(error_calls) > 0
        assert error_calls[0][0][1]["status"] == "failed"

    @patch("os.path.exists")
    @patch("meeting_transcription.pipeline.combine_transcript_words.combine_transcript_words")
    def test_process_recall_transcript_with_metadata_patching(
        self,
        mock_combine: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        mock_plugin: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Successfully pass meeting metadata to plugin."""
        mock_exists.return_value = True
        mock_storage.list_meetings.return_value = [sample_meeting_dict]
        mock_storage.save_file_from_path.return_value = "gs://bucket/file"

        with patch.object(service, "_download_transcript", return_value="/tmp/transcript.json"):
            service.process_recall_transcript("transcript-456")

        # Verify plugin was called with metadata
        mock_plugin.process_transcript.assert_called_once()
        call_kwargs = mock_plugin.process_transcript.call_args[1]
        assert "metadata" in call_kwargs
        assert call_kwargs["metadata"] == sample_meeting_dict

    @patch("os.path.exists")
    @patch("meeting_transcription.pipeline.combine_transcript_words.combine_transcript_words")
    def test_process_recall_transcript_uses_recording_id_when_meeting_not_found(
        self,
        mock_combine: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        mock_plugin: MagicMock,
    ) -> None:
        """Process transcript using recording_id as fallback when meeting not found."""
        mock_exists.return_value = True
        mock_storage.list_meetings.return_value = []
        mock_storage.save_file_from_path.return_value = "gs://bucket/file"

        with patch.object(service, "_download_transcript", return_value="/tmp/transcript.json"):
            service.process_recall_transcript("transcript-456", "recording-789")

        mock_storage.update_meeting.assert_any_call(
            "recording-789", {"status": "processing"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
