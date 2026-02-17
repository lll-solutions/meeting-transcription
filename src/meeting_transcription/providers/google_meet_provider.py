"""
Google Meet transcript provider.

Integrates with Google Meet's REST API for automatic transcript retrieval.
Unlike Recall.ai (bot-based), this provider works via Workspace Events
notifications and fetches transcripts after meetings end.

The provider does not "join" meetings — instead it monitors for transcript
events and auto-creates sessions when transcripts become available.
"""

from typing import Any

from .base import ProviderType, TranscriptProvider


class GoogleMeetProvider(TranscriptProvider):
    """
    Transcript provider using Google Meet's native API.

    This is an event-driven provider. It doesn't actively join meetings.
    Instead, transcripts are pushed via Workspace Events / Pub/Sub
    and processed by MeetSessionHandler.

    create_meeting() is not used in the typical flow — sessions are
    auto-created when transcript events arrive.
    """

    _provider_type = ProviderType.GOOGLE_MEET

    def __init__(self) -> None:
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

    async def create_meeting(self, meeting_url: str, **kwargs: Any) -> str:
        """
        Not applicable for Google Meet provider.

        Google Meet transcripts are received passively via Workspace Events.
        Sessions are auto-created when a transcript event arrives.

        Raises:
            NotImplementedError: Always. Use MeetSessionHandler instead.
        """
        raise NotImplementedError(
            "Google Meet provider receives transcripts automatically via "
            "Workspace Events. Sessions are created when transcripts arrive. "
            "Connect your Google account in Settings to enable."
        )

    async def get_transcript(self, meeting_id: str) -> dict[str, Any]:
        """
        Fetch transcript for a Google Meet session.

        In practice, transcripts are fetched by MeetSessionHandler
        when the event arrives, not by polling.

        Args:
            meeting_id: Meeting identifier (gmeet-xxxx format)

        Returns:
            dict: Transcript data in internal format
        """
        # Meeting ID format: gmeet-{uuid}
        # We need to look up the transcript_name from the stored meeting data
        # This is a fallback path — normally MeetSessionHandler handles this
        raise NotImplementedError(
            "Use MeetSessionHandler.handle_transcript_ready() for the "
            "normal transcript flow. Direct get_transcript() requires "
            "the stored Google Meet metadata."
        )

    async def get_status(self, meeting_id: str) -> str:
        """
        Get meeting/transcript status.

        Args:
            meeting_id: Meeting identifier

        Returns:
            Status string
        """
        # Google Meet sessions don't have real-time status tracking
        # Status comes from the meeting record in storage
        return "unknown"

    def handle_webhook(self, event: dict[str, Any]) -> str | None:
        """
        Handle a Pub/Sub push event for Meet transcripts.

        This is called by the webhook route. Returns the transcript
        name if a transcript event was received.

        Args:
            event: Pub/Sub push message data

        Returns:
            Transcript name if ready, None otherwise
        """
        from meeting_transcription.google_meet.webhook_handler import MeetWebhookHandler

        handler = MeetWebhookHandler()
        result = handler.handle_push_message(event)

        if result.get("status") == "processed":
            return result.get("transcript_name")

        return None
