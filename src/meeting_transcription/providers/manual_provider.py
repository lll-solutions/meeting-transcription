"""
Manual upload transcript provider.

Handles user-uploaded transcripts without requiring a meeting bot.
"""

import json
import os
import uuid
from typing import Any

from .base import ProviderType, TranscriptProvider


class ManualUploadProvider(TranscriptProvider):
    """
    Transcript provider for manually uploaded transcripts.

    This provider handles the case where users upload transcript
    files directly (JSON, VTT, or text format) rather than having
    a bot join a meeting.
    """

    _provider_type = ProviderType.MANUAL

    def __init__(self):
        """Initialize the manual upload provider."""
        self._bucket_name = os.getenv("OUTPUT_BUCKET")

    @property
    def name(self) -> str:
        """Human-readable provider name."""
        return "Manual Upload"

    @property
    def provider_type(self) -> ProviderType:
        """Provider type identifier."""
        return ProviderType.MANUAL

    async def create_meeting(self, meeting_url: str, **kwargs) -> str:
        """
        Create a meeting record for an uploaded transcript.

        For manual uploads, meeting_url is not used - we generate
        a unique meeting ID.

        Args:
            meeting_url: Ignored for manual uploads
            **kwargs: Additional options (unused)

        Returns:
            str: Generated meeting ID (format: upload-{uuid})
        """
        # Generate unique ID for this upload
        meeting_id = f"upload-{uuid.uuid4().hex[:8]}"
        return meeting_id

    async def get_transcript(self, meeting_id: str) -> dict[str, Any]:
        """
        Fetch uploaded transcript from GCS temp storage.

        Args:
            meeting_id: The meeting ID

        Returns:
            dict: Transcript data

        Raises:
            RuntimeError: If transcript not found or fetch fails
        """
        if not self._bucket_name:
            raise RuntimeError("OUTPUT_BUCKET environment variable not set")

        from google.cloud import storage as gcs_storage

        blob_name = f"temp/{meeting_id}/transcript_upload.json"

        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(self._bucket_name)
        blob = bucket.blob(blob_name)

        if not blob.exists():
            raise RuntimeError(f"Transcript not found in temp storage: {blob_name}")

        transcript_json = blob.download_as_text()
        return json.loads(transcript_json)

    async def get_status(self, meeting_id: str) -> str:
        """
        Get the status of an uploaded transcript.

        For manual uploads, if the transcript exists in temp storage,
        it's ready for processing.

        Args:
            meeting_id: The meeting ID

        Returns:
            str: Status ('uploaded', 'not_found')
        """
        if not self._bucket_name:
            return "not_found"

        try:
            from google.cloud import storage as gcs_storage

            blob_name = f"temp/{meeting_id}/transcript_upload.json"

            gcs_client = gcs_storage.Client()
            bucket = gcs_client.bucket(self._bucket_name)
            blob = bucket.blob(blob_name)

            if blob.exists():
                return "uploaded"
            return "not_found"
        except Exception:
            return "error"

    async def store_transcript(
        self, meeting_id: str, transcript_data: list[dict[str, Any]]
    ) -> None:
        """
        Store an uploaded transcript in GCS temp storage.

        This is a provider-specific method for storing uploaded transcripts
        before processing.

        Args:
            meeting_id: The meeting ID
            transcript_data: Transcript data (list of segments)

        Raises:
            RuntimeError: If storage fails
        """
        if not self._bucket_name:
            raise RuntimeError("OUTPUT_BUCKET environment variable not set")

        from google.cloud import storage as gcs_storage

        blob_name = f"temp/{meeting_id}/transcript_upload.json"

        gcs_client = gcs_storage.Client()
        bucket = gcs_client.bucket(self._bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_string(
            json.dumps(transcript_data),
            content_type="application/json"
        )

        print(f"✅ Transcript stored temporarily: gs://{self._bucket_name}/{blob_name}")

    async def delete_temp_transcript(self, meeting_id: str) -> None:
        """
        Delete temporary transcript file from GCS.

        Called after processing is complete.

        Args:
            meeting_id: The meeting ID
        """
        if not self._bucket_name:
            return

        try:
            from google.cloud import storage as gcs_storage

            blob_name = f"temp/{meeting_id}/transcript_upload.json"

            gcs_client = gcs_storage.Client()
            bucket = gcs_client.bucket(self._bucket_name)
            blob = bucket.blob(blob_name)
            blob.delete()

            print("🗑️ Temp transcript deleted")
        except Exception:
            # Ignore errors - this is cleanup
            pass
