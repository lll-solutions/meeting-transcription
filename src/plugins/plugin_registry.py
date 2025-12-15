"""
Plugin registry for managing transcript processing plugins.

Handles plugin registration, discovery, and retrieval.
"""

from typing import Dict, List, Optional
from .transcript_plugin_protocol import TranscriptPlugin


class PluginRegistry:
    """Central registry for managing transcript processing plugins."""

    def __init__(self):
        """Initialize empty plugin registry."""
        self._plugins: Dict[str, TranscriptPlugin] = {}

    def register(self, plugin: TranscriptPlugin) -> None:
        """
        Register a plugin.

        Args:
            plugin: Plugin instance implementing TranscriptPlugin protocol

        Raises:
            ValueError: If plugin name is already registered
        """
        if plugin.name in self._plugins:
            raise ValueError(
                f"Plugin '{plugin.name}' is already registered. "
                f"Existing: {self._plugins[plugin.name].display_name}"
            )

        self._plugins[plugin.name] = plugin
        print(f"✅ Registered plugin: {plugin.display_name} ({plugin.name})")

    def get(self, name: str) -> TranscriptPlugin:
        """
        Get a registered plugin by name.

        Args:
            name: Plugin identifier

        Returns:
            Plugin instance

        Raises:
            ValueError: If plugin not found
        """
        if name not in self._plugins:
            available = ', '.join(self._plugins.keys())
            raise ValueError(
                f"Plugin '{name}' not found. "
                f"Available plugins: {available}"
            )

        return self._plugins[name]

    def list(self) -> List[Dict[str, str]]:
        """
        List all registered plugins.

        Returns:
            List of plugin info dictionaries:
            [
                {
                    "name": "educational",
                    "display_name": "Educational Class",
                    "description": "..."
                }
            ]
        """
        return [
            {
                "name": plugin.name,
                "display_name": plugin.display_name,
                "description": plugin.description
            }
            for plugin in self._plugins.values()
        ]

    def has(self, name: str) -> bool:
        """
        Check if a plugin is registered.

        Args:
            name: Plugin identifier

        Returns:
            True if plugin is registered
        """
        return name in self._plugins

    def unregister(self, name: str) -> None:
        """
        Unregister a plugin.

        Args:
            name: Plugin identifier

        Raises:
            ValueError: If plugin not found
        """
        if name not in self._plugins:
            raise ValueError(f"Plugin '{name}' not found")

        plugin = self._plugins.pop(name)
        print(f"❌ Unregistered plugin: {plugin.display_name} ({name})")


# Global registry instance
_registry = PluginRegistry()


# Convenience functions for global registry
def register_plugin(plugin: TranscriptPlugin) -> None:
    """Register a plugin in the global registry."""
    _registry.register(plugin)


def get_plugin(name: str) -> TranscriptPlugin:
    """Get a plugin from the global registry."""
    return _registry.get(name)


def list_plugins() -> List[Dict[str, str]]:
    """List all plugins in the global registry."""
    return _registry.list()


def has_plugin(name: str) -> bool:
    """Check if a plugin is registered in the global registry."""
    return _registry.has(name)


def get_registry() -> PluginRegistry:
    """Get the global registry instance."""
    return _registry
