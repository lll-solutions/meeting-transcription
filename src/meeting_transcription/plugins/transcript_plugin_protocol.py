"""
Plugin interface for meeting transcription processing.

Defines the contract that all transcript processing plugins must implement.
"""

from typing import Any, Protocol


class TranscriptPlugin(Protocol):
    """
    Interface that all transcript processing plugins must implement.

    Plugins control the entire processing pipeline after transcript combination:
    - Chunking strategy
    - LLM orchestration (single-pass, multi-stage, etc.)
    - Output formatting
    - What gets saved
    """

    @property
    def name(self) -> str:
        """
        Plugin identifier (e.g., 'educational', 'therapy', 'legal').
        Used for registration and selection.
        """
        ...

    @property
    def display_name(self) -> str:
        """
        Human-readable name (e.g., 'Educational Class', 'Therapy Session').
        Shown in UI for plugin selection.
        """
        ...

    @property
    def description(self) -> str:
        """
        Brief description of what this plugin does.
        Shown in UI to help users choose.
        """
        ...

    @property
    def metadata_schema(self) -> dict[str, Any]:
        """
        Declare what metadata this plugin needs.

        Used to:
        - Build UI forms when creating meetings
        - Validate before processing
        - Document plugin requirements

        Returns:
            Dictionary defining metadata fields:
            {
                "field_name": {
                    "type": "string" | "integer" | "select" | "text" | "boolean",
                    "required": bool,
                    "label": "Display label",
                    "description": "Help text",
                    "default": default_value,
                    "options": [...],  # For select type
                    "validation": "regex_pattern"  # For string type
                }
            }
        """
        ...

    @property
    def settings_schema(self) -> dict[str, Any]:
        """
        Declare user-configurable settings.

        Settings can be:
        - User preferences (saved per-user)
        - Per-meeting overrides (specified at meeting creation)

        Returns:
            Dictionary defining settings:
            {
                "setting_name": {
                    "type": "string" | "integer" | "select" | "boolean",
                    "default": default_value,
                    "label": "Display label",
                    "description": "Help text",
                    "user_configurable": bool,  # Can user set in preferences?
                    "meeting_override": bool,   # Can override per-meeting?
                    "options": [...],  # For select type
                    "min": int,  # For integer type
                    "max": int   # For integer type
                }
            }
        """
        ...

    def configure(self, settings: dict[str, Any]) -> None:
        """
        Apply settings to plugin instance.

        Called before processing with combined user preferences
        and meeting-specific overrides.

        Args:
            settings: Combined settings dictionary
        """
        ...

    def process_transcript(
        self,
        combined_transcript_path: str,
        output_dir: str,
        llm_provider: str,
        metadata: dict[str, Any]
    ) -> dict[str, str]:
        """
        Process the combined transcript through domain-specific pipeline.

        Plugin has FULL control over:
        - Chunking strategy
        - LLM calling pattern (multi-stage, single-stage, etc.)
        - Output format
        - What gets saved

        Args:
            combined_transcript_path: Path to combined transcript JSON
            output_dir: Directory to write outputs
            llm_provider: Which LLM to use ('vertex_ai', 'anthropic', etc.)
            metadata: Meeting metadata (from metadata_schema)

        Returns:
            Dict of output file paths:
            {
                "summary": "/path/to/summary.json",
                "study_guide_md": "/path/to/guide.md",
                "study_guide_pdf": "/path/to/guide.pdf"
            }
        """
        ...
