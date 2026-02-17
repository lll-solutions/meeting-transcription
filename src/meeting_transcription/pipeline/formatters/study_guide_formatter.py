"""
Study guide formatter for educational content.

This formatter wraps the existing create_study_guide and markdown_to_pdf
implementations, maintaining 100% backward compatibility while conforming
to the BaseFormatter interface.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from pipeline import create_study_guide, markdown_to_pdf
from pipeline.core import BaseFormatter


class StudyGuideFormatter(BaseFormatter):
    """
    Formatter for educational content study guides.

    Delegates to existing create_study_guide.py and markdown_to_pdf.py
    to maintain backward compatibility while providing the BaseFormatter interface.

    Produces:
    - Markdown study guide
    - PDF study guide (optional)
    """

    def __init__(self, generate_pdf: bool = True):
        """
        Initialize study guide formatter.

        Args:
            generate_pdf: Whether to generate PDF version (default: True)
        """
        self.generate_pdf = generate_pdf

    def format_output(
        self,
        summary_data: dict[str, Any],
        output_dir: Path
    ) -> dict[str, str]:
        """
        Format educational summary into study guide (Markdown and optional PDF).

        This method delegates to the existing create_study_guide and markdown_to_pdf
        modules to maintain 100% backward compatibility with the current educational
        pipeline.

        Args:
            summary_data: Dict with:
                - 'metadata': ChunkMetadata
                - 'overall_summary': Dict from LLM
                - 'action_items': Dict from LLM
                - 'chunk_analyses': List of chunk analyses
            output_dir: Directory to write output files

        Returns:
            Dict mapping output names to file paths:
                - 'study_guide_md': path to markdown file
                - 'study_guide_pdf': path to PDF file (if generate_pdf=True)
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        outputs = {}

        # Save summary data as JSON (needed by create_study_guide)
        summary_json_path = output_dir / "summary.json"
        with open(summary_json_path, 'w') as f:
            # Convert metadata to dict for JSON serialization
            summary_copy = summary_data.copy()
            if 'metadata' in summary_copy:
                metadata = summary_copy['metadata']
                summary_copy['metadata'] = {
                    'content_type': str(metadata.content_type),
                    'chunk_strategy': str(metadata.chunk_strategy),
                    'total_chunks': metadata.total_chunks,
                    'meeting_duration_minutes': metadata.total_duration_minutes,
                    **metadata.additional_metadata
                }
            json.dump(summary_copy, f, indent=2)

        # Generate markdown study guide (existing function)
        md_path = output_dir / "study_guide.md"
        create_study_guide.create_markdown_study_guide(
            str(summary_json_path),
            str(md_path)
        )
        outputs['study_guide_md'] = str(md_path)

        # Generate PDF if requested (existing function)
        if self.generate_pdf:
            try:
                pdf_path = output_dir / "study_guide.pdf"
                markdown_to_pdf.convert_markdown_to_pdf(
                    str(md_path),
                    str(pdf_path)
                )
                outputs['study_guide_pdf'] = str(pdf_path)
            except Exception as e:
                print(f"Warning: Failed to generate PDF: {e}")
                # PDF generation is optional, continue without it

        return outputs

    def get_output_types(self) -> list[str]:
        """
        Return list of output types this formatter produces.

        Returns:
            List of output type names
        """
        types = ['study_guide_md']
        if self.generate_pdf:
            types.append('study_guide_pdf')
        return types
