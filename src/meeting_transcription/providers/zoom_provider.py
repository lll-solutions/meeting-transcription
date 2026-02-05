"""
Zoom transcript provider (stub).

This provider will integrate directly with Zoom's API
for meeting recordings and transcripts.

Implementation pending Epic 2: Zoom Integration.
"""

from typing import Any

from .base import ProviderType, TranscriptProvider


class ZoomProvider(TranscriptProvider):
    """
    Transcript provider using Zoom's native API.

    This is a stub implementation. The full integration will be
    implemented as part of Epic 2: Zoom Integration.

    The provider will:
    - Use Zoom Cloud Recordings API
    - Support OAuth2 Server-to-Server authentication
    - Handle Zoom webhooks for recording availability
    """

    _provider_type = ProviderType.ZOOM

    def __init__(self):
        """Initialize the Zoom provider."""
        pass

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "Zoom"

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        return ProviderType.ZOOM

    async def create_meeting(self, meeting_url: str, **kwargs) -> str:
        """
        Register a Zoom meeting for transcript retrieval.

        Not yet implemented - will be added in Epic 2.

        Args:
            meeting_url: Zoom meeting URL
            **kwargs: Additional options

        Raises:
            NotImplementedError: Always (stub implementation)
        """
        raise NotImplementedError(
            "Zoom integration not yet implemented. "
            "See Epic 2: Zoom Integration for roadmap."
        )

    async def get_transcript(self, meeting_id: str) -> dict[str, Any]:
        """
        Fetch transcript from Zoom Cloud Recordings.

        Not yet implemented - will be added in Epic 2.

        Args:
            meeting_id: Meeting identifier

        Raises:
            NotImplementedError: Always (stub implementation)
        """
        raise NotImplementedError(
            "Zoom integration not yet implemented. "
            "See Epic 2: Zoom Integration for roadmap."
        )

    async def get_status(self, meeting_id: str) -> str:
        """
        Get meeting/recording status.

        Not yet implemented - will be added in Epic 2.

        Args:
            meeting_id: Meeting identifier

        Raises:
            NotImplementedError: Always (stub implementation)
        """
        raise NotImplementedError(
            "Zoom integration not yet implemented. "
            "See Epic 2: Zoom Integration for roadmap."
        )
