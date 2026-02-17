"""
Provider registry for managing transcript providers.

Handles provider registration, discovery, and retrieval based on
environment configuration.
"""

import os

from .base import ProviderType, TranscriptProvider


class ProviderRegistry:
    """Central registry for managing transcript providers."""

    def __init__(self):
        """Initialize empty provider registry."""
        self._providers: dict[ProviderType, type[TranscriptProvider]] = {}
        self._instances: dict[ProviderType, TranscriptProvider] = {}

    def register(self, provider_class: type[TranscriptProvider]) -> None:
        """
        Register a provider class.

        Args:
            provider_class: Provider class implementing TranscriptProvider

        Raises:
            ValueError: If provider type is already registered
        """
        # Create a temporary instance to get the provider_type
        # This is safe because __init__ shouldn't have side effects
        object.__new__(provider_class)
        if hasattr(provider_class, 'provider_type') and isinstance(
            provider_class.provider_type, property
        ):
            # For classes with provider_type as a property
            provider_type = provider_class.__dict__.get('_provider_type')
            if provider_type is None:
                # Try to get from class attribute
                for attr in ['provider_type', '_provider_type']:
                    val = getattr(provider_class, attr, None)
                    if isinstance(val, ProviderType):
                        provider_type = val
                        break
        else:
            provider_type = getattr(provider_class, 'provider_type', None)

        if provider_type is None:
            raise ValueError(
                f"Provider class {provider_class.__name__} must define provider_type"
            )

        if provider_type in self._providers:
            existing = self._providers[provider_type]
            raise ValueError(
                f"Provider type '{provider_type.value}' is already registered "
                f"to {existing.__name__}. Cannot register {provider_class.__name__}."
            )

        self._providers[provider_type] = provider_class
        print(f"✅ Registered provider: {provider_class.__name__} ({provider_type.value})")

    def get(self, provider_type: ProviderType | str) -> TranscriptProvider:
        """
        Get a provider instance by type.

        Args:
            provider_type: Provider type enum or string value

        Returns:
            TranscriptProvider: Provider instance (singleton per type)

        Raises:
            ValueError: If provider type not found
        """
        # Convert string to ProviderType if needed
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type)
            except ValueError:
                available = ', '.join(p.value for p in self._providers)
                raise ValueError(
                    f"Unknown provider type '{provider_type}'. "
                    f"Available: {available}"
                ) from None

        if provider_type not in self._providers:
            available = ', '.join(p.value for p in self._providers)
            raise ValueError(
                f"Provider type '{provider_type.value}' not registered. "
                f"Available: {available}"
            )

        # Return cached instance or create new one
        if provider_type not in self._instances:
            provider_class = self._providers[provider_type]
            self._instances[provider_type] = provider_class()

        return self._instances[provider_type]

    def get_default(self) -> TranscriptProvider:
        """
        Get the default provider based on TRANSCRIPT_PROVIDER environment variable.

        Returns:
            TranscriptProvider: Provider instance

        Raises:
            ValueError: If configured provider not found
        """
        provider_type = os.getenv("TRANSCRIPT_PROVIDER", "recall")
        return self.get(provider_type)

    def list(self) -> list[dict[str, str]]:
        """
        List all registered providers.

        Returns:
            List of provider info dictionaries:
            [
                {
                    "type": "recall",
                    "name": "Recall.ai",
                    "class": "RecallProvider"
                }
            ]
        """
        result = []
        for provider_type, provider_class in self._providers.items():
            # Get name from class (may need instantiation)
            try:
                instance = self.get(provider_type)
                name = instance.name
            except Exception:
                name = provider_class.__name__

            result.append({
                "type": provider_type.value,
                "name": name,
                "class": provider_class.__name__
            })
        return result

    def has(self, provider_type: ProviderType | str) -> bool:
        """
        Check if a provider type is registered.

        Args:
            provider_type: Provider type enum or string value

        Returns:
            bool: True if provider is registered
        """
        if isinstance(provider_type, str):
            try:
                provider_type = ProviderType(provider_type)
            except ValueError:
                return False

        return provider_type in self._providers

    def unregister(self, provider_type: ProviderType) -> None:
        """
        Unregister a provider.

        Args:
            provider_type: Provider type to unregister

        Raises:
            ValueError: If provider not found
        """
        if provider_type not in self._providers:
            raise ValueError(f"Provider type '{provider_type.value}' not registered")

        provider_class = self._providers.pop(provider_type)
        self._instances.pop(provider_type, None)
        print(f"❌ Unregistered provider: {provider_class.__name__} ({provider_type.value})")


# Global registry instance
_registry = ProviderRegistry()


# Convenience functions for global registry
def register_provider(provider_class: type[TranscriptProvider]) -> None:
    """Register a provider class in the global registry."""
    _registry.register(provider_class)


def get_provider(provider_type: ProviderType | str | None = None) -> TranscriptProvider:
    """
    Get a provider from the global registry.

    Args:
        provider_type: Provider type (uses default if None)

    Returns:
        TranscriptProvider instance
    """
    if provider_type is None:
        return _registry.get_default()
    return _registry.get(provider_type)


def list_providers() -> list[dict[str, str]]:
    """List all providers in the global registry."""
    return _registry.list()


def has_provider(provider_type: ProviderType | str) -> bool:
    """Check if a provider is registered in the global registry."""
    return _registry.has(provider_type)


def get_registry() -> ProviderRegistry:
    """Get the global registry instance."""
    return _registry
