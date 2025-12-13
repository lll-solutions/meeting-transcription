"""
Tests for TranscriptService - Recall transcript processing.

Test coverage:
- Happy path: Recall transcript processing
- Edge cases: Download failures, pipeline failures, missing metadata
- Integration: Storage and pipeline module interaction
"""

import json
from unittest.mock import MagicMock, mock_open, patch

import pytest

from src.services.transcript_service import TranscriptService


@pytest.fixture
def mock_storage() -> MagicMock:
    """Mock MeetingStorage instance."""
    return MagicMock()


@pytest.fixture
def service(mock_storage: MagicMock) -> TranscriptService:
    """TranscriptService instance with mocked storage."""
    return TranscriptService(storage=mock_storage, llm_provider="test_provider")


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
    @patch("builtins.open", new_callable=mock_open)
    @patch("src.services.transcript_service.markdown_to_pdf")
    @patch("src.services.transcript_service.create_study_guide")
    @patch("src.services.transcript_service.summarize_educational_content")
    @patch("src.services.transcript_service.create_educational_chunks")
    @patch("src.services.transcript_service.combine_transcript_words")
    @patch("src.services.transcript_service.download_transcript")
    def test_process_recall_transcript_success(
        self,
        mock_download: MagicMock,
        mock_combine: MagicMock,
        mock_chunks: MagicMock,
        mock_summarize: MagicMock,
        mock_study_guide: MagicMock,
        mock_pdf: MagicMock,
        mock_file: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Successfully process a Recall API transcript."""
        mock_download.return_value = True
        mock_exists.return_value = True
        mock_storage.list_meetings.return_value = [sample_meeting_dict]
        mock_storage.save_file_from_path.side_effect = lambda mid, fname, fpath: (
            f"gs://bucket/{mid}/{fname}"
        )

        summary_data = {"content": "test"}
        mock_file.return_value.__enter__.return_value.read.return_value = json.dumps(
            summary_data
        )

        service.process_recall_transcript("transcript-456", "recording-789")

        mock_download.assert_called_once()
        mock_combine.combine_transcript_words.assert_called_once()
        mock_chunks.create_educational_content_chunks.assert_called_once()
        mock_summarize.summarize_educational_content.assert_called_once()
        mock_study_guide.create_markdown_study_guide.assert_called_once()
        mock_pdf.convert_markdown_to_pdf.assert_called_once()

        assert mock_storage.update_meeting.call_count >= 2
        mock_storage.update_meeting.assert_any_call(
            "meeting-123", {"status": "processing"}
        )

        final_call = mock_storage.update_meeting.call_args_list[-1]
        assert final_call[0][0] == "meeting-123"
        assert final_call[0][1]["status"] == "completed"
        assert "outputs" in final_call[0][1]
        assert "completed_at" in final_call[0][1]

    @patch("src.services.transcript_service.download_transcript")
    def test_process_recall_transcript_download_failure(
        self,
        mock_download: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Handle download failure from Recall API."""
        mock_download.return_value = False
        mock_storage.list_meetings.return_value = [sample_meeting_dict]

        with pytest.raises(RuntimeError, match="Failed to download transcript"):
            service.process_recall_transcript("transcript-456")

        error_calls = [
            c for c in mock_storage.update_meeting.call_args_list if "error" in c[0][1]
        ]
        assert len(error_calls) > 0
        assert error_calls[0][0][0] == "meeting-123"
        assert error_calls[0][0][1]["status"] == "failed"
        assert "error" in error_calls[0][0][1]

    @patch("src.services.transcript_service.combine_transcript_words")
    @patch("src.services.transcript_service.download_transcript")
    def test_process_recall_transcript_pipeline_failure(
        self,
        mock_download: MagicMock,
        mock_combine: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Handle pipeline processing failure."""
        mock_download.return_value = True
        mock_combine.combine_transcript_words.side_effect = Exception("Pipeline error")
        mock_storage.list_meetings.return_value = [sample_meeting_dict]

        with pytest.raises(Exception, match="Pipeline error"):
            service.process_recall_transcript("transcript-456")

        error_calls = [
            c for c in mock_storage.update_meeting.call_args_list if "error" in c[0][1]
        ]
        assert len(error_calls) > 0
        assert error_calls[0][0][1]["status"] == "failed"

    @patch("src.services.transcript_service.markdown_to_pdf")
    @patch("src.services.transcript_service.create_study_guide")
    @patch("src.services.transcript_service.summarize_educational_content")
    @patch("src.services.transcript_service.create_educational_chunks")
    @patch("src.services.transcript_service.combine_transcript_words")
    @patch("src.services.transcript_service.download_transcript")
    @patch("builtins.open", new_callable=mock_open)
    def test_process_recall_transcript_with_metadata_patching(
        self,
        mock_file: MagicMock,
        mock_download: MagicMock,
        mock_combine: MagicMock,
        mock_chunks: MagicMock,
        mock_summarize: MagicMock,
        mock_study_guide: MagicMock,
        mock_pdf: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Successfully patch summary with meeting metadata."""
        mock_download.return_value = True
        mock_storage.list_meetings.return_value = [sample_meeting_dict]
        mock_storage.save_file_from_path.return_value = "gs://bucket/file"

        summary_data = {"content": "test"}
        mock_file.return_value.read.return_value = json.dumps(summary_data)

        service.process_recall_transcript("transcript-456")

        assert mock_file.call_count >= 2

    @patch("src.services.transcript_service.markdown_to_pdf")
    @patch("src.services.transcript_service.create_study_guide")
    @patch("src.services.transcript_service.summarize_educational_content")
    @patch("src.services.transcript_service.create_educational_chunks")
    @patch("src.services.transcript_service.combine_transcript_words")
    @patch("src.services.transcript_service.download_transcript")
    def test_process_recall_transcript_uses_recording_id_when_meeting_not_found(
        self,
        mock_download: MagicMock,
        mock_combine: MagicMock,
        mock_chunks: MagicMock,
        mock_summarize: MagicMock,
        mock_study_guide: MagicMock,
        mock_pdf: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Process transcript using recording_id as fallback when meeting not found."""
        mock_download.return_value = True
        mock_storage.list_meetings.return_value = []
        mock_storage.save_file_from_path.return_value = "gs://bucket/file"

        service.process_recall_transcript("transcript-456", "recording-789")

        mock_storage.update_meeting.assert_any_call(
            "recording-789", {"status": "processing"}
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
