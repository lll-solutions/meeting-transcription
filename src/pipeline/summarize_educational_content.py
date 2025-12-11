#!/usr/bin/env python3
"""
Educational content summarization pipeline using LLM.
Processes educational chunks and creates comprehensive study guides.

Supports multiple LLM providers:
- vertex_ai: Google Vertex AI (Gemini) - recommended for GCP deployment
- azure_openai: Azure OpenAI (GPT-4)
- openai: OpenAI API (GPT-4)
- anthropic: Anthropic (Claude)
"""
import json
import sys
import os
from typing import List, Dict, Any

# Import prompts - handle both direct run and module import
try:
    from . import educational_prompts as prompts
except ImportError:
    import educational_prompts as prompts

# Load environment variables from .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check for LLM providers
HAS_VERTEX_AI = False
HAS_ANTHROPIC = False
HAS_OPENAI = False

try:
    from google import genai
    from google.genai import types
    HAS_VERTEX_AI = True
except ImportError as e:
    print(f"⚠️ google.genai import failed: {e}")
    HAS_VERTEX_AI = False
except Exception as e:
    print(f"❌ Unexpected error importing google.genai: {e}")
    HAS_VERTEX_AI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    pass

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    pass


class EducationalSummarizer:
    """Summarize educational content using LLM."""

    def __init__(self, provider: str = 'vertex_ai', model: str = None):
        """
        Initialize summarizer with LLM provider.

        Args:
            provider: 'vertex_ai' (default), 'azure_openai', 'openai', or 'anthropic'
            model: Model name (optional, uses defaults)
        """
        self.provider = provider
        self.client = None
        self.model = model

        if provider == 'vertex_ai':
            self._init_vertex_ai(model)
        elif provider == 'azure_openai':
            self._init_azure_openai(model)
        elif provider == 'openai':
            self._init_openai(model)
        elif provider == 'anthropic':
            self._init_anthropic(model)
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                "Use 'vertex_ai', 'azure_openai', 'openai', or 'anthropic'"
            )

    def _init_vertex_ai(self, model: str = None):
        """Initialize Google Vertex AI (Gemini)."""
        if not HAS_VERTEX_AI:
            raise ImportError(
                "google-genai not installed. "
                "Run: pip install google-genai"
            )

        # Get project from environment or auto-detect
        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")

        # Initialize Vertex AI client
        self.client = genai.Client(vertexai=True)

        # Default to Gemini 3 Pro Preview
        self.model = model or os.getenv("VERTEX_AI_MODEL", "gemini-3-pro-preview")

        print(f"✅ Using Vertex AI: {self.model}")
        if project:
            print(f"   Project: {project}")

    def _init_azure_openai(self, model: str = None):
        """Initialize Azure OpenAI."""
        if not HAS_OPENAI:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

        if not azure_api_key or not azure_endpoint:
            raise ValueError(
                "AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT required"
            )

        self.client = openai.AzureOpenAI(
            api_key=azure_api_key,
            azure_endpoint=azure_endpoint,
            api_version=azure_api_version
        )
        self.model = model or azure_deployment or "gpt-4o"

        print(f"✅ Using Azure OpenAI: {azure_endpoint}")
        print(f"   Deployment: {self.model}")

    def _init_openai(self, model: str = None):
        """Initialize OpenAI."""
        if not HAS_OPENAI:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found")

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model or "gpt-4-turbo"

        print(f"✅ Using OpenAI: {self.model}")

    def _init_anthropic(self, model: str = None):
        """Initialize Anthropic Claude."""
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or "claude-3-5-sonnet-20241022"

        print(f"✅ Using Anthropic: {self.model}")

    def call_llm(self, prompt: str, max_tokens: int = 4096) -> str:
        """
        Call LLM with prompt.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response

        Returns:
            LLM response text
        """
        if self.provider == 'vertex_ai':
            return self._call_vertex_ai(prompt, max_tokens)
        elif self.provider == 'anthropic':
            return self._call_anthropic(prompt, max_tokens)
        elif self.provider in ['openai', 'azure_openai']:
            return self._call_openai(prompt, max_tokens)

    def _call_vertex_ai(self, prompt: str, max_tokens: int) -> str:
        """Call Vertex AI (Gemini)."""
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]

        generation_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=0.7,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=generation_config
        )

        return response.text

    def _call_anthropic(self, prompt: str, max_tokens: int) -> str:
        """Call Anthropic Claude."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _call_openai(self, prompt: str, max_tokens: int) -> str:
        """Call OpenAI or Azure OpenAI."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens
        )
        return response.choices[0].message.content

    def _parse_json_response(self, response: str) -> Dict:
        """
        Parse JSON from LLM response, handling markdown code blocks.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed dictionary
        """
        try:
            # Extract JSON from markdown code blocks if present
            if '```json' in response:
                json_str = response.split('```json')[1].split('```')[0].strip()
            elif '```' in response:
                json_str = response.split('```')[1].split('```')[0].strip()
            else:
                json_str = response.strip()

            return json.loads(json_str)

        except json.JSONDecodeError as e:
            print(f"⚠️ JSON parse error: {e}")
            return None

    def analyze_chunk(self, chunk_data: Dict, instructor: str) -> Dict:
        """
        Analyze a single educational chunk.

        Args:
            chunk_data: Chunk dictionary from educational chunks JSON
            instructor: Name of instructor

        Returns:
            Structured analysis as dictionary
        """
        chunk_num = chunk_data['chunk_number']
        time_range = chunk_data['time_range']
        print(f"   Analyzing chunk {chunk_num} ({time_range})...")

        # Format prompt
        prompt = prompts.format_chunk_for_llm_analysis(chunk_data, instructor)

        # Call LLM
        response = self.call_llm(prompt, max_tokens=4096)

        # Parse response
        analysis = self._parse_json_response(response)

        if analysis:
            analysis['chunk_number'] = chunk_num
            analysis['time_range'] = time_range
            return analysis
        else:
            # Return minimal structure on parse failure
            return {
                'chunk_number': chunk_num,
                'time_range': time_range,
                'main_theme': 'Error parsing response',
                'raw_response': response[:1000]
            }

    def create_overall_summary(
        self,
        chunk_analyses: List[Dict],
        metadata: Dict
    ) -> Dict:
        """
        Create overall summary from chunk analyses.

        Args:
            chunk_analyses: List of chunk analysis dictionaries
            metadata: Meeting metadata

        Returns:
            Overall summary dictionary
        """
        print("   Creating overall summary...")

        # Format chunk analyses as text
        chunk_summaries = [json.dumps(a, indent=2) for a in chunk_analyses]

        # Create prompt
        prompt = prompts.create_overall_summary_prompt(chunk_summaries, metadata)

        # Call LLM with larger context
        response = self.call_llm(prompt, max_tokens=8192)

        # Parse response
        summary = self._parse_json_response(response)

        if summary:
            return summary
        else:
            return {
                'error': 'Could not parse summary',
                'raw_response': response[:2000]
            }

    def extract_action_items(self, overall_summary: Dict) -> Dict:
        """
        Extract action items from overall summary.

        Args:
            overall_summary: Overall summary dictionary

        Returns:
            Action items dictionary
        """
        print("   Extracting action items...")

        prompt = prompts.create_action_items_prompt(json.dumps(overall_summary, indent=2))
        response = self.call_llm(prompt, max_tokens=2048)

        action_items = self._parse_json_response(response)

        if action_items:
            return action_items
        else:
            return {'error': 'Could not parse', 'raw_response': response[:1000]}


