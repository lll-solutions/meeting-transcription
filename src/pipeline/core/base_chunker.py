from abc import ABC, abstractmethod
from typing import List, Dict, Any
from dataclasses import dataclass

from .types import ContentType, ChunkStrategy


@dataclass
class ChunkMetadata:
    """Metadata about the chunking process"""
    content_type: ContentType
    chunk_strategy: ChunkStrategy
    total_chunks: int
    total_duration_minutes: int
    additional_metadata: Dict[str, Any]


class BaseChunker(ABC):
    """
    Abstract base class for transcript chunking strategies.

    Different content types may require different chunking approaches:
    - Educational: Time-based chunks (10-min windows)
    - Therapy: Whole session (single chunk)
    - Podcast: Topic-based chunks (future)

    This interface allows pluggable chunking strategies while maintaining
    consistent pipeline structure.
    """

    @abstractmethod
    def chunk_transcript(
        self,
        combined_transcript: List[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chunk a combined transcript into processing units.

        Args:
            combined_transcript: List of transcript segments with speaker/text/timestamps
                Each segment format:
                {
                    'participant': {'name': str},
                    'text': str,
                    'word_count': int,
                    'start_timestamp': {'relative': float},
                    'end_timestamp': {'relative': float}
                }
            **kwargs: Chunker-specific parameters

        Returns:
            Dict with:
                - 'metadata': ChunkMetadata instance
                - 'chunks': List of chunk dictionaries
        """
        pass

    @abstractmethod
    def get_chunk_count(self) -> int:
        """
        Return number of chunks that will be created.

        Returns:
            int: Number of chunks
        """
        pass
