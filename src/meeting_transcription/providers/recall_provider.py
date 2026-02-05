"""
Recall.ai transcript provider.

Integrates with Recall.ai's bot service to join meetings,
record, and retrieve transcripts.
"""

import os
from typing import Any

from .base import ProviderType, TranscriptProvider


class RecallProvider(TranscriptProvider):
    """
    Transcript provider using Recall.ai bot service.

    Recall.ai provides bots that join video meetings (Zoom, Google Meet, Teams)
    to record and transcribe the meeting.
    """

    _provider_type = ProviderType.RECALL

    def __init__(self, api_key: str | None = None):
        """
        Initialize the Recall provider.

        Args:
            api_key: Recall.ai API key (defaults to RECALL_API_KEY env var)
        """
        self._api_key = api_key or os.getenv("RECALL_API_KEY")
        self._base_url = os.getenv(
            "RECALL_API_BASE_URL", "https://us-west-2.recall.ai/api/v1"
        )

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "Recall.ai"

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        return ProviderType.RECALL

    async def create_meeting(self, meeting_url: str, **kwargs) -> str:
        """
        Create a bot to join a meeting.

        Args:
            meeting_url: The meeting URL to join
            **kwargs:
                webhook_url: URL to receive bot events
                bot_name: Display name for the bot

        Returns:
            str: Bot ID (used as meeting_id)

        Raises:
            ValueError: If API key not configured
            RuntimeError: If bot creation fails
        """
        if not self._api_key:
            raise ValueError("RECALL_API_KEY not configured")

        import requests

        webhook_url = kwargs.get("webhook_url", "")
        bot_name = kwargs.get("bot_name", "Meeting Assistant Bot")

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "meeting_url": meeting_url,
            "bot_name": bot_name,
            "webhook_url": webhook_url,
            "automatic_leave": {
                "waiting_room_timeout": 600,
                "noone_joined_timeout": 600,
                "everyone_left_timeout": 2
            },
            "recording_config": {
                "recording_mode": "speaker_view"
            }
        }

        response = requests.post(
            f"{self._base_url}/bot/",
            json=payload,
            headers=headers
        )

        if response.status_code == 201:
            bot_data = response.json()
            print(f"✅ Bot created successfully! ID: {bot_data['id']}")
            return bot_data["id"]
        else:
            print(f"❌ Error creating bot: {response.status_code}")
            print(response.text)
            raise RuntimeError(
                f"Failed to create bot: {response.status_code} - {response.text}"
            )

    async def get_transcript(self, meeting_id: str) -> dict[str, Any]:
        """
        Fetch transcript data for a meeting.

        Note: This fetches via transcript_id, not meeting_id directly.
        The transcript_id is obtained from webhook events or bot status.

        Args:
            meeting_id: Actually the transcript_id from Recall

        Returns:
            dict: Transcript data from Recall API

        Raises:
            RuntimeError: If transcript fetch fails
        """
        if not self._api_key:
            raise ValueError("RECALL_API_KEY not configured")

        import requests

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Accept": "application/json"
        }

        response = requests.get(
            f"{self._base_url}/transcript/{meeting_id}/",
            headers=headers
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise RuntimeError(
                f"Failed to get transcript: {response.status_code} - {response.text}"
            )

    async def get_status(self, meeting_id: str) -> str:
        """
        Get the current status of a bot.

        Args:
            meeting_id: The bot ID

        Returns:
            str: Bot status (e.g., 'joining_call', 'in_call_not_recording', etc.)
        """
        if not self._api_key:
            raise ValueError("RECALL_API_KEY not configured")

        import requests

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Accept": "application/json"
        }

        response = requests.get(
            f"{self._base_url}/bot/{meeting_id}/",
            headers=headers
        )

        if response.status_code == 200:
            data = response.json()
            # Return the status_changes[-1].code if available
            status_changes = data.get("status_changes", [])
            if status_changes:
                return status_changes[-1].get("code", "unknown")
            return "unknown"
        else:
            return "error"

    def handle_webhook(self, event: dict[str, Any]) -> str | None:
        """
        Handle Recall.ai webhook events.

        Args:
            event: Webhook event payload

        Returns:
            str | None: Bot ID if transcript is ready
        """
        event_type = event.get("event", "")

        # Transcript ready event
        if event_type == "transcript.done":
            # Return the bot_id so caller knows which meeting has transcript ready
            bot_id = event.get("data", {}).get("bot", {}).get("id")
            if bot_id:
                return bot_id

        return None

    async def leave_meeting(self, meeting_id: str) -> bool:
        """
        Make a bot leave the meeting.

        Args:
            meeting_id: The bot ID

        Returns:
            bool: True if leave command succeeded
        """
        if not self._api_key:
            return False

        import requests

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        response = requests.post(
            f"{self._base_url}/bot/{meeting_id}/leave_call/",
            headers=headers
        )

        if response.status_code == 200:
            print(f"✅ Bot {meeting_id} is leaving the meeting")
            return True
        else:
            print(f"❌ Error making bot leave: {response.status_code}")
            return False

    async def create_async_transcript(self, recording_id: str) -> dict[str, Any] | None:
        """
        Request an async transcript from Recall.ai.

        This is a Recall-specific method for requesting high-quality
        transcription via AssemblyAI.

        Args:
            recording_id: The recording ID

        Returns:
            dict | None: Transcript request data, or None if failed
        """
        if not self._api_key:
            return None

        import requests

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        payload = {
            "provider": {
                "assembly_ai_async": {
                    "language_code": "en_us",
                    "punctuate": True,
                    "format_text": True,
                    "speaker_labels": True,
                    "disfluencies": False,
                    "sentiment_analysis": True,
                    "auto_chapters": True,
                    "entity_detection": True
                }
            }
        }

        response = requests.post(
            f"{self._base_url}/recording/{recording_id}/create_transcript/",
            json=payload,
            headers=headers
        )

        if response.status_code == 200:
            transcript_data = response.json()
            print(f"✅ Async transcript requested! ID: {transcript_data['id']}")
            return transcript_data
        else:
            print(f"❌ Error creating async transcript: {response.status_code}")
            print(response.text)
            return None

    async def download_transcript(
        self, transcript_id: str, output_file: str | None = None
    ) -> str | dict[str, Any] | None:
        """
        Download the transcript JSON file or return content.

        Args:
            transcript_id: The transcript ID
            output_file: Optional path to save transcript

        Returns:
            str | dict | None: File path if output_file provided,
                               transcript content otherwise, None if failed
        """
        if not self._api_key:
            return None

        import requests

        # Get transcript metadata with download URL
        transcript = await self.get_transcript(transcript_id)

        download_url = transcript.get("data", {}).get("download_url")
        if not download_url:
            print("❌ No download URL in transcript data")
            return None

        response = requests.get(download_url)

        if response.status_code == 200:
            if output_file:
                with open(output_file, 'w') as f:
                    f.write(response.text)
                print(f"✅ Transcript downloaded to {output_file}")
                return output_file
            else:
                return response.json()

        print("❌ Could not download transcript")
        return None
