"""Tests for Google Meet transcript parser."""

from meeting_transcription.google_meet.transcript_parser import (
    meet_transcript_to_text,
    parse_meet_transcript,
)


class TestParseMeetTranscript:
    """Tests for parse_meet_transcript()."""

    def test_empty_entries(self):
        result = parse_meet_transcript([])
        assert result == []

    def test_single_entry(self):
        entries = [
            {
                "name": "conferenceRecords/abc/transcripts/def/entries/001",
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "Hello everyone",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:05Z",
            }
        ]
        participants = [
            {
                "name": "conferenceRecords/abc/participants/p1",
                "signedinUser": {"displayName": "Alice"},
            }
        ]

        result = parse_meet_transcript(entries, participants)

        assert len(result) == 1
        assert result[0]["participant"] == "Alice"
        assert result[0]["text"] == "Hello everyone"
        assert result[0]["start_timestamp"] == 0.0
        assert result[0]["end_timestamp"] == 5.0

    def test_multiple_speakers(self):
        entries = [
            {
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "How are you?",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:03Z",
            },
            {
                "participant": "conferenceRecords/abc/participants/p2",
                "text": "I'm good, thanks.",
                "startTime": "2024-01-15T10:00:04Z",
                "endTime": "2024-01-15T10:00:07Z",
            },
        ]
        participants = [
            {
                "name": "conferenceRecords/abc/participants/p1",
                "signedinUser": {"displayName": "Alice"},
            },
            {
                "name": "conferenceRecords/abc/participants/p2",
                "signedinUser": {"displayName": "Bob"},
            },
        ]

        result = parse_meet_transcript(entries, participants)

        assert len(result) == 2
        assert result[0]["participant"] == "Alice"
        assert result[1]["participant"] == "Bob"

    def test_consecutive_same_speaker_merged(self):
        entries = [
            {
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "First sentence.",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:03Z",
            },
            {
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "Second sentence.",
                "startTime": "2024-01-15T10:00:03Z",
                "endTime": "2024-01-15T10:00:06Z",
            },
            {
                "participant": "conferenceRecords/abc/participants/p2",
                "text": "Response.",
                "startTime": "2024-01-15T10:00:07Z",
                "endTime": "2024-01-15T10:00:09Z",
            },
        ]
        participants = [
            {
                "name": "conferenceRecords/abc/participants/p1",
                "signedinUser": {"displayName": "Alice"},
            },
            {
                "name": "conferenceRecords/abc/participants/p2",
                "signedinUser": {"displayName": "Bob"},
            },
        ]

        result = parse_meet_transcript(entries, participants)

        assert len(result) == 2
        assert result[0]["text"] == "First sentence. Second sentence."
        assert result[0]["start_timestamp"] == 0.0
        assert result[0]["end_timestamp"] == 6.0
        assert result[1]["participant"] == "Bob"

    def test_unknown_participant(self):
        entries = [
            {
                "participant": "conferenceRecords/abc/participants/unknown",
                "text": "Hello",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:02Z",
            }
        ]

        result = parse_meet_transcript(entries, participants=[])

        assert len(result) == 1
        assert result[0]["participant"] == "Unknown"

    def test_empty_text_skipped(self):
        entries = [
            {
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:02Z",
            },
            {
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "Real content",
                "startTime": "2024-01-15T10:00:03Z",
                "endTime": "2024-01-15T10:00:05Z",
            },
        ]

        result = parse_meet_transcript(entries, participants=[])

        assert len(result) == 1
        assert result[0]["text"] == "Real content"

    def test_relative_timestamps_from_meeting_start(self):
        entries = [
            {
                "participant": "p1",
                "text": "Late entry",
                "startTime": "2024-01-15T10:05:00Z",
                "endTime": "2024-01-15T10:05:10Z",
            }
        ]

        result = parse_meet_transcript(
            entries,
            meeting_start_time="2024-01-15T10:00:00Z",
        )

        assert result[0]["start_timestamp"] == 300.0  # 5 minutes
        assert result[0]["end_timestamp"] == 310.0

    def test_anonymous_participant(self):
        entries = [
            {
                "participant": "conferenceRecords/abc/participants/p1",
                "text": "Hello",
                "startTime": "2024-01-15T10:00:00Z",
                "endTime": "2024-01-15T10:00:02Z",
            }
        ]
        participants = [
            {
                "name": "conferenceRecords/abc/participants/p1",
                "anonymousUser": {"displayName": "Guest 1"},
            }
        ]

        result = parse_meet_transcript(entries, participants)

        assert result[0]["participant"] == "Guest 1"


class TestMeetTranscriptToText:
    """Tests for meet_transcript_to_text()."""

    def test_basic_conversion(self):
        segments = [
            {"participant": "Alice", "text": "Hello"},
            {"participant": "Bob", "text": "Hi there"},
        ]

        result = meet_transcript_to_text(segments)

        assert "Alice: Hello" in result
        assert "Bob: Hi there" in result

    def test_empty_segments(self):
        result = meet_transcript_to_text([])
        assert result == ""
