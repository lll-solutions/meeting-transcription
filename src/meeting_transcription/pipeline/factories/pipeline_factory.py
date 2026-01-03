"""
Pipeline Factory for creating content-specific processing pipelines.

This factory detects content type and instantiates appropriate
chunker, prompt engine, and formatter implementations.
"""

from typing import Dict, Any, Optional
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from pipeline.core import (
    PipelineConfig,
    ContentType,
)
from pipeline.chunkers import EducationalTimeBasedChunker
from pipeline.prompts import EducationalPromptEngine
from pipeline.formatters import StudyGuideFormatter


class PipelineFactory:
    """
    Factory for creating appropriate pipeline configurations.

    Determines content type and instantiates appropriate chunker,
    prompt engine, and formatter based on content type.

    Supports:
    - Educational: Time-based chunking, study guide output
    - Therapy: (future) Whole-session chunking, SOAP note output
    """

    @staticmethod
    def detect_content_type(
        metadata: Optional[Dict[str, Any]] = None,
        content_type_hint: Optional[str] = None
    ) -> ContentType:
        """
        Detect content type from metadata or explicit hint.

        Args:
            metadata: Meeting/session metadata
            content_type_hint: Explicit content type ('educational', 'therapy')

        Returns:
            ContentType enum value
        """
        # Explicit hint takes precedence
        if content_type_hint:
            hint_lower = content_type_hint.lower()
            if hint_lower == 'educational':
                return ContentType.EDUCATIONAL
            elif hint_lower == 'therapy':
                return ContentType.THERAPY
            else:
                print(f"Warning: Unknown content_type_hint '{content_type_hint}', defaulting to educational")
                return ContentType.EDUCATIONAL

        # Check metadata for indicators
        if metadata:
            # Check for therapy indicators
            if any(key in metadata for key in ['client_id', 'therapist_id', 'session_type']):
                return ContentType.THERAPY

            # Check for educational indicators
            if any(key in metadata for key in ['instructor', 'course_id', 'class_name']):
                return ContentType.EDUCATIONAL

        # Default to educational (backward compatibility)
        return ContentType.EDUCATIONAL

    @staticmethod
    def create_pipeline_config(
        content_type: ContentType = ContentType.EDUCATIONAL,
        llm_provider: str = 'vertex_ai',
        llm_model: Optional[str] = None,
        **kwargs
    ) -> PipelineConfig:
        """
        Create pipeline configuration for specified content type.

        Args:
            content_type: ContentType enum value
            llm_provider: LLM provider name ('vertex_ai', 'azure', 'openai', 'anthropic')
            llm_model: Optional model name
            **kwargs: Additional parameters for chunker

        Returns:
            PipelineConfig with appropriate components

        Raises:
            ValueError: If content_type is not supported
        """
        if content_type == ContentType.EDUCATIONAL:
            return PipelineConfig(
                content_type=ContentType.EDUCATIONAL,
                chunker_class=EducationalTimeBasedChunker,
                prompt_engine_class=EducationalPromptEngine,
                formatter_class=StudyGuideFormatter,
                chunker_params={
                    'chunk_minutes': kwargs.get('chunk_minutes', 10)
                },
                llm_provider=llm_provider,
                llm_model=llm_model,
                requires_previous_session=False,
                generate_pdf=kwargs.get('generate_pdf', True)
            )

        elif content_type == ContentType.THERAPY:
            # Therapy pipeline not yet implemented
            # When implemented, this will return:
            # PipelineConfig(
            #     content_type=ContentType.THERAPY,
            #     chunker_class=TherapyWholeSessionChunker,
            #     prompt_engine_class=TherapySOAPPromptEngine,
            #     formatter_class=SOAPNoteFormatter,
            #     ...
            # )
            raise NotImplementedError(
                "Therapy pipeline not yet implemented. "
                "Coming in Week 2 of migration plan."
            )

        else:
            raise ValueError(f"Unknown content type: {content_type}")

    @staticmethod
    def create_pipeline_from_hint(
        content_type_hint: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> PipelineConfig:
        """
        Convenience method: detect content type and create config.

        Args:
            content_type_hint: Optional explicit content type string
            metadata: Optional metadata for detection
            **kwargs: Additional parameters passed to create_pipeline_config

        Returns:
            PipelineConfig
        """
        content_type = PipelineFactory.detect_content_type(
            metadata=metadata,
            content_type_hint=content_type_hint
        )

        return PipelineFactory.create_pipeline_config(
            content_type=content_type,
            **kwargs
        )