def summarize_educational_content(
    chunks_file: str,
    output_file: str,
    provider: str = 'vertex_ai',
    model: str = None,
    sample_chunks: int = None
):
    """
    Main function to summarize educational content.

    Args:
        chunks_file: Path to educational chunks JSON
        output_file: Path to output summary JSON
        provider: LLM provider ('vertex_ai', 'azure_openai', 'anthropic', 'openai')
        model: Model name (optional, uses defaults)
        sample_chunks: If set, only process first N chunks (for testing)
    """
    # Load chunks
    print(f"📂 Loading chunks from {chunks_file}...")
    with open(chunks_file, 'r') as f:
        data = json.load(f)

    metadata = data['metadata']
    chunks = data['chunks']

    if sample_chunks:
        print(f"⚠️ Processing only first {sample_chunks} chunks (test mode)")
        chunks = chunks[:sample_chunks]

    # Initialize summarizer
    print(f"\n🤖 Initializing {provider} LLM...")
    summarizer = EducationalSummarizer(provider=provider, model=model)

    # Analyze each chunk
    print(f"\n📊 Analyzing {len(chunks)} chunks...")
    chunk_analyses = []
    for i, chunk in enumerate(chunks, 1):
        analysis = summarizer.analyze_chunk(chunk, metadata.get('instructor', 'Unknown'))
        chunk_analyses.append(analysis)
        print(f"   ✓ Chunk {i}/{len(chunks)} complete")

    # Create overall summary
    print("\n📝 Generating summary...")
    overall_summary = summarizer.create_overall_summary(chunk_analyses, metadata)

    # Extract action items
    action_items = summarizer.extract_action_items(overall_summary)

    # Combine everything
    final_output = {
        'metadata': metadata,
        'overall_summary': overall_summary,
        'action_items': action_items,
        'chunk_analyses': chunk_analyses,
        'processing_info': {
            'provider': provider,
            'model': summarizer.model,
            'chunks_processed': len(chunks),
            'total_chunks': len(data['chunks'])
        }
    }

    # Save output
    with open(output_file, 'w') as f:
        json.dump(final_output, f, indent=2)

    print(f"\n✅ Summary saved to: {output_file}")
    print(f"\n📋 Summary Stats:")
    print(f"   • Chunks processed: {len(chunks)}")
    print(f"   • Instructor: {metadata.get('instructor', 'Unknown')}")
    print(f"   • Duration: {metadata.get('meeting_duration_minutes', 'N/A')} minutes")
    if 'class_metadata' in overall_summary:
        print(f"   • Topic: {overall_summary['class_metadata'].get('topic', 'N/A')}")

    return final_output


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("""
Usage: python summarize_educational_content.py <chunks_file> <output_file> [provider] [sample_chunks]

Providers:
  vertex_ai    - Google Vertex AI / Gemini (default, recommended for GCP)
  azure_openai - Azure OpenAI / GPT-4
  openai       - OpenAI API / GPT-4
  anthropic    - Anthropic / Claude

Examples:
  # Use Vertex AI (default)
  python summarize_educational_content.py chunks.json summary.json

  # Use Azure OpenAI
  python summarize_educational_content.py chunks.json summary.json azure_openai

  # Test with only 2 chunks
  python summarize_educational_content.py chunks.json summary.json vertex_ai 2

Environment Variables:
  Vertex AI (default):
    - GOOGLE_CLOUD_PROJECT (auto-detected on GCP)
    - GCP_REGION (default: us-central1)
    - VERTEX_AI_MODEL (default: gemini-3-pro-preview)

  Azure OpenAI:
    - AZURE_OPENAI_API_KEY
    - AZURE_OPENAI_ENDPOINT
    - AZURE_OPENAI_DEPLOYMENT

  OpenAI:
    - OPENAI_API_KEY

  Anthropic:
    - ANTHROPIC_API_KEY
""")
        sys.exit(1)

    chunks_file = sys.argv[1]
    output_file = sys.argv[2]
    provider = sys.argv[3] if len(sys.argv) > 3 else 'vertex_ai'
    sample_chunks = int(sys.argv[4]) if len(sys.argv) > 4 else None

    summarize_educational_content(
        chunks_file,
        output_file,
        provider=provider,
        sample_chunks=sample_chunks
    )
