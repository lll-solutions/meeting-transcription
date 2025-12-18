"""
Webhook event handling service.

Handles business logic for Recall.ai webhook events:
- Bot lifecycle events (joining, ended)
- Recording completion events
- Transcript completion events
- Cloud Tasks integration for async processing
"""

import json
import os
import time
from collections.abc import Callable
from typing import Any

from src.api.storage import MeetingStorage


class WebhookService:
    """Service for handling Recall.ai webhook events."""

    def __init__(
        self,
        storage: MeetingStorage,
        recall_client: Any,
        process_transcript_callback: Callable[[str, str | None], None] | None = None,
    ) -> None:
        """
        Initialize the webhook service.

        Args:
            storage: Meeting storage instance for persistence
            recall_client: Recall API client module
            process_transcript_callback: Optional callback for sync transcript processing
        """
        self.storage = storage
        self.recall = recall_client
        self.process_transcript_callback = process_transcript_callback

    def handle_event(self, event_data: dict, service_url: str) -> None:
        """
        Route webhook events to appropriate handlers.

        Args:
            event_data: Webhook event payload from Recall.ai
            service_url: Base URL of this service for Cloud Tasks

        Raises:
            ValueError: If event type is missing
        """
        event = event_data.get("event")
        if not event:
            raise ValueError("Missing event type in webhook payload")

        print(f"\n📨 Received event: {event}")

        # Route to appropriate handler
        if event == "bot.joining_call":
            self._handle_bot_joining(event_data)
        elif event in ["bot.done", "bot.call_ended"]:
            self._handle_bot_ended(event_data)
        elif event == "recording.done":
            self._handle_recording_done(event_data)
        elif event == "transcript.done":
            self._handle_transcript_done(event_data, service_url)
        elif event == "transcript.failed":
            self._handle_transcript_failed(event_data)
        else:
            print(f"ℹ️ Unhandled event: {event}")

    def _handle_bot_joining(self, event_data: dict) -> None:
        """
        Handle bot.joining_call event.

        Args:
            event_data: Event payload
        """
        bot_id = event_data.get("data", {}).get("bot", {}).get("id") or event_data.get(
            "bot_id"
        )
        print(f"👋 Bot joining the call! ID: {bot_id}")

        if bot_id:
            self.storage.update_meeting(bot_id, {"status": "in_meeting"})

    def _handle_bot_ended(self, event_data: dict) -> None:
        """
        Handle bot.done / bot.call_ended event.

        Args:
            event_data: Event payload
        """
        bot_id = event_data.get("data", {}).get("bot", {}).get("id") or event_data.get(
            "bot_id"
        )
        recording_id = event_data.get("data", {}).get("recording", {}).get(
            "id"
        ) or event_data.get("data", {}).get("recording_id")

        print(f"👋 Bot left the call. Recording ID: {recording_id}")

        # Update meeting status
        if bot_id:
            self.storage.update_meeting(
                bot_id, {"status": "ended", "recording_id": recording_id}
            )

        # Request async transcript
        if recording_id:
            self._request_transcript(bot_id, recording_id)

    def _handle_recording_done(self, event_data: dict) -> None:
        """
        Handle recording.done event.

        Args:
            event_data: Event payload
        """
        recording_id = event_data.get("data", {}).get("recording", {}).get("id")
        bot_id = event_data.get("data", {}).get("bot", {}).get("id")

        print(f"🎬 Recording completed! ID: {recording_id}, Bot ID: {bot_id}")

        # Update meeting with recording_id
        if bot_id and recording_id:
            try:
                self.storage.update_meeting(bot_id, {"recording_id": recording_id})
                print(f"✅ Updated meeting {bot_id} with recording_id {recording_id}")
            except Exception as e:
                print(f"⚠️ Could not update meeting with recording_id: {e}")

        # Request async transcript
        if recording_id:
            self._request_transcript(bot_id, recording_id)

    def _handle_transcript_done(self, event_data: dict, service_url: str) -> None:
        """
        Handle transcript.done event.

        Queues transcript processing via Cloud Tasks, with fallback to sync processing.

        Args:
            event_data: Event payload
            service_url: Base URL of this service
        """
        transcript_id = event_data.get("data", {}).get("transcript", {}).get("id")
        recording_id = event_data.get("data", {}).get("recording", {}).get("id")

        print(
            f"✅ Transcript ready! ID: {transcript_id}, Recording ID: {recording_id}"
        )

        if not transcript_id:
            print("⚠️ No transcript_id in event data")
            return

        # Find meeting ID for this transcript
        meeting_id = self._find_meeting_by_transcript(transcript_id, recording_id)

        # Try to queue via Cloud Tasks (async)
        task_created = self._create_cloud_task(
            meeting_id, transcript_id, recording_id, service_url
        )

        if task_created:
            # Update status to queued
            self.storage.update_meeting(meeting_id, {"status": "queued"})
        else:
            # Fallback to synchronous processing
            print("⚠️ Falling back to synchronous processing")
            if self.process_transcript_callback:
                self.process_transcript_callback(transcript_id, recording_id)

    def _handle_transcript_failed(self, event_data: dict) -> None:
        """
        Handle transcript.failed event.

        Args:
            event_data: Event payload
        """
        print("❌ Transcript failed")
        print(event_data)

    def _request_transcript(
        self, bot_id: str | None, recording_id: str | None
    ) -> None:
        """
        Request async transcript from Recall API.

        Args:
            bot_id: Bot/meeting ID to update
            recording_id: Recording ID to create transcript for
        """
        if not recording_id:
            return

        print(f"📝 Requesting async transcript for recording {recording_id}")
        time.sleep(5)  # Wait for recording to finalize

        transcript_result = self.recall.create_async_transcript(recording_id)

        # Update meeting with transcript_id
        if bot_id and transcript_result:
            try:
                self.storage.update_meeting(
                    bot_id,
                    {
                        "transcript_id": transcript_result["id"],
                        "status": "transcribing",
                    },
                )
                print(
                    f"✅ Updated meeting {bot_id} with transcript_id {transcript_result['id']}"
                )
            except Exception as e:
                print(f"⚠️ Could not update meeting with transcript_id: {e}")

    def _find_meeting_by_transcript(
        self, transcript_id: str, recording_id: str | None
    ) -> str:
        """
        Find meeting ID by transcript or recording ID.

        Args:
            transcript_id: Transcript ID to search for
            recording_id: Recording ID to search for (fallback)

        Returns:
            Meeting ID (uses recording_id or transcript_id as fallback)
        """
        meetings_list = self.storage.list_meetings()
        for meeting in meetings_list:
            # Try matching by transcript_id first, then recording_id
            if meeting.get("transcript_id") == transcript_id or meeting.get(
                "recording_id"
            ) == recording_id:
                meeting_id: str = str(meeting["id"])
                print(f"✅ Found meeting {meeting_id} for transcript {transcript_id}")
                return meeting_id

        # Fallback: use recording_id or transcript_id as meeting_id
        print(
            f"⚠️ No meeting found for transcript {transcript_id} / recording {recording_id}"
        )
        print("   Using recording_id as meeting_id (fallback)")
        fallback_id: str = recording_id or transcript_id
        return fallback_id

    def _create_cloud_task(
        self,
        meeting_id: str,
        transcript_id: str,
        recording_id: str | None,
        service_url: str,
    ) -> bool:
        """
        Create Cloud Task for async transcript processing.

        Args:
            meeting_id: Meeting ID
            transcript_id: Transcript ID
            recording_id: Optional recording ID
            service_url: Base URL of this service

        Returns:
            True if task created successfully, False otherwise
        """
        try:
            from google.cloud import tasks_v2

            project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
            if not project_id:
                raise ValueError("GOOGLE_CLOUD_PROJECT environment variable not set")

            location = os.getenv("GCP_REGION", "us-central1")
            queue = "transcript-processing"

            url = f"{service_url}/api/transcripts/process-recall/{meeting_id}"

            client = tasks_v2.CloudTasksClient()
            parent = client.queue_path(project_id, location, queue)

            payload = {"transcript_id": transcript_id, "recording_id": recording_id}

            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": url,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps(payload).encode(),
                    "oidc_token": {
                        "service_account_email": (
                            f"{os.getenv('GCP_PROJECT_NUMBER', '')}-compute@developer.gserviceaccount.com"
                        ),
                        "audience": service_url,
                    },
                }
            }

            response = client.create_task(request={"parent": parent, "task": task})
            print(f"✅ Cloud Task created for transcript processing: {response.name}")
            return True

        except Exception as e:
            print(f"❌ Failed to create Cloud Task for transcript: {e}")
            import traceback

            traceback.print_exc()
            return False
