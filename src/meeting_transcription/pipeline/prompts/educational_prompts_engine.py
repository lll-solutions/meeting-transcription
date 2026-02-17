"""
Educational content prompt engine.

This prompt engine wraps the existing educational_prompts module,
maintaining 100% backward compatibility while conforming to the
BasePromptEngine interface.
"""

import json
import os
import sys
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from pipeline import educational_prompts
from pipeline.core import BasePromptEngine, PromptContext


class EducationalPromptEngine(BasePromptEngine):
    """
    Prompt engine for educational content extraction.

    Delegates to existing educational_prompts.py to maintain backward
    compatibility while providing the BasePromptEngine interface.

    Generates prompts for:
    - Chunk analysis: Extract key concepts, Q&A, best practices
    - Overall summary: Create comprehensive study guide
    - Action items: Extract assignments and homework
    """

    def create_chunk_analysis_prompt(
        self,
        chunk_data: dict[str, Any],
        context: PromptContext
    ) -> str:
        """
        Generate prompt for analyzing an educational content chunk.

        Delegates to educational_prompts.format_chunk_for_llm_analysis()

        Args:
            chunk_data: Chunk dictionary from chunker
            context: PromptContext with metadata

        Returns:
            str: Formatted prompt for LLM
        """
        instructor = context.session_metadata.get(
            'instructor',
            chunk_data.get('instructor', 'Unknown')
        )

        # Delegate to existing function
        return educational_prompts.format_chunk_for_llm_analysis(
            chunk_data,
            instructor
        )

    def create_overall_summary_prompt(
        self,
        chunk_analyses: list[dict[str, Any]],
        context: PromptContext
    ) -> str:
        """
        Generate prompt for creating overall study guide from chunk analyses.

        Delegates to educational_prompts.create_overall_summary_prompt()

        Args:
            chunk_analyses: List of analyzed chunks from LLM
            context: PromptContext with metadata

        Returns:
            str: Formatted prompt for LLM
        """
        # Convert chunk analyses to JSON strings for the prompt
        chunk_summaries = []
        for analysis in chunk_analyses:
            chunk_summaries.append(json.dumps(analysis, indent=2))

        # Build metadata dict for the existing function
        metadata = {
            'instructor': context.session_metadata.get('instructor', 'Unknown'),
            'meeting_duration_minutes': context.session_metadata.get(
                'total_duration_minutes',
                0
            ),
            'meeting_date': context.session_metadata.get('date', 'Unknown'),
            'total_participants': context.session_metadata.get('total_participants', 0)
        }

        # Delegate to existing function
        return educational_prompts.create_overall_summary_prompt(
            chunk_summaries,
            metadata
        )

    def create_action_items_prompt(
        self,
        overall_summary: dict[str, Any],
        context: PromptContext
    ) -> str:
        """
        Generate prompt for extracting action items.

        Delegates to educational_prompts.create_action_items_prompt()

        Args:
            overall_summary: Overall summary from LLM
            context: PromptContext with metadata

        Returns:
            str: Formatted prompt for LLM
        """
        # Convert summary to JSON string for the prompt
        summary_json = json.dumps(overall_summary, indent=2)

        # Delegate to existing function
        return educational_prompts.create_action_items_prompt(summary_json)

    def supports_context_injection(self) -> bool:
        """
        Educational content doesn't need previous session context.

        Returns:
            bool: False (no context injection needed)
        """
        return False
