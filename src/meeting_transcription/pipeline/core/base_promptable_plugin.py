"""
Base Promptable Plugin

Base class for plugins using single-pass LLM structured extraction.

Handles transcript chunking, LLM calling, and response parsing.
Subclasses implement domain-specific prompts and output formatting.
"""
import json
import os
from abc import ABC, abstractmethod
from dataclasses import asdict, is_dataclass
from typing import Any

from meeting_transcription.utils.llm_client import LLMClient


class BasePromptablePlugin(ABC):
    """Base class for single-pass LLM extraction plugins."""

    def process_transcript(
        self,
        combined_transcript_path: str,
        output_dir: str,
        metadata: dict[str, Any],
        model: str | None = None
    ) -> dict[str, str]:
        """
        Main pipeline implementation.

        1. Load and chunk transcript
        2. Format for LLM prompt
        3. Call LLM with structured extraction
        4. Save response and create output files
        """
        outputs = {}

        # Load transcript
        print("📂 Loading combined transcript...")
        with open(combined_transcript_path) as f:
            combined_transcript = json.load(f)

        # Chunk transcript
        print("📦 Chunking transcript...")
        chunker = self.get_chunker()
        chunked_data = chunker.chunk_transcript(combined_transcript, **metadata)

        # Convert ChunkMetadata dataclass to dict for JSON serialization
        chunks_to_save = {
            'metadata': asdict(chunked_data['metadata']) if is_dataclass(chunked_data['metadata']) else chunked_data['metadata'],
            'chunks': chunked_data['chunks']
        }

        chunks_path = os.path.join(output_dir, "chunks.json")
        with open(chunks_path, 'w') as f:
            json.dump(chunks_to_save, f, indent=2)
        outputs["chunks"] = chunks_path
        print(f"   Saved {len(chunked_data['chunks'])} chunks")

        # Format transcript for prompt
        print("📝 Formatting transcript for LLM...")
        transcript_text = self._format_transcript_for_prompt(chunked_data)

        # Get prompt from subclass
        print("🎯 Building extraction prompt...")
        prompt = self.get_extraction_prompt(transcript_text, metadata)

        # Call LLM (uses AI_MODEL env var if model not provided)
        print("🤖 Calling LLM...")
        llm_client = LLMClient(model=model)

        response_schema = self.get_response_schema()
        if response_schema:
            print("   Using structured output schema")
            llm_response = llm_client.call_structured(
                prompt=prompt,
                response_schema=response_schema,
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature()
            )
        else:
            print("   Using free-form text output")
            llm_response_text = llm_client.call(
                prompt=prompt,
                max_tokens=self.get_max_tokens(),
                temperature=self.get_temperature()
            )
            llm_response = self._parse_json_response(llm_response_text)

        # Save LLM response
        print("💾 Saving LLM response...")
        summary_path = os.path.join(output_dir, "summary.json")

        # Extract chunk strategy from metadata (handle both dict and dataclass)
        chunk_metadata = chunked_data.get('metadata', {})
        if is_dataclass(chunk_metadata):
            chunk_strategy = str(chunk_metadata.chunk_strategy)
        else:
            chunk_strategy = chunk_metadata.get('chunk_strategy', 'unknown')

        # Extract provider from model for logging
        provider = llm_client.model.split(":")[0] if ":" in llm_client.model else "unknown"

        summary_data = {
            'metadata': {
                **metadata,
                'chunking': {
                    'strategy': chunk_strategy,
                    'total_chunks': len(chunked_data['chunks'])
                }
            },
            'llm_response': llm_response,
            'processing_info': {
                'provider': provider,
                'model': llm_client.model,
                'chunks_processed': len(chunked_data['chunks'])
            }
        }
        with open(summary_path, 'w') as f:
            json.dump(summary_data, f, indent=2)
        outputs["summary"] = summary_path

        # Create output files via subclass
        print("📋 Formatting outputs...")
        subclass_outputs = self.process_llm_response(
            llm_response=llm_response,
            output_dir=output_dir,
            metadata=metadata
        )
        outputs.update(subclass_outputs)

        print(f"✅ Pipeline complete! Generated {len(outputs)} outputs")
        return outputs

    def _format_transcript_for_prompt(self, chunked_data: dict) -> str:
        """Format transcript chunks into text for LLM prompt."""
        lines = []
        for chunk in chunked_data['chunks']:
            for segment in chunk.get('segments', []):
                speaker = segment['participant']['name']
                text = segment['text']
                timestamp = segment['start_timestamp']['relative']
                minutes = int(timestamp // 60)
                seconds = int(timestamp % 60)
                lines.append(f"[{minutes:02d}:{seconds:02d}] {speaker}: {text}")
        return "\n".join(lines)

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        if '```json' in response:
            json_str = response.split('```json')[1].split('```')[0].strip()
        elif '```' in response:
            json_str = response.split('```')[1].split('```')[0].strip()
        else:
            json_str = response.strip()
        return json.loads(json_str)

    # ========================================================================
    # Abstract methods - subclass must implement
    # ========================================================================

    @abstractmethod
    def get_extraction_prompt(self, transcript_text: str, metadata: dict[str, Any]) -> str:
        """
        Generate the LLM extraction prompt.

        Args:
            transcript_text: Formatted transcript
            metadata: Meeting metadata

        Returns:
            Complete prompt string
        """
        pass

    @abstractmethod
    def process_llm_response(
        self,
        llm_response: dict[str, Any],
        output_dir: str,
        metadata: dict[str, Any]
    ) -> dict[str, str]:
        """
        Process LLM response into output files.

        Args:
            llm_response: Parsed JSON from LLM
            output_dir: Directory to write outputs
            metadata: Meeting metadata

        Returns:
            Dict of output file paths
        """
        pass

    # ========================================================================
    # Optional overrides
    # ========================================================================

    def get_response_schema(self) -> dict[str, Any] | None:
        """Return JSON schema for structured output (optional)."""
        return None

    def get_chunker(self):
        """Return chunker instance (default: whole meeting)."""
        from ..chunkers.whole_meeting_chunker import WholeMeetingChunker
        return WholeMeetingChunker()

    def get_max_tokens(self) -> int:
        """Return max tokens for LLM response (default: 8000)."""
        return 8000

    def get_temperature(self) -> float:
        """Return temperature for LLM sampling (default: 0.7)."""
        return 0.7
