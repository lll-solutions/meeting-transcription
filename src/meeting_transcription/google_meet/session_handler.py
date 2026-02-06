"""
Auto-trigger session creation when a Google Meet transcript is received.

Orchestrates: event received -> fetch transcript -> parse -> create meeting -> queue pipeline.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from .meet_client import MeetApiClient
from .transcript_parser import parse_meet_transcript


class MeetSessionHandler:
    """
    Handles automatic session creation from Google Meet transcript events.

    When a transcript.fileGenerated event is received, this handler:
    1. Fetches transcript entries from the Meet API
    2. Fetches participant info for speaker names
    3. Parses into internal format
    4. Creates a meeting record in storage
    5. Queues processing via Cloud Tasks
    """

    def __init__(self, storage: Any, service_url: str = "") -> None:
        """
        Args:
            storage: MeetingStorage instance
            service_url: Base service URL for Cloud Tasks callbacks
        """
        self.storage = storage
        self.service_url = service_url or os.getenv("SERVICE_URL", "")
        self.meet_client = MeetApiClient()

    def handle_transcript_ready(
        self,
        user_id: str,
        transcript_name: str,
        event_data: dict[str, Any],
    ) -> str:
        """
        Handle a transcript-ready event end-to-end.

        Args:
            user_id: App user ID who owns the subscription
            transcript_name: Meet transcript resource name
                (e.g., "conferenceRecords/abc/transcripts/def")
            event_data: Full event data from Workspace Events

        Returns:
            meeting_id: The created meeting ID

        Raises:
            ValueError: If transcript fetch or parsing fails
        """
        # Extract conference record ID
        parts = transcript_name.split("/")
        conference_record_id = parts[1] if len(parts) >= 4 else ""

        print(f"Processing Meet transcript: {transcript_name}")

        # 1. Fetch transcript entries from Meet API
        entries = self.meet_client.get_transcript_entries(user_id, transcript_name)
        if not entries:
            raise ValueError(f"No transcript entries found for {transcript_name}")

        print(f"  Fetched {len(entries)} transcript entries")

        # 2. Fetch participant info for name resolution
        participants = []
        if conference_record_id:
            try:
                participants = self.meet_client.get_participants(
                    user_id, conference_record_id
                )
                print(f"  Fetched {len(participants)} participants")
            except Exception as e:
                print(f"  Warning: Could not fetch participants: {e}")

        # 3. Get conference record for meeting metadata
        meeting_meta = {}
        if conference_record_id:
            try:
                conf_record = self.meet_client.get_conference_record(
                    user_id, conference_record_id
                )
                meeting_meta = {
                    "space": conf_record.get("space", ""),
                    "start_time": conf_record.get("startTime", ""),
                    "end_time": conf_record.get("endTime", ""),
                }
            except Exception as e:
                print(f"  Warning: Could not fetch conference record: {e}")

        # 4. Parse transcript to internal format
        segments = parse_meet_transcript(
            entries=entries,
            participants=participants,
            meeting_start_time=meeting_meta.get("start_time"),
        )

        if not segments:
            raise ValueError("Parsed transcript is empty")

        print(f"  Parsed {len(segments)} segments")

        # 5. Create meeting record
        meeting_id = f"gmeet-{uuid.uuid4().hex[:8]}"
        title = self._generate_title(meeting_meta, conference_record_id)

        self.storage.create_meeting(
            meeting_id=meeting_id,
            user=user_id,
            meeting_url=meeting_meta.get("space", ""),
            bot_name=title,
        )

        self.storage.update_meeting(
            meeting_id,
            {
                "status": "queued",
                "provider": "google_meet",
                "source": "auto",
                "google_meet": {
                    "transcript_name": transcript_name,
                    "conference_record_id": conference_record_id,
                    **meeting_meta,
                },
            },
        )

        # 6. Store transcript and queue processing
        self._store_and_queue(meeting_id, segments, title)

        print(f"  Created meeting {meeting_id}, queued for processing")

        return meeting_id

    def _generate_title(
        self, meeting_meta: dict[str, Any], conference_record_id: str
    ) -> str:
        """Generate a meeting title from metadata."""
        start_time = meeting_meta.get("start_time", "")

        if start_time:
            try:
                dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                return f"Google Meet {dt.strftime('%Y-%m-%d %H:%M')}"
            except (ValueError, TypeError):
                pass

        return f"Google Meet {conference_record_id[:8] if conference_record_id else datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

    def _store_and_queue(
        self, meeting_id: str, segments: list[dict], title: str
    ) -> None:
        """Store transcript in GCS and create Cloud Task for processing."""
        bucket_name = os.getenv("OUTPUT_BUCKET")
        if not bucket_name:
            # Fallback: process inline (dev mode)
            print("  No OUTPUT_BUCKET set, storing locally")
            self.storage.update_meeting(meeting_id, {"status": "pending"})
            return

        # Store transcript in GCS temp
        try:
            from google.cloud import storage as gcs

            gcs_client = gcs.Client()
            bucket = gcs_client.bucket(bucket_name)
            blob = bucket.blob(f"temp/{meeting_id}/transcript_upload.json")
            blob.upload_from_string(
                json.dumps(segments), content_type="application/json"
            )
        except Exception as e:
            print(f"  Error storing transcript: {e}")
            self.storage.update_meeting(
                meeting_id, {"status": "failed", "error": str(e)}
            )
            return

        # Create Cloud Task
        if self.service_url:
            try:
                self._create_cloud_task(meeting_id, title)
            except Exception as e:
                print(f"  Error creating Cloud Task: {e}")
                self.storage.update_meeting(
                    meeting_id,
                    {"status": "failed", "error": f"Queue error: {e}"},
                )

    def _create_cloud_task(self, meeting_id: str, title: str) -> None:
        """Create a Cloud Task for processing."""
        from google.cloud import tasks_v2

        project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
        if not project_id:
            return

        location = os.getenv("GCP_REGION", "us-central1")
        queue = "transcript-processing"

        url = f"{self.service_url.rstrip('/')}/api/transcripts/process/{meeting_id}"

        client = tasks_v2.CloudTasksClient()
        parent = client.queue_path(project_id, location, queue)

        payload = {"meeting_id": meeting_id, "title": title}

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode(),
                "oidc_token": {
                    "service_account_email": (
                        f"{os.getenv('GCP_PROJECT_NUMBER', '')}"
                        "-compute@developer.gserviceaccount.com"
                    ),
                    "audience": self.service_url,
                },
            }
        }

        response = client.create_task(request={"parent": parent, "task": task})
        print(f"  Cloud Task created: {response.name}")
