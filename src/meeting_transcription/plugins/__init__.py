"""
Plugin system for meeting transcription processing.

Allows domain-specific processing pipelines (educational, therapy, legal, etc.)
to be plugged into the base infrastructure.
"""

from .plugin_loader import discover_and_register_plugins, register_builtin_plugins
from .plugin_registry import (
    PluginRegistry,
    get_plugin,
    get_registry,
    has_plugin,
    list_plugins,
    register_plugin,
)
from .transcript_plugin_protocol import TranscriptPlugin

__all__ = [
    'TranscriptPlugin',
    'PluginRegistry',
    'register_plugin',
    'get_plugin',
    'list_plugins',
    'has_plugin',
    'get_registry',
    'discover_and_register_plugins',
    'register_builtin_plugins'
]
