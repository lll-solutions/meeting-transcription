"""
LLM Client Utility

Unified interface for calling multiple LLM providers:
- vertex_ai: Google Vertex AI (Gemini)
- anthropic: Anthropic (Claude)
- openai: OpenAI API (GPT-4)
- azure_openai: Azure OpenAI (GPT-4)

Used by BasePromptablePlugin and educational summarization pipeline.
"""
import json
import os
from typing import Dict, Any, Optional

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Check for LLM provider availability
HAS_VERTEX_AI = False
HAS_ANTHROPIC = False
HAS_OPENAI = False

try:
    from google import genai
    from google.genai import types
    HAS_VERTEX_AI = True
except ImportError as e:
    print(f"⚠️ google.genai not available: {e}")
except Exception as e:
    print(f"❌ Error importing google.genai: {e}")

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


class LLMClient:
    """
    Unified client for calling multiple LLM providers.

    Handles provider initialization, API calls, and response parsing.

    Usage:
        client = LLMClient(provider='vertex_ai')
        response = client.call(prompt="Explain quantum physics")

        # With structured output
        response_dict = client.call_structured(
            prompt="Extract info",
            response_schema={"type": "object", ...}
        )
    """

    def __init__(self, provider: str = 'vertex_ai', model: Optional[str] = None):
        """
        Initialize LLM client with provider.

        Args:
            provider: 'vertex_ai', 'anthropic', 'openai', or 'azure_openai'
            model: Model name (optional, uses provider defaults)
        """
        self.provider = provider
        self.client = None
        self.model = model

        if provider == 'vertex_ai':
            self._init_vertex_ai(model)
        elif provider == 'anthropic':
            self._init_anthropic(model)
        elif provider == 'openai':
            self._init_openai(model)
        elif provider == 'azure_openai':
            self._init_azure_openai(model)
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                "Supported: 'vertex_ai', 'anthropic', 'openai', 'azure_openai'"
            )

    def _init_vertex_ai(self, model: Optional[str] = None):
        """Initialize Google Vertex AI (Gemini)."""
        if not HAS_VERTEX_AI:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai"
            )

        project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")

        self.client = genai.Client(vertexai=True)
        self.model = model or os.getenv("VERTEX_AI_MODEL", "gemini-3-pro-preview")

        print(f"✅ Using Vertex AI: {self.model}")
        if project:
            print(f"   Project: {project}")

    def _init_anthropic(self, model: Optional[str] = None):
        """Initialize Anthropic Claude."""
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package not installed. Run: pip install anthropic"
            )

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")

        print(f"✅ Using Anthropic: {self.model}")

    def _init_openai(self, model: Optional[str] = None):
        """Initialize OpenAI."""
        if not HAS_OPENAI:
            raise ImportError(
                "openai package not installed. Run: pip install openai"
            )

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment")

        self.client = openai.OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4-turbo")

        print(f"✅ Using OpenAI: {self.model}")

    def _init_azure_openai(self, model: Optional[str] = None):
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

    def call(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.7) -> str:
        """
        Call LLM with prompt and return text response.

        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens in response (default: 4096)
            temperature: Sampling temperature 0-1 (default: 0.7)

        Returns:
            LLM response as text string
        """
        if self.provider == 'vertex_ai':
            return self._call_vertex_ai(prompt, max_tokens, temperature)
        elif self.provider == 'anthropic':
            return self._call_anthropic(prompt, max_tokens, temperature)
        elif self.provider in ['openai', 'azure_openai']:
            return self._call_openai(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Provider {self.provider} not initialized")

    def call_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        max_tokens: int = 8000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Call LLM with prompt and return structured JSON response.

        Uses provider-specific structured output features when available.
        Falls back to JSON parsing from text response.

        Args:
            prompt: The prompt to send
            response_schema: JSON schema for expected response structure
            max_tokens: Maximum tokens in response (default: 8000)
            temperature: Sampling temperature 0-1 (default: 0.7)

        Returns:
            Parsed JSON response as dictionary
        """
        if self.provider == 'vertex_ai':
            return self._call_vertex_ai_structured(prompt, response_schema, max_tokens, temperature)
        elif self.provider == 'anthropic':
            return self._call_anthropic_structured(prompt, response_schema, max_tokens, temperature)
        elif self.provider in ['openai', 'azure_openai']:
            return self._call_openai_structured(prompt, response_schema, max_tokens, temperature)
        else:
            raise ValueError(f"Provider {self.provider} not initialized")

    def _call_vertex_ai(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call Vertex AI (Gemini) for text response."""
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]

        generation_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=generation_config
        )

        return response.text

    def _call_vertex_ai_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call Vertex AI (Gemini) for structured JSON response."""
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )
        ]

        generation_config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json"
        )

        response = self.client.models.generate_content(
            model=self.model,
            contents=contents,
            config=generation_config
        )

        return self._parse_json_response(response.text)

    def _call_anthropic(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call Anthropic Claude for text response."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text

    def _call_anthropic_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call Anthropic Claude for structured JSON response using tool calling."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=[{
                "name": "extract_structured_data",
                "description": "Extract structured data according to schema",
                "input_schema": response_schema
            }],
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract from tool use block
        for block in response.content:
            if block.type == "tool_use":
                return block.input

        # Fallback: try to parse text as JSON
        return self._parse_json_response(response.content[0].text)

    def _call_openai(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Call OpenAI or Azure OpenAI for text response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )
        return response.choices[0].message.content

    def _call_openai_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call OpenAI or Azure OpenAI for structured JSON response."""
        # Note: Azure OpenAI may not support structured outputs yet
        # Fall back to JSON mode if structured outputs not available
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception:
            # Fallback: regular call with JSON parsing
            text_response = self._call_openai(prompt, max_tokens, temperature)
            return self._parse_json_response(text_response)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling markdown code blocks.

        Args:
            response: Raw LLM response text

        Returns:
            Parsed dictionary

        Raises:
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        # Extract JSON from markdown code blocks if present
        if '```json' in response:
            json_str = response.split('```json')[1].split('```')[0].strip()
        elif '```' in response:
            json_str = response.split('```')[1].split('```')[0].strip()
        else:
            json_str = response.strip()

        return json.loads(json_str)
