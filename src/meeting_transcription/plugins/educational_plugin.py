"""
Educational plugin for processing class/workshop transcripts.

Generates comprehensive study guides with:
- Key concepts and technical topics
- Q&A exchanges
- Tools/frameworks covered
- Best practices
- Code demonstrations
- Assignments
"""

import os
from typing import Any

from meeting_transcription.pipeline import (
    create_educational_chunks,
    create_study_guide,
    markdown_to_pdf,
    summarize_educational_content,
)


class EducationalPlugin:
    """Plugin for processing educational class/workshop transcripts."""

    def __init__(self):
        """Initialize educational plugin with default settings."""
        # Default settings
        self.chunk_duration_minutes = 10
        self.include_code_examples = True
        self.summarization_depth = "detailed"
        self.generate_pdf = True

    @property
    def name(self) -> str:
        """Plugin identifier."""
        return "educational"

    @property
    def display_name(self) -> str:
        """Human-readable name."""
        return "Educational Class"

    @property
    def description(self) -> str:
        """Plugin description."""
        return (
            "Generate comprehensive study guides from class recordings, workshops, "
            "and training sessions. Extracts key concepts, Q&A, code examples, "
            "and assignments."
        )

    @property
    def metadata_schema(self) -> dict[str, Any]:
        """Define metadata fields needed for educational sessions."""
        return {
            "instructor_name": {
                "type": "string",
                "required": False,
                "label": "Instructor Name",
                "description": "Name of the class instructor or workshop leader",
                "default": "Instructor"
            },
            "course_name": {
                "type": "string",
                "required": False,
                "label": "Course/Workshop Name",
                "description": "e.g., 'AI Solutions Architect Session 3'",
                "default": ""
            },
            "session_number": {
                "type": "integer",
                "required": False,
                "label": "Session Number",
                "description": "Which session in the course series (if applicable)",
                "default": None
            }
        }

    @property
    def settings_schema(self) -> dict[str, Any]:
        """Define user-configurable settings."""
        return {
            "chunk_duration_minutes": {
                "type": "integer",
                "default": 10,
                "min": 5,
                "max": 30,
                "label": "Chunk Duration (minutes)",
                "description": "How long each segment should be for detailed analysis",
                "user_configurable": True,
                "meeting_override": True
            },
            "include_code_examples": {
                "type": "boolean",
                "default": True,
                "label": "Extract Code Examples",
                "description": "Identify and extract code demonstrations from the class",
                "user_configurable": True,
                "meeting_override": False
            },
            "summarization_depth": {
                "type": "select",
                "default": "detailed",
                "options": ["brief", "standard", "detailed"],
                "label": "Summarization Depth",
                "description": (
                    "Brief = key points only, "
                    "Standard = balanced overview, "
                    "Detailed = comprehensive analysis"
                ),
                "user_configurable": True,
                "meeting_override": True
            },
            "generate_pdf": {
                "type": "boolean",
                "default": True,
                "label": "Generate PDF",
                "description": "Create PDF version of study guide (in addition to Markdown)",
                "user_configurable": True,
                "meeting_override": True
            }
        }

    def configure(self, settings: dict[str, Any]) -> None:
        """
        Apply settings to plugin instance.

        Args:
            settings: Combined user preferences and meeting overrides
        """
        self.chunk_duration_minutes = settings.get(
            'chunk_duration_minutes',
            self.chunk_duration_minutes
        )
        self.include_code_examples = settings.get(
            'include_code_examples',
            self.include_code_examples
        )
        self.summarization_depth = settings.get(
            'summarization_depth',
            self.summarization_depth
        )
        self.generate_pdf = settings.get(
            'generate_pdf',
            self.generate_pdf
        )

        print("📚 Educational plugin configured:")
        print(f"   - Chunk duration: {self.chunk_duration_minutes} minutes")
        print(f"   - Summarization depth: {self.summarization_depth}")
        print(f"   - Generate PDF: {self.generate_pdf}")

    def process_transcript(
        self,
        combined_transcript_path: str,
        output_dir: str,
        llm_provider: str,
        metadata: dict[str, Any]
    ) -> dict[str, str]:
        """
        Process educational transcript through multi-stage pipeline.

        Pipeline:
        1. Chunk transcript into time-based segments
        2. Analyze each chunk with LLM (extract concepts, Q&A, etc.)
        3. Consolidate and deduplicate across all chunks
        4. Extract action items and assignments
        5. Format as study guide (Markdown)
        6. Generate PDF (optional)

        Args:
            combined_transcript_path: Path to combined transcript JSON
            output_dir: Directory to write outputs
            llm_provider: LLM to use ('vertex_ai', 'anthropic', etc.)
            metadata: Meeting metadata (instructor_name, course_name, etc.)

        Returns:
            Dict of output file paths
        """
        outputs = {}

        # Step 1: Create educational chunks
        print(f"📦 Creating educational chunks ({self.chunk_duration_minutes} min each)...")
        chunks_path = os.path.join(output_dir, "transcript_chunks.json")
        create_educational_chunks.create_educational_content_chunks(
            combined_transcript_path,
            chunks_path,
            chunk_minutes=self.chunk_duration_minutes
        )
        outputs["chunks"] = chunks_path

        # Step 2: Multi-stage LLM summarization with deduplication
        print("🤖 Generating AI summary (multi-stage with deduplication)...")
        summary_path = os.path.join(output_dir, "summary.json")
        summarize_educational_content.summarize_educational_content(
            chunks_path,
            summary_path,
            provider=llm_provider
        )
        # Note: This internally does:
        # - Analyze each chunk (N LLM calls)
        # - Consolidate + deduplicate (1 LLM call with OVERALL_SUMMARY_PROMPT)
        # - Extract action items (1 LLM call)
        outputs["summary"] = summary_path

        # Step 3: Create study guide (Markdown)
        print("📚 Creating study guide...")
        study_guide_md = os.path.join(output_dir, "study_guide.md")
        create_study_guide.create_markdown_study_guide(summary_path, study_guide_md)
        outputs["study_guide_md"] = study_guide_md

        # Step 4: Generate PDF (optional)
        if self.generate_pdf:
            print("📄 Generating PDF...")
            study_guide_pdf = os.path.join(output_dir, "study_guide.pdf")
            try:
                markdown_to_pdf.convert_markdown_to_pdf(study_guide_md, study_guide_pdf)
                outputs["study_guide_pdf"] = study_guide_pdf
            except Exception as e:
                print(f"⚠️ PDF generation failed (non-fatal): {e}")

        return outputs
