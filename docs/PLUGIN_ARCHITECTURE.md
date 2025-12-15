# Plugin Architecture

The meeting-transcription system uses a plugin architecture to support domain-specific transcript processing while sharing common infrastructure (bot management, storage, auth, deployment).

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Base Infrastructure                       │
│  - Bot orchestration (Recall.ai)                            │
│  - Storage (GCS, Firestore)                                 │
│  - Auth (Firebase Auth)                                     │
│  - Deployment scripts                                        │
│  - Webhooks routing                                         │
│  - Universal preprocessing (word combining)                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  │ Selected at meeting creation
                  ▼
        ┌─────────────────────┐
        │  Plugin Registry    │
        │                     │
        │  • Educational      │ → Study guides for classes
        │  • Custom plugins   │ → Your domain-specific processing
        └─────────────────────┘
```

## Plugin Interface

All plugins implement the `TranscriptPlugin` protocol defined in `src/plugins/transcript_plugin_protocol.py`:

```python
class TranscriptPlugin(Protocol):
    # Identity
    name: str              # Plugin ID (e.g., "educational")
    display_name: str      # UI name (e.g., "Educational Class")
    description: str       # What this plugin does

    # Configuration
    metadata_schema: Dict  # What data plugin needs
    settings_schema: Dict  # User-configurable options

    # Processing
    def configure(settings: Dict) -> None
    def process_transcript(...) -> Dict[str, str]
```

## Plugin Lifecycle

### 1. Registration

Plugins are registered at application startup:

```python
from src.plugins import register_plugin
from src.plugins.educational_plugin import EducationalPlugin

# Register built-in plugins
register_plugin(EducationalPlugin())

# Custom plugins can be registered
from my_custom_plugin import CustomPlugin
register_plugin(CustomPlugin())
```

### 2. Meeting Creation

When creating a meeting, user selects a plugin:

```python
POST /api/meetings
{
    "meeting_url": "https://zoom.us/...",
    "plugin": "educational",  # Plugin selection
    "metadata": {
        "instructor_name": "Dr. Smith",
        "course_name": "Introduction to Python"
    },
    "plugin_settings": {
        "chunk_duration_minutes": 15  # Override user preference
    }
}
```

Stored in Firestore:

```json
{
    "id": "meeting-abc123",
    "meeting_url": "...",
    "plugin": "educational",
    "metadata": { ... },
    "plugin_settings": { ... }
}
```

### 3. Processing

When transcript is ready:

```python
# Webhook fires: transcript.done
meeting = get_meeting(meeting_id)
plugin_name = meeting.get('plugin', 'educational')  # Default

# Get plugin instance
plugin = get_plugin(plugin_name)

# Configure with user settings + meeting overrides
user_settings = get_user_plugin_settings(user_id, plugin_name)
meeting_settings = meeting.get('plugin_settings', {})
plugin.configure({**user_settings, **meeting_settings})

# Create service with plugin
service = TranscriptService(
    storage=storage,
    plugin=plugin,
    llm_provider='vertex_ai'
)

# Process transcript
service.process_recall_transcript(transcript_id)
```

## Pipeline Flow

### Universal Steps (Base)

1. **Download transcript** (from Recall API)
2. **Combine words** into sentences (universal preprocessing)

### Plugin-Specific Processing

Plugin takes over with full control:

```python
outputs = plugin.process_transcript(
    combined_transcript_path,  # Input
    output_dir,                # Where to write
    llm_provider,              # Which LLM to use
    metadata                   # Domain-specific metadata
)
# Returns: {"summary": "...", "study_guide_md": "...", ...}
```

### Universal Completion (Base)

3. **Upload outputs** to GCS
4. **Update meeting** status in Firestore

## Built-in Plugins

### Educational Plugin

**Purpose**: Generate study guides from class recordings

**Features**:
- Time-based chunking (5-30 minutes)
- Multi-stage LLM analysis with deduplication
- Extracts: key concepts, Q&A, code examples, assignments
- Outputs: Markdown + PDF study guides

**Metadata Schema**:
```python
{
    "instructor_name": str (optional),
    "course_name": str (optional),
    "session_number": int (optional)
}
```

**Settings Schema**:
```python
{
    "chunk_duration_minutes": int (5-30, default: 10),
    "summarization_depth": "brief" | "standard" | "detailed",
    "generate_pdf": bool (default: true)
}
```

**Pipeline**:
1. Chunk transcript (10-minute segments)
2. Analyze each chunk with LLM (N calls)
3. Consolidate + deduplicate (1 LLM call)
4. Extract action items (1 LLM call)
5. Format as study guide (Markdown + PDF)


## Configuration Levels

### 1. Plugin Defaults

Hard-coded in plugin class:

```python
class EducationalPlugin:
    def __init__(self):
        self.chunk_duration_minutes = 10  # Default
