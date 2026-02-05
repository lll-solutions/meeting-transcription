"""
Transcript provider base classes and types.

Defines the contract that all transcript providers must implement.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


class ProviderType(Enum):
    """Supported transcript provider types."""

    RECALL = "recall"
    GOOGLE_MEET = "google_meet"
    ZOOM = "zoom"
    MANUAL = "manual"


class TranscriptProvider(ABC):
    """
    Abstract base class for transcript providers.

    Providers handle the full lifecycle of meeting transcription:
    - Creating/joining meetings
    - Fetching transcripts
    - Handling provider-specific webhooks
    - Reporting status
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g., 'Recall.ai', 'Google Meet')."""
        ...

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        ...

    @abstractmethod
    async def create_meeting(self, meeting_url: str, **kwargs) -> str:
        """
        Create or register a meeting with the provider.

        Args:
            meeting_url: The meeting URL to join
            **kwargs: Provider-specific options (webhook_url, bot_name, etc.)

        Returns:
            str: Meeting ID assigned by the provider

        Raises:
            ValueError: If meeting_url is invalid
            RuntimeError: If meeting creation fails
        """
        ...

    @abstractmethod
    async def get_transcript(self, meeting_id: str) -> dict[str, Any]:
        """
        Fetch transcript data for a meeting.

        Args:
            meeting_id: The meeting ID

        Returns:
            dict: Normalized transcript data with structure:
                {
                    "segments": [
                        {
                            "speaker": "Speaker Name",
                            "text": "What they said",
                            "start_time": 0.0,
                            "end_time": 5.0
                        },
                        ...
                    ],
                    "metadata": {...}
                }

        Raises:
            RuntimeError: If transcript fetch fails
        """
        ...

    @abstractmethod
    async def get_status(self, meeting_id: str) -> str:
        """
        Get the current status of a meeting/transcript.

        Args:
            meeting_id: The meeting ID

        Returns:
            str: Status string (provider-specific, but typically:
                 'pending', 'in_meeting', 'recording', 'transcribing',
                 'completed', 'failed')
        """
        ...

    def handle_webhook(self, event: dict[str, Any]) -> str | None:
        """
        Handle a provider-specific webhook event.

        Override this method if the provider uses webhooks to notify
        about meeting/transcript events.

        Args:
            event: Webhook event payload

        Returns:
            str | None: Meeting ID if transcript is ready, None otherwise
        """
        return None

    async def leave_meeting(self, meeting_id: str) -> bool:
        """
        Leave/disconnect from a meeting.

        Override this method if the provider supports active meeting management.

        Args:
            meeting_id: The meeting ID

        Returns:
            bool: True if leave command succeeded
        """
        return False
