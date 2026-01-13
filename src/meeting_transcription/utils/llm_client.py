"""
LLM Client using aisuite for multi-provider support.

Supports multiple providers configured via environment variables:
- OpenAI (direct or Azure): OPENAI_API_KEY, OPENAI_ENDPOINT (optional for Azure)
- Anthropic (direct or Azure): ANTHROPIC_API_KEY, ANTHROPIC_ENDPOINT (optional for Azure)
- Google Vertex AI: GOOGLE_CLOUD_PROJECT, GOOGLE_REGION

Set AI_MODEL environment variable to choose which model to use:
- AI_MODEL=google:gemini-3-pro-preview
- AI_MODEL=anthropic:claude-sonnet-4-5
- AI_MODEL=openai:gpt-4o
"""
import json
import os
from typing import Dict, Any, Optional

try:
    import aisuite as ai
    HAS_AISUITE = True
except ImportError:
    HAS_AISUITE = False
    print("⚠️ aisuite not available")


class LLMClient:
    """
    Unified client for calling multiple LLM providers via aisuite.

    Auto-configures all providers from environment variables.
    Switch models using AI_MODEL environment variable.

    Usage:
        client = LLMClient()
        response = client.call(prompt="Explain quantum physics")

        # With structured output
        response_dict = client.call_structured(
            prompt="Extract info",
            response_schema={"type": "object", ...}
        )
    """

    def __init__(self, model: Optional[str] = None):
        """
        Initialize LLM client with all configured providers.

        Args:
            model: Override AI_MODEL env var (optional)
        """
        if not HAS_AISUITE:
            raise ImportError(
                "aisuite not installed. Run: poetry add aisuite"
            )

        # Build provider configs from environment variables
        provider_configs = {}

        # Google Vertex AI
        google_project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_PROJECT_ID")
        if google_project:
            # aisuite expects specific env var names, so set them
            os.environ["GOOGLE_PROJECT_ID"] = google_project
            os.environ["GOOGLE_REGION"] = os.getenv("GOOGLE_REGION") or os.getenv("GCP_REGION", "global")

            # Get credentials path (ADC or service account)
            creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not creds_path:
                # Fall back to ADC (from gcloud auth application-default login)
                from pathlib import Path
                adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
                if adc_path.exists():
                    creds_path = str(adc_path)

            # Build config for aisuite
            provider_configs["google"] = {
                "project_id": google_project,
                "region": os.environ["GOOGLE_REGION"],
            }

            # Add credentials if we have them (skip in Cloud Run - uses default service account)
            if creds_path:
                provider_configs["google"]["application_credentials"] = creds_path

        # OpenAI (direct or Azure)
        openai_key = os.getenv("OPENAI_API_KEY")
        if openai_key:
            provider_configs["openai"] = {"api_key": openai_key}

            # Check if using Azure OpenAI
            openai_endpoint = os.getenv("OPENAI_ENDPOINT")
            if openai_endpoint:
                deployment = os.getenv("OPENAI_DEPLOYMENT", "gpt-4o")
                provider_configs["openai"]["base_url"] = f"{openai_endpoint}openai/deployments/{deployment}"
                provider_configs["openai"]["default_query"] = {
                    "api-version": os.getenv("OPENAI_API_VERSION", "2024-05-01-preview")
                }

        # Anthropic (direct or Azure)
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        if anthropic_key:
            provider_configs["anthropic"] = {"api_key": anthropic_key}

            # Check if using Azure Claude
            anthropic_endpoint = os.getenv("ANTHROPIC_ENDPOINT")
            if anthropic_endpoint:
                provider_configs["anthropic"]["base_url"] = anthropic_endpoint
                provider_configs["anthropic"]["default_headers"] = {
                    "anthropic-version": "2023-06-01"
                }

        if not provider_configs:
            raise ValueError(
                "No LLM provider configured. Set one of:\n"
                "  - GOOGLE_CLOUD_PROJECT (+ GOOGLE_REGION)\n"
                "  - OPENAI_API_KEY (+ OPENAI_ENDPOINT for Azure)\n"
                "  - ANTHROPIC_API_KEY (+ ANTHROPIC_ENDPOINT for Azure)"
            )

        # Initialize aisuite client with all configured providers
        self.client = ai.Client(provider_configs)

        # Get model from parameter or environment
        self.model = model or os.getenv("AI_MODEL", "google:gemini-3-pro-preview")

        # Print which provider/model we're using
        provider_name = self.model.split(":")[0] if ":" in self.model else "unknown"
        model_name = self.model.split(":")[1] if ":" in self.model else self.model

        emoji_map = {
            "google": "💎",
            "openai": "🤖",
            "anthropic": "🎭"
        }
        emoji = emoji_map.get(provider_name, "🔮")

        print(f"{emoji} Using {provider_name}: {model_name}")

        # Print config details
        if provider_name == "google" and "google" in provider_configs:
            print(f"   Project: {provider_configs['google']['project_id']}")
            print(f"   Region: {provider_configs['google']['region']}")
        elif provider_name == "openai" and "openai" in provider_configs:
            if "base_url" in provider_configs["openai"]:
                print(f"   Azure OpenAI: {os.getenv('OPENAI_ENDPOINT')}")
            else:
                print(f"   Direct OpenAI API")
        elif provider_name == "anthropic" and "anthropic" in provider_configs:
            if "base_url" in provider_configs["anthropic"]:
                print(f"   Azure Claude: {os.getenv('ANTHROPIC_ENDPOINT')}")
            else:
                print(f"   Direct Anthropic API")

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
        messages = [{"role": "user", "content": prompt}]

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )

        return response.choices[0].message.content

    def call_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        max_tokens: int = 8000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Call LLM with prompt and return structured JSON response.

        Args:
            prompt: The prompt to send
            response_schema: JSON schema for expected response structure
            max_tokens: Maximum tokens in response (default: 8000)
            temperature: Sampling temperature 0-1 (default: 0.7)

        Returns:
            Parsed JSON response as dictionary
        """
        # Add JSON instruction to prompt
        json_prompt = (
            f"{prompt}\n\n"
            f"Respond with valid JSON matching this schema:\n"
            f"{json.dumps(response_schema, indent=2)}"
        )

        response_text = self.call(json_prompt, max_tokens, temperature)
        return self._parse_json_response(response_text)

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
