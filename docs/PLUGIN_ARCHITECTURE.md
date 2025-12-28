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

Plugins are automatically registered at application startup in `main.py`:

**Built-in Plugins** (in `src/plugins/`):
```python
from src.plugins import register_builtin_plugins

# Automatically registers Educational and other built-in plugins
register_builtin_plugins()
```

**Custom Plugins** (in `plugins/` directory):
```python
from src.plugins import discover_and_register_plugins

# Automatically discovers and registers all plugins in plugins/ directory
discover_and_register_plugins()
```

Custom plugins are discovered from the `plugins/` directory at the project root. Simply create a subdirectory with your plugin code - no code changes to `main.py` required!

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

## Plugin Configuration

Plugins can be controlled via environment variables in your `.env` file:

### Environment Variables

```bash
# Enable/disable built-in plugins (default: true)
ENABLE_BUILTIN_PLUGINS=true

# Enable/disable custom plugin auto-discovery (default: true)
ENABLE_PLUGIN_DISCOVERY=true

# Disable specific plugins by name (comma-separated)
DISABLED_PLUGINS=educational,custom_plugin
```

### Configuration Examples

**Disable all custom plugins (production recommended):**
```bash
ENABLE_BUILTIN_PLUGINS=true
ENABLE_PLUGIN_DISCOVERY=false
```

**Disable educational plugin, use only custom plugins:**
```bash
ENABLE_BUILTIN_PLUGINS=true
DISABLED_PLUGINS=educational
ENABLE_PLUGIN_DISCOVERY=true
```

**Disable all plugins:**
```bash
ENABLE_BUILTIN_PLUGINS=false
ENABLE_PLUGIN_DISCOVERY=false
```

**Note**: Plugin names come from the plugin's `name` property, not the directory or filename.

## Creating a Custom Plugin

### ⚠️ Security Warning

**Custom plugins execute arbitrary Python code at application startup!**

Custom plugins have unrestricted access to:
- All environment variables (API keys, secrets)
- File system (read/write/delete files)
- Network (HTTP requests, data exfiltration)
- Application code and memory
- User data (transcripts, meetings)

**Only install plugins you wrote or fully trust. For production deployments, set `ENABLE_PLUGIN_DISCOVERY=false`.**

### Step 1: Create Plugin Directory Structure

Create a subdirectory in `plugins/` at the project root:

```
plugins/
└── my_plugin/                  # Your plugin directory name
    ├── __init__.py             # (optional) Package marker
    ├── plugin.py               # REQUIRED: defines get_plugin()
    └── my_plugin_class.py      # Your plugin implementation
```

**Important**: The `plugin.py` file with `get_plugin()` function is **required** for auto-discovery.

### Step 2: Implement Plugin Class

```python
# plugins/my_plugin/my_plugin_class.py
from src.plugins.transcript_plugin_protocol import TranscriptPlugin

class MyPlugin:
    @property
    def name(self) -> str:
        return "my_plugin"  # Used in API and DISABLED_PLUGINS

    @property
    def display_name(self) -> str:
        return "My Custom Plugin"

    @property
    def description(self) -> str:
        return "Description of what your plugin does"

    @property
    def metadata_schema(self) -> dict:
        return {}  # Define required metadata fields

    @property
    def settings_schema(self) -> dict:
        return {}  # Define user-configurable settings

    def configure(self, settings: dict) -> None:
        # Apply settings to your plugin
        pass

    def process_transcript(self, combined_path, output_dir, llm_provider, metadata):
        # Your custom processing logic
        # Return dict with output file paths
        return {
            "summary": "/path/to/summary.md",
            "output": "/path/to/output.pdf"
        }
```

### Step 3: Create Plugin Entry Point

```python
# plugins/my_plugin/plugin.py
from .my_plugin_class import MyPlugin

def get_plugin():
    """Required function that returns plugin instance."""
    return MyPlugin()
```