```

### 2. User Preferences

Stored in Firestore per user:

```json
{
    "user_id": "teacher@example.com",
    "plugin_settings": {
        "educational": {
            "chunk_duration_minutes": 15,
            "generate_pdf": true
        }
    }
}
```

### 3. Meeting Overrides

Specified at meeting creation:

```json
{
    "plugin_settings": {
        "chunk_duration_minutes": 20  // Just for this meeting
    }
}
```

### Priority

Meeting overrides > User preferences > Plugin defaults

## Creating a Custom Plugin

### Step 1: Implement Protocol

```python
# my_plugin.py
from src.plugins import TranscriptPlugin

class MyPlugin:
    @property
    def name(self) -> str:
        return "my_plugin"

    @property
    def display_name(self) -> str:
        return "My Custom Plugin"

    # ... implement other protocol methods

    def process_transcript(self, combined_path, output_dir, llm_provider, metadata):
        # Your custom processing logic
        return {"output": "/path/to/output.md"}
```

### Step 2: Register Plugin

```python
# main.py
from src.plugins import register_plugin
from my_plugin import MyPlugin

register_plugin(MyPlugin())
```

### Step 3: Use Plugin

```bash
POST /api/meetings
{
    "plugin": "my_plugin",
    "metadata": { ... }
}
```

## API Endpoints

### List Available Plugins

```bash
GET /api/plugins

Response:
[
    {
        "name": "educational",
        "display_name": "Educational Class",
        "description": "Generate study guides..."
    },
    {
        "name": "custom_plugin",
        "display_name": "Custom Plugin",
        "description": "Your custom processing..."
    }
]
```

### Get Plugin Details

```bash
GET /api/plugins/educational

Response:
{
    "name": "educational",
    "display_name": "Educational Class",
    "description": "...",
    "metadata_schema": { ... },
    "settings_schema": { ... }
}
```

### User Plugin Settings

```bash
# Get user's settings for a plugin
GET /api/users/me/plugin-settings/educational

# Update user's settings
PATCH /api/users/me/plugin-settings/educational
{
    "chunk_duration_minutes": 15,
    "generate_pdf": true
}
```

## Future Enhancements

### v1.1: Plugin Marketplace
- Curated, security-reviewed plugins
- Version management
- One-click installation

### v1.2: Multi-Plugin Support
- Run multiple plugins on same transcript
- Namespaced outputs
- Use case: Different analysis types on the same meeting

### v2.0: Custom GitHub Plugins
- User-provided plugins from GitHub repos
- Security validation and sandboxing
- User-specific Cloud Run services (premium feature)

## Security Considerations

### Built-in Plugins
- Reviewed and maintained by core team
- Trusted execution environment

### Future: User Plugins
- Code signing and verification
- AST parsing for forbidden patterns
- Sandbox execution (gVisor)
- Rate limiting and resource quotas
- User-specific Cloud Run services for isolation

## Testing

### Plugin Unit Tests

```python
def test_educational_plugin():
    plugin = EducationalPlugin()
    plugin.configure({"chunk_duration_minutes": 15})

    outputs = plugin.process_transcript(
        combined_path="test_data/transcript.json",
        output_dir="/tmp/test",
        llm_provider="vertex_ai",
        metadata={"instructor_name": "Test Instructor"}
    )

    assert "summary" in outputs
    assert "study_guide_md" in outputs
```

### Integration Tests

```python
def test_end_to_end_with_plugin():
    # Register test plugin
    register_plugin(TestPlugin())

    # Create meeting with plugin
    meeting = create_meeting(plugin="test_plugin")

    # Process transcript
    service = TranscriptService(storage, get_plugin("test_plugin"))
    service.process_recall_transcript(transcript_id)

    # Verify outputs
    assert meeting.status == "completed"
    assert "test_output" in meeting.outputs
```

## Troubleshooting

### Plugin Not Found

```
ValueError: Plugin 'custom_plugin' not found. Available plugins: educational
```

**Solution**: Ensure plugin is registered at startup:
```python
register_plugin(CustomPlugin())
```

### Missing Metadata

```
KeyError: 'instructor_name'
```

**Solution**: Provide required metadata when creating meeting:
```json
{
    "plugin": "educational",
    "metadata": {
        "instructor_name": "Dr. Smith",  // If required by your plugin
        "course_name": "Introduction to Python"
    }
}
```

### Configuration Issues

Check user preferences and meeting overrides are compatible with plugin's settings schema.

---

For more details, see:
- [Plugin Interface](../src/plugins/transcript_plugin_protocol.py)
- [Plugin Registry](../src/plugins/plugin_registry.py)
- [Educational Plugin](../src/plugins/educational_plugin.py)
