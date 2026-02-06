"""
Tests for plugin registry.
"""

import pytest
from meeting_transcription.plugins import (
    PluginRegistry,
    get_plugin,
    get_registry,
    has_plugin,
    list_plugins,
    register_plugin,
)


class MockPlugin:
    """Mock plugin for testing."""

    @property
    def name(self):
        return "mock"

    @property
    def display_name(self):
        return "Mock Plugin"

    @property
    def description(self):
        return "A mock plugin for testing"

    @property
    def metadata_schema(self):
        return {}

    @property
    def settings_schema(self):
        return {}

    def configure(self, settings):
        pass

    def process_transcript(self, combined_transcript_path, output_dir, llm_provider, metadata):
        return {"mock_output": "/tmp/mock.txt"}


class TestPluginRegistry:
    """Tests for PluginRegistry class."""

    def test_register_plugin(self):
        """Test registering a plugin."""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)

        assert registry.has("mock")
        assert registry.get("mock") is plugin

    def test_register_duplicate_plugin_raises_error(self):
        """Test that registering duplicate plugin raises ValueError."""
        registry = PluginRegistry()
        plugin1 = MockPlugin()
        plugin2 = MockPlugin()

        registry.register(plugin1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(plugin2)

    def test_get_nonexistent_plugin_raises_error(self):
        """Test that getting nonexistent plugin raises ValueError."""
        registry = PluginRegistry()

        with pytest.raises(ValueError, match="not found"):
            registry.get("nonexistent")

    def test_list_plugins(self):
        """Test listing registered plugins."""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)

        plugins_list = registry.list()

        assert len(plugins_list) == 1
        assert plugins_list[0]["name"] == "mock"
        assert plugins_list[0]["display_name"] == "Mock Plugin"
        assert plugins_list[0]["description"] == "A mock plugin for testing"

    def test_has_plugin(self):
        """Test checking if plugin exists."""
        registry = PluginRegistry()
        plugin = MockPlugin()

        assert not registry.has("mock")

        registry.register(plugin)

        assert registry.has("mock")
        assert not registry.has("nonexistent")

    def test_unregister_plugin(self):
        """Test unregistering a plugin."""
        registry = PluginRegistry()
        plugin = MockPlugin()

        registry.register(plugin)
        assert registry.has("mock")

        registry.unregister("mock")
        assert not registry.has("mock")

    def test_unregister_nonexistent_plugin_raises_error(self):
        """Test that unregistering nonexistent plugin raises ValueError."""
        registry = PluginRegistry()

        with pytest.raises(ValueError, match="not found"):
            registry.unregister("nonexistent")


class TestGlobalRegistryFunctions:
    """Tests for global registry convenience functions."""

    def setup_method(self):
        """Clear global registry before each test."""
        # Clear the global registry
        registry = get_registry()
        for plugin_name in list(registry._plugins.keys()):
            registry.unregister(plugin_name)

    def test_register_and_get_plugin(self):
        """Test global register and get functions."""
        plugin = MockPlugin()

        register_plugin(plugin)

        assert has_plugin("mock")
        assert get_plugin("mock") is plugin

    def test_list_plugins_global(self):
        """Test global list function."""
        plugin = MockPlugin()

        register_plugin(plugin)

        plugins_list = list_plugins()

        assert len(plugins_list) == 1
        assert plugins_list[0]["name"] == "mock"

    def test_get_registry_returns_singleton(self):
        """Test that get_registry returns the same instance."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2
