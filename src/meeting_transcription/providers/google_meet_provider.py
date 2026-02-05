"""
Google Meet transcript provider (stub).

This provider will integrate directly with Google Meet's API
for meeting recordings and transcripts.

Implementation pending Epic 1: Google Meet Integration.
"""

from typing import Any

from .base import ProviderType, TranscriptProvider


class GoogleMeetProvider(TranscriptProvider):
    """
    Transcript provider using Google Meet's native API.

    This is a stub implementation. The full integration will be
    implemented as part of Epic 1: Google Meet Integration.

    The provider will:
    - Use Google Calendar API to access meeting recordings
    - Use Google Drive API to fetch recordings and transcripts
    - Support OAuth2 authentication for user consent
    """

    _provider_type = ProviderType.GOOGLE_MEET

    def __init__(self):
        """Initialize the Google Meet provider."""
        pass

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "Google Meet"

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        return ProviderType.GOOGLE_MEET

    async def create_meeting(self, meeting_url: str, **kwargs) -> str:
        """
        Register a Google Meet meeting for transcript retrieval.

        Not yet implemented - will be added in Epic 1.

        Args:
            meeting_url: Google Meet URL
            **kwargs: Additional options

        Raises:
            NotImplementedError: Always (stub implementation)
        """
        raise NotImplementedError(
            "Google Meet integration not yet implemented. "
            "See Epic 1: Google Meet Integration for roadmap."
        )

    async def get_transcript(self, meeting_id: str) -> dict[str, Any]:
        """
        Fetch transcript from Google Meet/Drive.

        Not yet implemented - will be added in Epic 1.

        Args:
            meeting_id: Meeting identifier

        Raises:
            NotImplementedError: Always (stub implementation)
        """
        raise NotImplementedError(
            "Google Meet integration not yet implemented. "
            "See Epic 1: Google Meet Integration for roadmap."
        )

    async def get_status(self, meeting_id: str) -> str:
        """
        Get meeting status.

        Not yet implemented - will be added in Epic 1.

        Args:
            meeting_id: Meeting identifier

        Raises:
            NotImplementedError: Always (stub implementation)
        """
        raise NotImplementedError(
            "Google Meet integration not yet implemented. "
            "See Epic 1: Google Meet Integration for roadmap."
        )
