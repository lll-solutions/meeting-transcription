"""
Whole Meeting Chunker

Processes entire transcript as a single chunk.
Used by plugins that need full meeting context (therapy, legal, etc.)
"""
from typing import Any

from ..core.base_chunker import BaseChunker, ChunkMetadata
from ..core.types import ChunkStrategy, ContentType


class WholeMeetingChunker(BaseChunker):
    """
    Chunks entire meeting as one unit.

    Best for:
    - Therapy sessions (SOAP note generation)
    - Legal depositions (complete context needed)
    - Short meetings (<1 hour)
    """

    def __init__(self):
        self.chunk_count = 1

    def chunk_transcript(
        self,
        combined_transcript: list[dict],
        **kwargs
    ) -> dict[str, Any]:
        """
        Process entire meeting as one chunk.

        Args:
            combined_transcript: List of transcript segments
            **kwargs: Additional metadata

        Returns:
            Dict with metadata and single-item chunks list
        """
        if not combined_transcript:
            return {
                'metadata': self._create_metadata(0, kwargs),
                'chunks': []
            }

        # Calculate meeting duration
        start_time = combined_transcript[0]['start_timestamp']['relative']
        end_time = combined_transcript[-1]['end_timestamp']['relative']
        duration_minutes = int((end_time - start_time) / 60)

        # Calculate statistics
        total_words = sum(seg.get('word_count', 0) for seg in combined_transcript)

        # Identify participants
        participants = {}
        for seg in combined_transcript:
            speaker_name = seg['participant']['name']
            if speaker_name not in participants:
                participants[speaker_name] = {
                    'name': speaker_name,
                    'is_host': seg['participant'].get('is_host', False),
                    'word_count': 0,
                    'turn_count': 0
                }
            participants[speaker_name]['word_count'] += seg.get('word_count', 0)
            participants[speaker_name]['turn_count'] += 1

        # Create single chunk with full meeting
        chunk = {
            'chunk_number': 1,
            'time_range': f"Full meeting ({duration_minutes} min)",
            'start_time': start_time,
            'end_time': end_time,
            'duration_minutes': duration_minutes,
            'segments': combined_transcript,
            'total_words': total_words,
            'participants': list(participants.values())
        }

        # Create metadata
        metadata = self._create_metadata(duration_minutes, kwargs)

        return {
            'metadata': metadata,
            'chunks': [chunk]
        }

    def _create_metadata(self, duration_minutes: int, kwargs: dict[str, Any]) -> ChunkMetadata:
        """Create chunk metadata."""
        # Allow content_type to be specified in kwargs, default to THERAPY
        content_type = kwargs.get('content_type', ContentType.THERAPY)

        return ChunkMetadata(
            content_type=content_type,
            chunk_strategy=ChunkStrategy.WHOLE_SESSION,
            total_chunks=1,
            total_duration_minutes=duration_minutes,
            additional_metadata=kwargs
        )

    def get_chunk_count(self) -> int:
        """Return number of chunks (always 1)."""
        return self.chunk_count
