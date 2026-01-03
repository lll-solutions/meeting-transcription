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

from meeting_transcription.services.transcript_service import TranscriptService


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



if __name__ == "__main__":
    pytest.main([__file__, "-v"])
