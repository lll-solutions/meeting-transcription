"""
Plugin auto-discovery and loading system.

Automatically discovers and registers plugins from the plugins/ directory.
This allows plugins to be installed by simply copying files - no code changes needed.
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import List, Optional

from .plugin_registry import register_plugin


def _is_plugin_disabled(plugin_name: str) -> bool:
    """
    Check if a plugin is disabled via DISABLED_PLUGINS env var.

    Args:
        plugin_name: Name of the plugin to check (uses plugin.name property)

    Returns:
        True if plugin is in the disabled list, False otherwise
    """
    disabled_plugins = os.getenv('DISABLED_PLUGINS', '').strip()
    if not disabled_plugins:
        return False

    disabled_list = [p.strip().lower() for p in disabled_plugins.split(',')]
    return plugin_name.lower() in disabled_list


def discover_and_register_plugins(plugins_base_dir: Optional[str] = None) -> List[str]:
    """
    Auto-discover and register plugins from plugins/ directory.

    Controlled by ENABLE_PLUGIN_DISCOVERY environment variable (default: true).
    Individual plugins can be disabled via DISABLED_PLUGINS env var.

    Directory structure expected:
    ```
    plugins/
    ├── therapy/
    │   ├── __init__.py
    │   ├── plugin.py           (defines get_plugin() function)
    │   ├── chunkers/
    │   └── formatters/
    └── other-plugin/
        └── plugin.py
    ```

    Each plugin directory should contain a `plugin.py` file that defines
    a `get_plugin()` function returning a plugin instance.

    Args:
        plugins_base_dir: Base directory containing plugins.
                         Defaults to 'plugins/' in project root.

    Returns:
        List of registered plugin names

    Example plugin.py:
    ```python
    from .therapy_plugin import TherapyPlugin

    def get_plugin():
        return TherapyPlugin()
    ```
    """
    # Check if plugin discovery is enabled
    if os.getenv('ENABLE_PLUGIN_DISCOVERY', 'true').lower() != 'true':
        print("📦 Plugin auto-discovery disabled (ENABLE_PLUGIN_DISCOVERY=false)")
        return []

    if plugins_base_dir is None:
        # Default to plugins/ directory in project root
        # This file is in: meeting-transcription/src/plugins/plugin_loader.py
        # Project root is 2 levels up
        project_root = Path(__file__).parent.parent.parent
        plugins_base_dir = project_root / "plugins"
    else:
        plugins_base_dir = Path(plugins_base_dir)

    registered_plugins = []

    # Check if plugins directory exists
    if not plugins_base_dir.exists():
        print(f"📦 No plugins directory found at {plugins_base_dir}")
        print(f"   Create {plugins_base_dir} and add plugins to enable auto-discovery")
        return registered_plugins

    print(f"🔍 Discovering plugins in {plugins_base_dir}")
    print("⚠️  WARNING: Custom plugins execute arbitrary Python code!")
    print("   Only load plugins you wrote or fully trust.")
    print("   See plugins/README.md for security information.")
    print()

    # Iterate through directories in plugins/
    for plugin_dir in plugins_base_dir.iterdir():
        # Skip non-directories and hidden directories
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue

        # Look for plugin.py in this directory
        plugin_file = plugin_dir / "plugin.py"

        if not plugin_file.exists():
            print(f"⚠️  Skipping {plugin_dir.name} - no plugin.py found")
            continue

        # Import the plugin module
        try:
            # Add plugin directory to sys.path temporarily
            plugin_parent = str(plugin_dir.parent)
            if plugin_parent not in sys.path:
                sys.path.insert(0, plugin_parent)

            # Import plugin.py module
            module_name = f"{plugin_dir.name}.plugin"
            spec = importlib.util.spec_from_file_location(module_name, plugin_file)

            if spec is None or spec.loader is None:
                print(f"❌ Failed to load {plugin_dir.name} - invalid module spec")
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

            # Look for get_plugin() function
            if not hasattr(module, 'get_plugin'):
                print(f"❌ {plugin_dir.name}/plugin.py must define a get_plugin() function")
                continue

            # Get plugin instance
            plugin = module.get_plugin()

            # Check if plugin is disabled
            if _is_plugin_disabled(plugin.name):
                print(f"⏭️  Skipped {plugin_dir.name}/ - '{plugin.name}' is disabled (DISABLED_PLUGINS)")
                continue

            # Register the plugin
            register_plugin(plugin)
            registered_plugins.append(plugin.name)

            print(f"✅ Loaded plugin '{plugin.name}' from {plugin_dir.name}/")

        except Exception as e:
            print(f"❌ Error loading plugin from {plugin_dir.name}: {e}")
            import traceback
            traceback.print_exc()
            continue

    if registered_plugins:
        print(f"📦 Registered {len(registered_plugins)} plugin(s): {', '.join(registered_plugins)}")
    else:
        print(f"📦 No plugins found in {plugins_base_dir}")

    return registered_plugins


def register_builtin_plugins():
    """
    Register built-in plugins that come with meeting-transcription.

    Controlled by ENABLE_BUILTIN_PLUGINS environment variable (default: true).
    Individual plugins can be disabled via DISABLED_PLUGINS env var.
    """
    # Check if built-in plugins are enabled
    if os.getenv('ENABLE_BUILTIN_PLUGINS', 'true').lower() != 'true':
        print("📚 Built-in plugins disabled (ENABLE_BUILTIN_PLUGINS=false)")
        return

    from .educational_plugin import EducationalPlugin

    print("📚 Registering built-in plugins...")

    # Educational plugin
    educational = EducationalPlugin()
    if _is_plugin_disabled(educational.name):
        print(f"⏭️  Skipped '{educational.name}' - disabled (DISABLED_PLUGINS)")
    else:
        register_plugin(educational)
        print(f"✅ Registered '{educational.name}' plugin")
