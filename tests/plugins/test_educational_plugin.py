"""
Tests for EducationalPlugin.
"""

import json
import os
import tempfile
from unittest.mock import patch

from meeting_transcription.plugins.educational_plugin import EducationalPlugin


class TestEducationalPlugin:
    """Tests for EducationalPlugin class."""

    def test_plugin_identity(self):
        """Test plugin identity properties."""
        plugin = EducationalPlugin()

        assert plugin.name == "educational"
        assert plugin.display_name == "Educational Class"
        assert "study guides" in plugin.description.lower()

    def test_metadata_schema(self):
        """Test metadata schema definition."""
        plugin = EducationalPlugin()
        schema = plugin.metadata_schema

        assert "instructor_name" in schema
        assert schema["instructor_name"]["type"] == "string"
        assert schema["instructor_name"]["required"] is False

        assert "course_name" in schema
        assert "session_number" in schema

    def test_settings_schema(self):
        """Test settings schema definition."""
        plugin = EducationalPlugin()
        schema = plugin.settings_schema

        assert "chunk_duration_minutes" in schema
        assert schema["chunk_duration_minutes"]["type"] == "integer"
        assert schema["chunk_duration_minutes"]["min"] == 5
        assert schema["chunk_duration_minutes"]["max"] == 30
        assert schema["chunk_duration_minutes"]["default"] == 10

        assert "summarization_depth" in schema
        assert set(schema["summarization_depth"]["options"]) == {"brief", "standard", "detailed"}

        assert "generate_pdf" in schema
        assert schema["generate_pdf"]["type"] == "boolean"

    def test_default_settings(self):
        """Test plugin initializes with default settings."""
        plugin = EducationalPlugin()

        assert plugin.chunk_duration_minutes == 10
        assert plugin.include_code_examples is True
        assert plugin.summarization_depth == "detailed"
        assert plugin.generate_pdf is True

    def test_configure_settings(self):
        """Test configure method applies settings."""
        plugin = EducationalPlugin()

        plugin.configure({
            "chunk_duration_minutes": 15,
            "summarization_depth": "brief",
            "generate_pdf": False
        })

        assert plugin.chunk_duration_minutes == 15
        assert plugin.summarization_depth == "brief"
        assert plugin.generate_pdf is False

    def test_configure_partial_settings(self):
        """Test configure with partial settings uses defaults."""
        plugin = EducationalPlugin()

        plugin.configure({
            "chunk_duration_minutes": 20
        })

        assert plugin.chunk_duration_minutes == 20
        assert plugin.include_code_examples is True  # Default
        assert plugin.summarization_depth == "detailed"  # Default

    @patch('meeting_transcription.plugins.educational_plugin.create_educational_chunks')
    @patch('meeting_transcription.plugins.educational_plugin.summarize_educational_content')
    @patch('meeting_transcription.plugins.educational_plugin.create_study_guide')
    @patch('meeting_transcription.plugins.educational_plugin.markdown_to_pdf')
    def test_process_transcript_success(
        self,
        mock_pdf,
        mock_study_guide,
        mock_summarize,
        mock_chunks
    ):
        """Test process_transcript executes pipeline successfully."""
        plugin = EducationalPlugin()

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock combined transcript
            combined_path = os.path.join(temp_dir, "combined.json")
            with open(combined_path, 'w') as f:
                json.dump([
                    {"speaker": "Instructor", "text": "Hello class", "start_timestamp": {"relative": 0}}
                ], f)

            # Mock pipeline functions to create expected files
            def mock_create_chunks(input_path, output_path, **kwargs):
                with open(output_path, 'w') as f:
                    json.dump({"metadata": {}, "chunks": []}, f)

            def mock_create_summary(input_path, output_path, **kwargs):
                with open(output_path, 'w') as f:
                    json.dump({"summary": "test"}, f)

            def mock_create_guide(input_path, output_path):
                with open(output_path, 'w') as f:
                    f.write("# Study Guide")

            def mock_create_pdf(input_path, output_path):
                with open(output_path, 'wb') as f:
                    f.write(b"PDF content")

            mock_chunks.create_educational_content_chunks.side_effect = mock_create_chunks
            mock_summarize.summarize_educational_content.side_effect = mock_create_summary
            mock_study_guide.create_markdown_study_guide.side_effect = mock_create_guide
            mock_pdf.convert_markdown_to_pdf.side_effect = mock_create_pdf

            # Process transcript
            outputs = plugin.process_transcript(
                combined_transcript_path=combined_path,
                output_dir=temp_dir,
                llm_provider="vertex_ai",
                metadata={"instructor_name": "Test Instructor"}
            )

            # Verify outputs
            assert "chunks" in outputs
            assert "summary" in outputs
            assert "study_guide_md" in outputs
            assert "study_guide_pdf" in outputs

            # Verify files exist
            assert os.path.exists(outputs["chunks"])
            assert os.path.exists(outputs["summary"])
            assert os.path.exists(outputs["study_guide_md"])
            assert os.path.exists(outputs["study_guide_pdf"])

    @patch('meeting_transcription.plugins.educational_plugin.create_educational_chunks')
    @patch('meeting_transcription.plugins.educational_plugin.summarize_educational_content')
    @patch('meeting_transcription.plugins.educational_plugin.create_study_guide')
    @patch('meeting_transcription.plugins.educational_plugin.markdown_to_pdf')
    def test_process_transcript_pdf_disabled(
        self,
        mock_pdf,
        mock_study_guide,
        mock_summarize,
        mock_chunks
    ):
        """Test process_transcript skips PDF when disabled."""
        plugin = EducationalPlugin()
        plugin.configure({"generate_pdf": False})

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock combined transcript
            combined_path = os.path.join(temp_dir, "combined.json")
            with open(combined_path, 'w') as f:
                json.dump([{"speaker": "Instructor", "text": "Hello"}], f)

            # Mock pipeline functions
            def mock_create_chunks(input_path, output_path, **kwargs):
                with open(output_path, 'w') as f:
                    json.dump({"metadata": {}, "chunks": []}, f)

            def mock_create_summary(input_path, output_path, **kwargs):
                with open(output_path, 'w') as f:
                    json.dump({"summary": "test"}, f)

            def mock_create_guide(input_path, output_path):
                with open(output_path, 'w') as f:
                    f.write("# Study Guide")

            mock_chunks.create_educational_content_chunks.side_effect = mock_create_chunks
            mock_summarize.summarize_educational_content.side_effect = mock_create_summary
            mock_study_guide.create_markdown_study_guide.side_effect = mock_create_guide

            # Process transcript
            outputs = plugin.process_transcript(
                combined_transcript_path=combined_path,
                output_dir=temp_dir,
                llm_provider="vertex_ai",
                metadata={}
            )

            # Verify PDF not in outputs
            assert "study_guide_pdf" not in outputs

            # Verify PDF conversion was not called
            mock_pdf.convert_markdown_to_pdf.assert_not_called()

    @patch('meeting_transcription.plugins.educational_plugin.create_educational_chunks')
    @patch('meeting_transcription.plugins.educational_plugin.summarize_educational_content')
    @patch('meeting_transcription.plugins.educational_plugin.create_study_guide')
    @patch('meeting_transcription.plugins.educational_plugin.markdown_to_pdf')
    def test_process_transcript_uses_configured_chunk_duration(
        self,
        mock_pdf,
        mock_study_guide,
        mock_summarize,
        mock_chunks
    ):
        """Test process_transcript uses configured chunk duration."""
        plugin = EducationalPlugin()
        plugin.configure({"chunk_duration_minutes": 20})

        with tempfile.TemporaryDirectory() as temp_dir:
            combined_path = os.path.join(temp_dir, "combined.json")
            with open(combined_path, 'w') as f:
                json.dump([{"speaker": "Instructor", "text": "Hello"}], f)

            def mock_create_chunks(input_path, output_path, **kwargs):
                with open(output_path, 'w') as f:
                    json.dump({"metadata": {}, "chunks": []}, f)

            def mock_create_summary(input_path, output_path, **kwargs):
                with open(output_path, 'w') as f:
                    json.dump({"summary": "test"}, f)

            def mock_create_guide(input_path, output_path):
                with open(output_path, 'w') as f:
                    f.write("# Study Guide")

            mock_chunks.create_educational_content_chunks.side_effect = mock_create_chunks
            mock_summarize.summarize_educational_content.side_effect = mock_create_summary
            mock_study_guide.create_markdown_study_guide.side_effect = mock_create_guide

            plugin.process_transcript(
                combined_transcript_path=combined_path,
                output_dir=temp_dir,
                llm_provider="vertex_ai",
                metadata={}
            )

            # Verify chunk_minutes parameter
            mock_chunks.create_educational_content_chunks.assert_called_once()
            call_kwargs = mock_chunks.create_educational_content_chunks.call_args[1]
            assert call_kwargs["chunk_minutes"] == 20
