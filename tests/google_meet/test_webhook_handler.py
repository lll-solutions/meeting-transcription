"""Tests for Google Meet webhook handler (Pub/Sub push messages)."""

import base64
import json

import pytest
from meeting_transcription.google_meet.webhook_handler import MeetWebhookHandler


def _make_push_message(event_data: dict, subscription: str = "") -> dict:
    """Helper to create a Pub/Sub push message."""
    encoded = base64.b64encode(json.dumps(event_data).encode()).decode()
    return {
        "message": {
            "data": encoded,
            "messageId": "test-msg-001",
            "publishTime": "2024-01-15T10:00:00Z",
        },
        "subscription": subscription or "projects/test/subscriptions/meet-transcript-push",
    }


class TestMeetWebhookHandler:
    """Tests for MeetWebhookHandler."""

    def test_transcript_generated_event(self):
        callback_calls = []

        def on_ready(user_id, transcript_name, event_data):
            callback_calls.append((user_id, transcript_name))

        handler = MeetWebhookHandler(on_transcript_ready=on_ready)

        event_data = {
            "subscriptionId": "sub-123",
            "targetResource": "//meet.googleapis.com/spaces/abc",
            "eventType": "google.workspace.meet.transcript.v2.fileGenerated",
            "event": {
                "transcript": {
                    "name": "conferenceRecords/abc/transcripts/def",
                }
            },
        }

        result = handler.handle_push_message(_make_push_message(event_data))

        assert result["status"] == "processed"
        assert result["transcript_name"] == "conferenceRecords/abc/transcripts/def"
        assert result["conference_record_id"] == "abc"

    def test_unknown_event_type_skipped(self):
        handler = MeetWebhookHandler()

        event_data = {
            "eventType": "google.workspace.meet.something.else",
        }

        result = handler.handle_push_message(_make_push_message(event_data))

        assert result["status"] == "skipped"

    def test_missing_message_raises(self):
        handler = MeetWebhookHandler()

        with pytest.raises(ValueError, match="Missing 'message'"):
            handler.handle_push_message({})

    def test_missing_data_raises(self):
        handler = MeetWebhookHandler()

        with pytest.raises(ValueError, match="Missing 'data'"):
            handler.handle_push_message({"message": {}})

    def test_invalid_base64_raises(self):
        handler = MeetWebhookHandler()

        msg = {
            "message": {
                "data": "not-valid-base64!!!",
                "messageId": "test",
            }
        }

        with pytest.raises(ValueError, match="Failed to decode"):
            handler.handle_push_message(msg)

    def test_transcript_without_name(self):
        handler = MeetWebhookHandler()

        event_data = {
            "eventType": "google.workspace.meet.transcript.v2.fileGenerated",
            "event": {
                "transcript": {}
            },
        }

        result = handler.handle_push_message(_make_push_message(event_data))

        assert result["status"] == "error"
        assert "No transcript name" in result["reason"]


class TestPushMessageFormat:
    """Tests for various Pub/Sub push message formats."""

    def test_valid_push_format(self):
        handler = MeetWebhookHandler()

        event_data = {
            "eventType": "google.workspace.meet.transcript.v2.fileGenerated",
            "event": {
                "transcript": {
                    "name": "conferenceRecords/123/transcripts/456"
                }
            },
        }

        msg = _make_push_message(event_data)

        # Should parse without error
        result = handler.handle_push_message(msg)
        assert result["status"] == "processed"

    def test_conference_record_id_extraction(self):
        handler = MeetWebhookHandler()

        event_data = {
            "eventType": "google.workspace.meet.transcript.v2.fileGenerated",
            "event": {
                "transcript": {
                    "name": "conferenceRecords/my-conf-id/transcripts/my-transcript-id"
                }
            },
        }

        result = handler.handle_push_message(_make_push_message(event_data))

        assert result["conference_record_id"] == "my-conf-id"
