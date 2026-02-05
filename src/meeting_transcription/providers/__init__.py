"""
Transcript providers package.

Provides a pluggable provider system for different transcript sources:
- Recall.ai (bot-based recording)
- Google Meet (direct API, stub)
- Zoom (direct API, stub)
- Manual Upload (user-uploaded files)

Usage:
    from meeting_transcription.providers import get_provider, ProviderType

    # Get default provider (based on TRANSCRIPT_PROVIDER env var)
    provider = get_provider()

    # Get specific provider
    provider = get_provider(ProviderType.RECALL)
    provider = get_provider("recall")

    # Create a meeting
    meeting_id = await provider.create_meeting(meeting_url, webhook_url=url)

    # Get transcript
    transcript = await provider.get_transcript(meeting_id)
"""

from .base import ProviderType, TranscriptProvider
from .registry import (
    get_provider,
    get_registry,
    has_provider,
    list_providers,
    register_provider,
)


def register_builtin_providers() -> None:
    """Register all built-in providers."""
    from .google_meet_provider import GoogleMeetProvider
    from .manual_provider import ManualUploadProvider
    from .recall_provider import RecallProvider
    from .zoom_provider import ZoomProvider

    # Register providers (order doesn't matter)
    register_provider(RecallProvider)
    register_provider(GoogleMeetProvider)
    register_provider(ZoomProvider)
    register_provider(ManualUploadProvider)


# Auto-register built-in providers on import
register_builtin_providers()


__all__ = [
    # Types
    "ProviderType",
    "TranscriptProvider",
    # Registry functions
    "get_provider",
    "register_provider",
    "list_providers",
    "has_provider",
    "get_registry",
    # Registration
    "register_builtin_providers",
]
