from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from .types import ContentType


@dataclass
class PromptContext:
    """
    Context information for prompt generation.

    This dataclass encapsulates session metadata and optional previous
    session data for continuity (particularly important for therapy sessions).
    """
    content_type: ContentType
    session_metadata: dict[str, Any]  # Meeting/session metadata
    previous_session_data: dict[str, Any] | None = None  # For therapy continuity


class BasePromptEngine(ABC):
    """
    Abstract base class for generating prompts for LLM processing.

    Different content types require different prompt structures:
    - Educational: Extract key concepts, Q&A, best practices, assignments
    - Therapy: Generate SOAP notes, assess risk, plan treatment

    This interface enables domain-specific prompt engineering while
    maintaining consistent pipeline structure.
    """

    @abstractmethod
    def create_chunk_analysis_prompt(
        self,
        chunk_data: dict[str, Any],
        context: PromptContext
    ) -> str:
        """
        Generate prompt for analyzing an individual chunk.

        Args:
            chunk_data: Chunk dictionary from chunker
            context: PromptContext with metadata and optional previous session data

        Returns:
            str: Formatted prompt for LLM
        """
        pass

    @abstractmethod
    def create_overall_summary_prompt(
        self,
        chunk_analyses: list[dict[str, Any]],
        context: PromptContext
    ) -> str:
        """
        Generate prompt for creating overall summary from chunk analyses.

        For educational content: consolidates chunk analyses into study guide.
        For therapy: creates client-facing action plan from SOAP note.

        Args:
            chunk_analyses: List of analyzed chunks from LLM
            context: PromptContext with metadata

        Returns:
            str: Formatted prompt for LLM
        """
        pass

    @abstractmethod
    def create_action_items_prompt(
        self,
        overall_summary: dict[str, Any],
        context: PromptContext
    ) -> str:
        """
        Generate prompt for extracting action items.

        For educational: extract assignments and homework.
        For therapy: extract homework assignments and follow-up tasks.

        Args:
            overall_summary: Overall summary from LLM
            context: PromptContext with metadata

        Returns:
            str: Formatted prompt for LLM
        """
        pass

    def supports_context_injection(self) -> bool:
        """
        Whether this prompt engine supports previous session context.

        Default: False
        Therapy prompt engine: True (needs previous Assessment/Plan)

        Returns:
            bool: True if context injection supported
        """
        return False
