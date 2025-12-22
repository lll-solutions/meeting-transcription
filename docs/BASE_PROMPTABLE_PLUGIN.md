# BasePromptablePlugin Architecture

## Overview

`BasePromptablePlugin` is a base class for plugins that use single-pass LLM structured extraction. It handles all the orchestration, allowing subclasses to focus on domain-specific prompts and output formatting.

## Files Created

```
meeting-transcription/src/
├── utils/
│   └── llm_client.py              # LLM provider abstraction
├── pipeline/
│   ├── core/
│   │   └── base_promptable_plugin.py  # Base plugin class
│   └── chunkers/
│       └── whole_meeting_chunker.py   # Whole-meeting chunking strategy
```

## Architecture

### 1. LLMClient (`src/utils/llm_client.py`)

Unified interface for calling LLM providers:

```python
from src.utils.llm_client import LLMClient

# Initialize
client = LLMClient(provider='vertex_ai')  # or 'anthropic', 'openai', 'azure_openai'

# Simple text call
response = client.call(prompt="Analyze this...", max_tokens=4096)

# Structured output
response_dict = client.call_structured(
    prompt="Extract data...",
    response_schema={"type": "object", "properties": {...}},
    max_tokens=8000
)
```

**Supported Providers:**
- `vertex_ai` - Google Vertex AI (Gemini)
- `anthropic` - Anthropic (Claude) with tool calling
- `openai` - OpenAI API (GPT-4)
- `azure_openai` - Azure OpenAI

### 2. BasePromptablePlugin (`src/pipeline/core/base_promptable_plugin.py`)

Base class implementing the full pipeline:

**Pipeline Steps:**
1. Load combined transcript JSON
2. Chunk transcript (default: whole meeting)
3. Format transcript for LLM prompt
4. Get extraction prompt from subclass
5. Call LLM with provider abstraction
6. Parse and validate response
7. Call subclass to create output files

**Subclass Must Implement:**

```python
from src.pipeline.core import BasePromptablePlugin

class MyPlugin(BasePromptablePlugin):
    def get_extraction_prompt(self, transcript_text: str, metadata: Dict) -> str:
        """Return the LLM extraction prompt."""
        return f"Extract info from: {transcript_text}"

    def process_llm_response(
        self,
        llm_response: Dict[str, Any],
        output_dir: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, str]:
        """Format LLM response into output files."""
        # Create files from llm_response
        return {"output_file": "/path/to/file"}
```

**Optional Overrides:**

```python
def get_response_schema(self) -> Optional[Dict]:
    """Return JSON schema for structured outputs."""
    return {"type": "object", "properties": {...}}

def get_chunker(self):
    """Override chunking strategy."""
    from src.pipeline.chunkers import WholeMeetingChunker
    return WholeMeetingChunker()

def get_max_tokens(self) -> int:
    """Override max tokens (default: 8000)."""
    return 10000

def get_temperature(self) -> float:
    """Override temperature (default: 0.7)."""
    return 0.3
```

### 3. WholeMeetingChunker (`src/pipeline/chunkers/whole_meeting_chunker.py`)

Processes entire transcript as a single chunk.

**Best for:**
- Therapy sessions (SOAP note generation)
- Legal depositions (complete context needed)
- Short meetings (<1 hour)

## Usage Example: Therapy Plugin

**Before (260 lines):**
```python
class TherapyPlugin:
    def process_transcript(self, ...):
        # Load transcript
        # Chunk manually
        # Format for prompt
        # TODO: Call LLM (not implemented!)
        # Create placeholder response
        # Format outputs
        return outputs
```

**After (~80 lines):**
```python
from src.pipeline.core import BasePromptablePlugin

class TherapyPlugin(BasePromptablePlugin):
    @property
    def name(self) -> str:
        return "therapy"

    # ... metadata and settings schemas ...

    def get_extraction_prompt(self, transcript_text: str, metadata: Dict) -> str:
        """Use TherapyPromptsEngine to generate SOAP extraction prompt."""
        return self.prompts_engine.get_chunk_analysis_prompt().format(
            transcript=transcript_text
        )

    def get_response_schema(self) -> Dict:
        """Define expected JSON structure for SOAP note."""
        return {
            "type": "object",
            "properties": {
                "subjective": {"type": "string"},
                "objective": {"type": "string"},
                "assessment": {"type": "string"},
                "plan": {"type": "string"},
                "risk_assessment": {"type": "string"}
            },
            "required": ["subjective", "objective", "assessment", "plan"]
        }

    def process_llm_response(
        self,
        llm_response: Dict,
        output_dir: str,
        metadata: Dict
    ) -> Dict[str, str]:
        """Format LLM response into SOAP note and action plan files."""
        outputs = {}

        # Use existing formatters
        soap_formatter = SOAPNoteFormatter(format_type=self.soap_format)
        soap_outputs = soap_formatter.format_output(
            {'overall_summary': llm_response, 'metadata': metadata},
            output_dir
        )
        outputs["soap_note"] = soap_outputs['soap_note']

        if self.include_client_action_plan:
            action_formatter = ActionPlanFormatter()
            action_outputs = action_formatter.format_output(
                {'overall_summary': llm_response, 'metadata': metadata},
                output_dir
            )
            outputs["action_plan"] = action_outputs['action_plan']

        return outputs
```

## Benefits

✅ **LLM provider abstraction** - Switch between Vertex AI, Anthropic, OpenAI easily
✅ **Structured outputs** - Native support for JSON schema validation
✅ **Less boilerplate** - ~70% reduction in plugin code
✅ **Error handling** - JSON parsing, code block extraction built-in
✅ **Testable** - Can mock LLMClient for testing
✅ **Reusable** - Easy to create new plugins (Legal, Medical, Sales, etc.)
✅ **Flexible** - Still have full control with original TranscriptPlugin protocol

## Two Plugin Patterns

### 1. BasePromptablePlugin (Simple)
**Use for:** Single-pass LLM extraction with structured output
**Examples:** Therapy SOAP notes, Legal summaries, Meeting minutes
**Code:** ~80 lines (just prompts and formatters)

### 2. TranscriptPlugin Protocol (Advanced)
**Use for:** Complex multi-stage processing
**Examples:** Educational study guides (multi-stage with chunk analysis)
**Code:** Full control over entire pipeline

## What Goes Where

| Component | Location | Responsibility |
|-----------|----------|----------------|
| `LLMClient` | `src/utils/` | LLM provider calls and initialization |
| `BasePromptablePlugin` | `src/pipeline/core/` | Pipeline orchestration |
| `WholeMeetingChunker` | `src/pipeline/chunkers/` | Whole-meeting chunking strategy |
| `TranscriptPlugin` | `src/plugins/` | Protocol for full-control plugins |
| Domain Plugins | External repos | Domain-specific prompts and formatters |

## Environment Variables

```bash
# Vertex AI (Google Cloud)
GOOGLE_CLOUD_PROJECT=your-project
VERTEX_AI_MODEL=gemini-3-pro-preview  # optional

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022  # optional

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo  # optional

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://....openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o  # optional
AZURE_OPENAI_API_VERSION=2024-12-01-preview  # optional
```

## Next Steps

1. Update `therapy-meeting-transcription` to use `BasePromptablePlugin`
2. Test with synthetic transcript
3. Verify SOAP note generation works with real LLM
4. Consider creating more plugins (Legal, Medical, etc.)
