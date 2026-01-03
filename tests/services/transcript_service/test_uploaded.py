"""
Tests for TranscriptService - Uploaded transcript processing.

Test coverage:
- Happy path: User-uploaded transcript processing
- Edge cases: Pipeline failures
- Features: Title handling, intermediate file uploads
"""

from unittest.mock import MagicMock, mock_open, patch

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
def sample_transcript_data() -> list:
    """Sample transcript JSON data."""
    return [
        {
            "speaker": "Speaker 1",
            "words": [
                {"text": "Hello", "start": 0.0, "end": 0.5},
                {"text": "world", "start": 0.5, "end": 1.0},
            ],
        }
    ]


class TestProcessUploadedTranscript:
    """Tests for process_uploaded_transcript method."""

    @patch("os.path.exists")
    @patch("src.pipeline.combine_transcript_words.combine_transcript_words")
    @patch("builtins.open", new_callable=mock_open)
    def test_process_uploaded_transcript_success(
        self,
        mock_file: MagicMock,
        mock_combine: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        mock_plugin: MagicMock,
        sample_transcript_data: list,
    ) -> None:
        """Successfully process an uploaded transcript."""
        mock_exists.return_value = True
        mock_storage.save_file_from_path.side_effect = lambda mid, fname, fpath: (
            f"gs://bucket/{mid}/{fname}"
        )

        result = service.process_uploaded_transcript(
            "meeting-123", sample_transcript_data
        )

        assert "outputs" in result
        assert isinstance(result["outputs"], dict)

        mock_combine.assert_called_once()
        mock_plugin.process_transcript.assert_called_once()

        mock_storage.update_meeting.assert_any_call(
            "meeting-123", {"status": "processing"}
        )

        final_call = mock_storage.update_meeting.call_args_list[-1]
        assert final_call[0][1]["status"] == "completed"

    @patch("os.path.exists")
    @patch("src.pipeline.combine_transcript_words.combine_transcript_words")
    @patch("builtins.open", new_callable=mock_open)
    def test_process_uploaded_transcript_with_title(
        self,
        mock_file: MagicMock,
        mock_combine: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        mock_plugin: MagicMock,
        sample_transcript_data: list,
    ) -> None:
        """Process uploaded transcript with title."""
        mock_exists.return_value = True
        mock_storage.save_file_from_path.return_value = "gs://bucket/file"

        result = service.process_uploaded_transcript(
            "meeting-123", sample_transcript_data, title="My Lecture"
        )

        assert "outputs" in result

        title_calls = [
            c
            for c in mock_storage.update_meeting.call_args_list
            if "title" in c[0][1]
        ]
        assert len(title_calls) > 0
        assert title_calls[0][0][1]["title"] == "My Lecture"

    @patch("os.path.exists")
    @patch("src.pipeline.combine_transcript_words.combine_transcript_words")
    @patch("builtins.open", new_callable=mock_open)
    def test_process_uploaded_transcript_uploads_intermediate_files(
        self,
        mock_file: MagicMock,
        mock_combine: MagicMock,
        mock_exists: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        mock_plugin: MagicMock,
        sample_transcript_data: list,
    ) -> None:
        """Uploaded transcripts include intermediate files."""
        mock_exists.return_value = True
        uploaded_files = []

        def capture_upload(mid: str, fname: str, fpath: str) -> str:
            uploaded_files.append(fname)
            return f"gs://bucket/{mid}/{fname}"

        mock_storage.save_file_from_path.side_effect = capture_upload

        _result = service.process_uploaded_transcript("meeting-123", sample_transcript_data)

        assert len(uploaded_files) >= 5

        combined_present = any("combined" in f for f in uploaded_files)
        chunks_present = any("chunks" in f for f in uploaded_files)
        assert combined_present, f"Expected combined file in {uploaded_files}"
        assert chunks_present, f"Expected chunks file in {uploaded_files}"

    @patch("src.pipeline.combine_transcript_words.combine_transcript_words")
    @patch("builtins.open", new_callable=mock_open)
    def test_process_uploaded_transcript_pipeline_failure(
        self,
        mock_file: MagicMock,
        mock_combine: MagicMock,
        service: TranscriptService,
        mock_storage: MagicMock,
        sample_transcript_data: list,
    ) -> None:
        """Handle pipeline failure during uploaded transcript processing."""
        mock_combine.side_effect = Exception("Pipeline error")

        with pytest.raises(Exception, match="Pipeline error"):
            service.process_uploaded_transcript("meeting-123", sample_transcript_data)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
