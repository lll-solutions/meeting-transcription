"""
Google Meet REST API v2 client for transcript retrieval.

Fetches transcript entries from the Meet API after receiving
a notification that a transcript is ready.

API docs: https://developers.google.com/workspace/meet/api/guides/overview
"""

from typing import Any

import requests

from .oauth import GoogleOAuthFlow

MEET_API_BASE = "https://meet.googleapis.com/v2"


class MeetApiClient:
    """Client for the Google Meet REST API v2."""

    def __init__(self) -> None:
        self.oauth = GoogleOAuthFlow()

    def get_transcript_entries(
        self, user_id: str, transcript_name: str
    ) -> list[dict[str, Any]]:
        """
        Fetch all transcript entries for a transcript.

        Args:
            user_id: App user ID (for OAuth token lookup)
            transcript_name: Full transcript resource name
                (e.g., "conferenceRecords/abc/transcripts/def")

        Returns:
            List of transcript entry dicts with speaker and text info

        Raises:
            ValueError: If API call fails
        """
        access_token = self._get_token(user_id)
        entries = []
        page_token = None

        while True:
            params: dict[str, str] = {"pageSize": "100"}
            if page_token:
                params["pageToken"] = page_token

            resp = requests.get(
                f"{MEET_API_BASE}/{transcript_name}/entries",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=30,
            )

            if resp.status_code == 401:
                # Refresh and retry once
                access_token = self.oauth.refresh_access_token(user_id)
                if not access_token:
                    raise ValueError("Failed to refresh access token")

                resp = requests.get(
                    f"{MEET_API_BASE}/{transcript_name}/entries",
                    headers={"Authorization": f"Bearer {access_token}"},
                    params=params,
                    timeout=30,
                )

            if resp.status_code != 200:
                raise ValueError(
                    f"Failed to fetch transcript entries: "
                    f"{resp.status_code} {resp.text}"
                )

            data = resp.json()
            entries.extend(data.get("transcriptEntries", []))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return entries

    def get_conference_record(
        self, user_id: str, conference_record_id: str
    ) -> dict[str, Any]:
        """
        Get conference record metadata (meeting info).

        Args:
            user_id: App user ID
            conference_record_id: Conference record ID

        Returns:
            Conference record dict with meeting metadata

        Raises:
            ValueError: If API call fails
        """
        access_token = self._get_token(user_id)

        resp = requests.get(
            f"{MEET_API_BASE}/conferenceRecords/{conference_record_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        if resp.status_code == 401:
            access_token = self.oauth.refresh_access_token(user_id)
            if not access_token:
                raise ValueError("Failed to refresh access token")

            resp = requests.get(
                f"{MEET_API_BASE}/conferenceRecords/{conference_record_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=30,
            )

        if resp.status_code != 200:
            raise ValueError(
                f"Failed to fetch conference record: "
                f"{resp.status_code} {resp.text}"
            )

        return resp.json()

    def get_participants(
        self, user_id: str, conference_record_id: str
    ) -> list[dict[str, Any]]:
        """
        Get participant list for a conference record.

        Args:
            user_id: App user ID
            conference_record_id: Conference record ID

        Returns:
            List of participant dicts
        """
        access_token = self._get_token(user_id)
        participants = []
        page_token = None

        while True:
            params: dict[str, str] = {"pageSize": "100"}
            if page_token:
                params["pageToken"] = page_token

            resp = requests.get(
                f"{MEET_API_BASE}/conferenceRecords/{conference_record_id}/participants",
                headers={"Authorization": f"Bearer {access_token}"},
                params=params,
                timeout=30,
            )

            if resp.status_code != 200:
                break

            data = resp.json()
            participants.extend(data.get("participants", []))

            page_token = data.get("nextPageToken")
            if not page_token:
                break

        return participants

    def list_transcripts(
        self, user_id: str, conference_record_id: str
    ) -> list[dict[str, Any]]:
        """
        List all transcripts for a conference record.

        Args:
            user_id: App user ID
            conference_record_id: Conference record ID

        Returns:
            List of transcript resource dicts
        """
        access_token = self._get_token(user_id)

        resp = requests.get(
            f"{MEET_API_BASE}/conferenceRecords/{conference_record_id}/transcripts",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )

        if resp.status_code != 200:
            return []

        return resp.json().get("transcripts", [])

    def _get_token(self, user_id: str) -> str:
        """Get a valid access token for the user."""
        token = self.oauth.get_valid_access_token(user_id)
        if not token:
            raise ValueError(
                f"No Google access token available for user {user_id}. "
                "User must connect their Google account first."
            )
        return token
