from dataclasses import dataclass, field
from typing import Any

from .types import ContentType


@dataclass
class PipelineConfig:
    """
    Configuration for a content processing pipeline.

    Encapsulates all components needed to process a specific content type,
    allowing the pipeline factory to instantiate appropriate implementations
    based on content type.
    """

    content_type: ContentType

    # Component classes (not instances - will be instantiated by pipeline)
    chunker_class: type  # Class implementing BaseChunker
    prompt_engine_class: type  # Class implementing BasePromptEngine
    formatter_class: type  # Class implementing BaseFormatter

    # Chunker-specific parameters
    chunker_params: dict[str, Any] = field(default_factory=dict)

    # LLM parameters
    llm_provider: str = 'vertex_ai'  # 'vertex_ai', 'azure', 'openai', 'anthropic'
    llm_model: str | None = None

    # Context injection (for therapy)
    requires_previous_session: bool = False

    # Output configuration
    generate_pdf: bool = True
