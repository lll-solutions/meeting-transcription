"""
Tests for TranscriptService - Internal pipeline helper methods.

Test coverage:
- Meeting lookup and fallback logic
- Metadata patching
- File upload handling
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


class TestPipelineInternals:
    """Tests for internal pipeline helper methods."""

    def test_find_meeting_by_transcript_id(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_meeting_dict: dict,
    ) -> None:
        """Find meeting by transcript ID."""
        mock_storage.list_meetings.return_value = [sample_meeting_dict]

        meeting_id, meeting_record = service._find_meeting_by_transcript(
            "transcript-456", None
        )

        assert meeting_id == "meeting-123"
        assert meeting_record == sample_meeting_dict

    @pytest.mark.parametrize(
        "recording_id,expected_meeting_id",
        [("recording-789", "recording-789"), (None, "transcript-456")],
    )
    def test_find_meeting_by_transcript_id_fallback(
        self,
        service: TranscriptService,
        mock_storage: MagicMock,
        recording_id: str | None,
        expected_meeting_id: str,
    ) -> None:
        """Fallback to recording_id or transcript_id when meeting not found."""
        mock_storage.list_meetings.return_value = []

        meeting_id, meeting_record = service._find_meeting_by_transcript(
            "transcript-456", recording_id
        )

        assert meeting_id == expected_meeting_id
        assert meeting_record is None

    @patch("builtins.open", new_callable=mock_open)
    def test_patch_summary_metadata(
        self, mock_file: MagicMock, service: TranscriptService
    ) -> None:
        """Patch summary with meeting metadata."""
        summary_data = {"content": "test"}
        meeting_record = {
            "created_at": "2024-12-13T10:00:00Z",
            "instructor_name": "Dr. Smith",
        }

        mock_file.return_value.__enter__.return_value.read.return_value = json.dumps(
            summary_data
        )

        service._patch_summary_metadata("summary.json", meeting_record)

        assert mock_file.call_count >= 2

    @patch("os.path.exists")
    def test_upload_outputs_all_files(
        self,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Upload all output files including PDF."""
        mock_exists.return_value = True
        mock_storage.save_file_from_path.side_effect = lambda mid, fname, fpath: (
            f"gs://bucket/{mid}/{fname}"
        )

        outputs = service._upload_outputs(
            meeting_id="meeting-123",
            transcript_file="/tmp/transcript.json",
            combined_file="/tmp/combined.json",
            chunks_file="/tmp/chunks.json",
            summary_file="/tmp/summary.json",
            study_guide_file="/tmp/guide.md",
            pdf_file="/tmp/guide.pdf",
            upload_intermediate=False,
        )

        assert "transcript" in outputs
        assert "summary" in outputs
        assert "study_guide_md" in outputs
        assert "study_guide_pdf" in outputs
        assert "transcript_combined" not in outputs

    @patch("os.path.exists")
    def test_upload_outputs_without_pdf(
        self,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Upload outputs when PDF generation failed."""
        mock_exists.return_value = True
        mock_storage.save_file_from_path.side_effect = lambda mid, fname, fpath: (
            f"gs://bucket/{mid}/{fname}"
        )

        outputs = service._upload_outputs(
            meeting_id="meeting-123",
            transcript_file="/tmp/transcript.json",
            combined_file="/tmp/combined.json",
            chunks_file="/tmp/chunks.json",
            summary_file="/tmp/summary.json",
            study_guide_file="/tmp/guide.md",
            pdf_file=None,
            upload_intermediate=False,
        )

        assert "transcript" in outputs
        assert "summary" in outputs
        assert "study_guide_md" in outputs
        assert "study_guide_pdf" not in outputs

    @patch("os.path.exists")
    def test_upload_outputs_with_intermediate_files(
        self,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
    ) -> None:
        """Upload intermediate files when flag is enabled."""
        mock_exists.return_value = True
        uploaded_files = []
        mock_storage.save_file_from_path.side_effect = lambda mid, fname, fpath: (
            uploaded_files.append(fname) or f"gs://bucket/{mid}/{fname}"
        )

        outputs = service._upload_outputs(
            meeting_id="meeting-123",
            transcript_file="/tmp/transcript.json",
            combined_file="/tmp/combined.json",
            chunks_file="/tmp/chunks.json",
            summary_file="/tmp/summary.json",
            study_guide_file="/tmp/guide.md",
            pdf_file="/tmp/guide.pdf",
            upload_intermediate=True,
        )

        assert "transcript_combined" in outputs
        assert "transcript_chunks" in outputs
        assert "combined.json" in uploaded_files
        assert "chunks.json" in uploaded_files


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
