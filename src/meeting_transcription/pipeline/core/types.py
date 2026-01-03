"""
Type definitions for the transcript processing pipeline.
"""

from enum import Enum


class ContentType(str, Enum):
    """
    Supported content types for transcript processing.

    Using str-based Enum for better JSON serialization and
    backward compatibility with existing string-based code.
    """
    EDUCATIONAL = "educational"
    THERAPY = "therapy"

    def __str__(self) -> str:
        return self.value


class ChunkStrategy(str, Enum):
    """
    Supported chunking strategies.
    """
    TIME_BASED = "time_based"
    WHOLE_SESSION = "whole_session"
    SPEAKER_BASED = "speaker_based"
    SEMANTIC = "semantic"

    def __str__(self) -> str:
        return self.value
