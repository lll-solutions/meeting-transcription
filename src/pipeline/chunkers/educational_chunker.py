"""
Educational content chunker - time-based chunking strategy.

This chunker wraps the existing create_educational_chunks implementation,
maintaining 100% backward compatibility while conforming to the BaseChunker interface.
"""

from typing import List, Dict, Any
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from pipeline.core import BaseChunker, ChunkMetadata, ContentType, ChunkStrategy
from pipeline import create_educational_chunks


class EducationalTimeBasedChunker(BaseChunker):
    """
    Time-based chunking for educational content.

    Delegates to existing create_educational_chunks.py to maintain
    backward compatibility while providing the BaseChunker interface.

    Default: 10-minute chunks
    """

    def __init__(self, chunk_minutes: int = 10):
        """
        Initialize educational chunker.

        Args:
            chunk_minutes: Minutes per chunk (default: 10)
        """
        self.chunk_minutes = chunk_minutes
        self._chunk_count = 0

    def chunk_transcript(
        self,
        combined_transcript: List[Dict],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create time-based chunks using existing educational chunking logic.

        This method delegates to the existing create_educational_chunks module
        to maintain 100% backward compatibility with the current educational
        pipeline.

        Args:
            combined_transcript: List of transcript segments
            **kwargs: Additional parameters (ignored for backward compatibility)

        Returns:
            Dict with 'metadata' (ChunkMetadata) and 'chunks' (list)
        """
        if not combined_transcript:
            raise ValueError("Empty transcript provided")

        # Identify instructor (existing function from create_educational_chunks)
        instructor = create_educational_chunks.identify_instructor(combined_transcript)

        # Create chunks (existing function)
        chunks = create_educational_chunks.create_educational_chunks(
            combined_transcript,
            instructor,
            chunk_minutes=self.chunk_minutes
        )

        self._chunk_count = len(chunks)

        # Calculate metadata
        total_duration = combined_transcript[-1]['end_timestamp']['relative'] / 60

        # Get participant statistics
        participants = {}
        for segment in combined_transcript:
            name = segment['participant']['name']
            if name not in participants:
                participants[name] = {
                    'name': name,
                    'is_instructor': name == instructor,
                    'total_words': 0,
                    'total_segments': 0
                }
            participants[name]['total_words'] += segment['word_count']
            participants[name]['total_segments'] += 1

        # Build metadata
        metadata = ChunkMetadata(
            content_type=ContentType.EDUCATIONAL,
            chunk_strategy=ChunkStrategy.TIME_BASED,
            total_chunks=len(chunks),
            total_duration_minutes=int(total_duration),
            additional_metadata={
                'chunk_duration_minutes': self.chunk_minutes,
                'instructor': instructor,
                'participants': list(participants.values()),
                'total_participants': len(participants)
            }
        )

        return {
            'metadata': metadata,
            'chunks': chunks
        }

    def get_chunk_count(self) -> int:
        """
        Return number of chunks created in last chunking operation.

        Returns:
            int: Number of chunks
        """
        return self._chunk_count
