# Custom Plugins Directory

This folder is where you can add custom plugins for domain-specific transcript processing.

## ⚠️ SECURITY WARNING

**Custom plugins execute arbitrary Python code at application startup!**

Plugins placed in this directory have unrestricted access to:
- ❌ All environment variables (API keys, database credentials, secrets)
- ❌ File system (read, write, delete any files the application can access)
- ❌ Network access (make HTTP requests, potentially exfiltrate data)
- ❌ Application code (modify behavior, install backdoors)
- ❌ User data (transcripts, meeting information, personal data)

### Only install plugins that:
✅ You wrote yourself
✅ Come from fully trusted sources
✅ You have personally reviewed all code

### For Production Deployments:
Set `ENABLE_PLUGIN_DISCOVERY=false` in your `.env` file to disable custom plugin loading.

## Plugin Structure

Place each plugin in its own subdirectory:

```
plugins/
└── my_plugin/
    ├── __init__.py          # (optional) Package marker
    ├── plugin.py            # Required: defines get_plugin() function
    └── my_plugin_class.py   # Your plugin implementation
```

See [Plugin Architecture Guide](../docs/PLUGIN_ARCHITECTURE.md) for implementation details.
