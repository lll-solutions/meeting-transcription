"""
Integration tests for TranscriptService with plugins.
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

from meeting_transcription.api.storage import MeetingStorage
from meeting_transcription.services.transcript_service import TranscriptService


class MockPlugin:
    """Mock plugin for testing."""

    def __init__(self):
        self.configured_settings = None

    @property
    def name(self):
        return "mock"

    @property
    def display_name(self):
        return "Mock Plugin"

    @property
    def description(self):
        return "Mock plugin for testing"

    @property
    def metadata_schema(self):
        return {"test_field": {"type": "string", "required": False}}

    @property
    def settings_schema(self):
        return {"test_setting": {"type": "string", "default": "default_value"}}

    def configure(self, settings):
        self.configured_settings = settings

    def process_transcript(self, combined_transcript_path, output_dir, llm_provider, metadata):
        """Mock processing that creates a simple output file."""
        output_path = os.path.join(output_dir, "mock_output.txt")
        with open(output_path, 'w') as f:
            f.write(f"Processed with {llm_provider}")

        return {"mock_output": output_path}


class TestTranscriptServiceIntegration:
    """Integration tests for TranscriptService with plugin system."""

    @patch('meeting_transcription.services.transcript_service.combine_transcript_words')
    def test_service_uses_plugin_for_processing(self, mock_combine_words):
        """Test that TranscriptService delegates processing to plugin."""
        # Create mock storage
        storage = Mock(spec=MeetingStorage)
        storage.update_meeting = Mock()
        storage.save_file_from_path = Mock(return_value="gs://bucket/file.txt")

        # Create mock plugin
        plugin = MockPlugin()

        # Create service with plugin
        service = TranscriptService(
            storage=storage,
            plugin=plugin,
            llm_provider="vertex_ai"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock transcript file
            transcript_file = os.path.join(temp_dir, "transcript.json")
            with open(transcript_file, 'w') as f:
                json.dump([{"word": "hello"}], f)

            def mock_combine(input_path, output_path):
                with open(output_path, 'w') as f:
                    json.dump([{"text": "hello"}], f)

            mock_combine_words.combine_transcript_words.side_effect = mock_combine

            # Run pipeline
            outputs = service._run_pipeline(
                meeting_id="test-meeting",
                transcript_file=transcript_file,
                temp_dir=temp_dir,
                meeting_record={"instructor_name": "Test"},
                upload_intermediate=False
            )

            # Verify plugin was called
            assert "mock_output" in outputs

            # Verify storage was updated
            storage.update_meeting.assert_called_once()
            update_call = storage.update_meeting.call_args
            assert update_call[0][0] == "test-meeting"
            assert update_call[0][1]["status"] == "completed"

    @patch('meeting_transcription.services.transcript_service.combine_transcript_words')
    def test_service_passes_metadata_to_plugin(self, mock_combine_words):
        """Test that TranscriptService passes metadata to plugin."""
        storage = Mock(spec=MeetingStorage)
        storage.update_meeting = Mock()
        storage.save_file_from_path = Mock(return_value="gs://bucket/file.txt")

        plugin = MockPlugin()
        service = TranscriptService(storage=storage, plugin=plugin)

        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_file = os.path.join(temp_dir, "transcript.json")
            with open(transcript_file, 'w') as f:
                json.dump([{"word": "hello"}], f)

            def mock_combine(input_path, output_path):
                with open(output_path, 'w') as f:
                    json.dump([{"text": "hello"}], f)

            mock_combine_words.combine_transcript_words.side_effect = mock_combine

            # Track what metadata was passed to plugin
            original_process = plugin.process_transcript
            received_metadata = {}

            def track_metadata(*args, **kwargs):
                received_metadata.update(kwargs.get('metadata', {}))
                return original_process(*args, **kwargs)

            plugin.process_transcript = track_metadata

            # Run with specific metadata
            meeting_metadata = {
                "instructor_name": "Dr. Smith",
                "session_number": 5
            }

            service._run_pipeline(
                meeting_id="test-meeting",
                transcript_file=transcript_file,
                temp_dir=temp_dir,
                meeting_record=meeting_metadata,
                upload_intermediate=False
            )

            # Verify metadata was passed
            assert received_metadata["instructor_name"] == "Dr. Smith"
            assert received_metadata["session_number"] == 5

    @patch('meeting_transcription.services.transcript_service.combine_transcript_words')
    def test_service_passes_llm_provider_to_plugin(self, mock_combine_words):
        """Test that TranscriptService passes LLM provider to plugin."""
        storage = Mock(spec=MeetingStorage)
        storage.update_meeting = Mock()
        storage.save_file_from_path = Mock(return_value="gs://bucket/file.txt")

        plugin = MockPlugin()
        service = TranscriptService(
            storage=storage,
            plugin=plugin,
            llm_provider="anthropic"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_file = os.path.join(temp_dir, "transcript.json")
            with open(transcript_file, 'w') as f:
                json.dump([{"word": "hello"}], f)

            def mock_combine(input_path, output_path):
                with open(output_path, 'w') as f:
                    json.dump([{"text": "hello"}], f)

            mock_combine_words.combine_transcript_words.side_effect = mock_combine

            service._run_pipeline(
                meeting_id="test-meeting",
                transcript_file=transcript_file,
                temp_dir=temp_dir,
                meeting_record={},
                upload_intermediate=False
            )

            # Check output file content
            mock_output_path = os.path.join(temp_dir, "mock_output.txt")
            with open(mock_output_path) as f:
                content = f.read()
                assert "anthropic" in content

    @patch('meeting_transcription.services.transcript_service.combine_transcript_words')
    def test_process_recall_transcript_with_plugin(self, mock_combine):
        """Test end-to-end process_recall_transcript with plugin."""
        storage = Mock(spec=MeetingStorage)
        storage.update_meeting = Mock()
        storage.save_file_from_path = Mock(return_value="gs://bucket/file.txt")
        storage.list_meetings = Mock(return_value=[
            {"id": "meeting-123", "transcript_id": "transcript-456"}
        ])

        plugin = MockPlugin()
        service = TranscriptService(storage=storage, plugin=plugin)

        def mock_combine_words_func(input_path, output_path):
            with open(output_path, 'w') as f:
                json.dump([{"text": "test"}], f)

        mock_combine.combine_transcript_words.side_effect = mock_combine_words_func

        # Mock _download_transcript on the service instance
        with patch.object(service, '_download_transcript', return_value="/tmp/transcript.json"):
            service.process_recall_transcript(
                transcript_id="transcript-456",
                recording_id="recording-789"
            )

        # Verify meeting was updated to completed
        update_calls = storage.update_meeting.call_args_list
        completed_updates = [
            call for call in update_calls
            if "status" in call[0][1] and call[0][1]["status"] == "completed"
        ]
        assert len(completed_updates) > 0

    @patch('meeting_transcription.services.transcript_service.combine_transcript_words')
    def test_service_uploads_plugin_outputs(self, mock_combine):
        """Test that TranscriptService uploads all plugin outputs."""
        storage = Mock(spec=MeetingStorage)
        storage.update_meeting = Mock()

        # Track all uploads
        uploaded_files = []

        def track_upload(meeting_id, filename, local_path):
            uploaded_files.append(filename)
            return f"gs://bucket/{filename}"

        storage.save_file_from_path = track_upload

        plugin = MockPlugin()
        service = TranscriptService(storage=storage, plugin=plugin)

        with tempfile.TemporaryDirectory() as temp_dir:
            transcript_file = os.path.join(temp_dir, "transcript.json")
            with open(transcript_file, 'w') as f:
                json.dump([{"word": "hello"}], f)

            def mock_combine_func(input_path, output_path):
                with open(output_path, 'w') as f:
                    json.dump([{"text": "hello"}], f)

            mock_combine.combine_transcript_words.side_effect = mock_combine_func

            service._run_pipeline(
                meeting_id="test-meeting",
                transcript_file=transcript_file,
                temp_dir=temp_dir,
                meeting_record={},
                upload_intermediate=False
            )

            # Verify files were uploaded
            assert "transcript.json" in uploaded_files
            assert "transcript_combined.json" in uploaded_files
            assert "mock_output.txt" in uploaded_files