### Step 4: Use Plugin

That's it! On application startup, your plugin will be automatically discovered and registered. Use it via the API:

```bash
POST /api/meetings
{
    "plugin": "my_plugin",  # Uses the 'name' property
    "metadata": { ... }
}
```

To disable your plugin without deleting it:
```bash
DISABLED_PLUGINS=my_plugin
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

### Current Security Model

**⚠️ Custom plugins execute with full application privileges!**

#### Built-in Plugins
- ✅ Reviewed and maintained by core team
- ✅ Trusted execution environment
- ✅ Can be disabled via `DISABLED_PLUGINS` if not needed

#### Custom Plugins
- ❌ **No sandboxing** - Full system access
- ❌ **No code review** - Arbitrary code execution
- ❌ **No isolation** - Same process/permissions as main app

#### Security Risks
Custom plugins can:
- Read all environment variables (API keys, secrets)
- Access file system (read/write/delete)
- Make network requests (data exfiltration)
- Modify application behavior at runtime
- Access all user data and transcripts

### Recommended Security Practices

**For Production/Multi-User Deployments:**
```bash
# Disable custom plugin discovery entirely
ENABLE_PLUGIN_DISCOVERY=false

# Only use vetted built-in plugins
ENABLE_BUILTIN_PLUGINS=true
```

**For Development/Single-User:**
- Only install plugins you wrote yourself
- Fully review any third-party plugin code before installing
- Treat plugin installation like installing software on your computer

**For Shared Environments:**
- Never allow untrusted users to add plugins
- Consider `plugins/` directory as sensitive infrastructure
- Use file system permissions to restrict write access

### Future Enhancements (Planned)
The following security features are planned but **not yet implemented**:
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

**Possible causes:**

1. **Plugin discovery disabled**:
   ```bash
   # Check your .env file
   ENABLE_PLUGIN_DISCOVERY=true  # Should be true for custom plugins
   ```

2. **Plugin is disabled**:
   ```bash
   # Check DISABLED_PLUGINS in .env
   DISABLED_PLUGINS=  # Remove the plugin name from this list
   ```

3. **Missing `plugin.py` or `get_plugin()` function**:
   ```
   plugins/my_plugin/
   └── plugin.py  # Must exist and define get_plugin()
   ```
   Check startup logs for messages like:
   - `⚠️ Skipping my_plugin - no plugin.py found`
   - `❌ my_plugin/plugin.py must define a get_plugin() function`

4. **Plugin directory structure wrong**:
   ```
   # Correct structure:
   plugins/
   └── my_plugin/
       └── plugin.py

   # NOT this:
   plugins/
   └── plugin.py  # Wrong - needs to be in a subdirectory
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

**Check multiple configuration levels:**

1. **Environment variables** (`.env` file):
   ```bash
   ENABLE_BUILTIN_PLUGINS=true
   ENABLE_PLUGIN_DISCOVERY=true
   DISABLED_PLUGINS=
   ```

2. **User preferences** (Firestore):
   - Stored per-user in `plugin_settings` field
   - Must match plugin's `settings_schema`

3. **Meeting overrides** (API request):
   - Specified in `plugin_settings` when creating meeting
   - Must be compatible with plugin's settings schema

### Built-in Plugins Not Loading

If the educational plugin isn't loading:
```bash
# Check .env file
ENABLE_BUILTIN_PLUGINS=true  # Should be true
DISABLED_PLUGINS=  # Make sure 'educational' is not in this list
```

Check startup logs for:
- `📚 Built-in plugins disabled (ENABLE_BUILTIN_PLUGINS=false)`
- `⏭️ Skipped 'educational' - disabled (DISABLED_PLUGINS)`

---

For more details, see:
- [Plugin Interface](../src/plugins/transcript_plugin_protocol.py)
- [Plugin Registry](../src/plugins/plugin_registry.py)
- [Educational Plugin](../src/plugins/educational_plugin.py)
