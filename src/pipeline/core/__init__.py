"""
Core abstract base classes for modular transcript processing pipeline.

This module provides the foundational interfaces for pluggable components:
- BaseChunker: Interface for different chunking strategies
- BasePromptEngine: Interface for domain-specific prompts
- BaseFormatter: Interface for output formatting
- BasePromptablePlugin: Base class for single-pass LLM plugins
- PipelineConfig: Configuration dataclass
- ContentType, ChunkStrategy: Type-safe enums
"""

from .types import ContentType, ChunkStrategy
from .base_chunker import BaseChunker, ChunkMetadata
from .base_prompt_engine import BasePromptEngine, PromptContext
from .base_formatter import BaseFormatter
from .base_promptable_plugin import BasePromptablePlugin
from .pipeline_config import PipelineConfig

__all__ = [
    'ContentType',
    'ChunkStrategy',
    'BaseChunker',
    'ChunkMetadata',
    'BasePromptEngine',
    'PromptContext',
    'BaseFormatter',
    'BasePromptablePlugin',
    'PipelineConfig',
]
