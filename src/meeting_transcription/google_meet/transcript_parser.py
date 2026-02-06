"""
Parse Google Meet transcript entries to internal format.

Converts Meet REST API transcript entries into the normalized
segment format expected by the processing pipeline.

Meet transcript entry format (from API):
{
    "name": "conferenceRecords/.../transcripts/.../entries/...",
    "participant": "conferenceRecords/.../participants/...",
    "text": "What the participant said",
    "languageCode": "en-US",
    "startTime": "2024-01-15T10:30:00Z",
    "endTime": "2024-01-15T10:30:05Z"
}

Internal format (for pipeline):
{
    "participant": "Speaker Name",
    "text": "What they said",
    "start_timestamp": 0.0,
    "end_timestamp": 5.0
}
"""

from datetime import datetime
from typing import Any


def parse_meet_transcript(
    entries: list[dict[str, Any]],
    participants: list[dict[str, Any]] | None = None,
    meeting_start_time: str | None = None,
) -> list[dict[str, Any]]:
    """
    Convert Meet API transcript entries to internal pipeline format.

    Args:
        entries: List of transcript entries from Meet API
        participants: Optional participant list for name resolution
        meeting_start_time: Meeting start time (ISO format) for relative timestamps.
            If not provided, uses the first entry's start time.

    Returns:
        List of segments in the internal combined format
    """
    if not entries:
        return []

    # Build participant ID -> name mapping
    participant_names = _build_participant_map(participants or [])

    # Determine meeting start time for relative timestamps
    base_time = _parse_timestamp(meeting_start_time) if meeting_start_time else None
    if base_time is None and entries:
        first_start = entries[0].get("startTime", "")
        base_time = _parse_timestamp(first_start)

    segments = []
    for entry in entries:
        segment = _parse_entry(entry, participant_names, base_time)
        if segment:
            segments.append(segment)

    # Merge consecutive segments from the same speaker
    merged = _merge_consecutive_segments(segments)

    return merged


def _parse_entry(
    entry: dict[str, Any],
    participant_names: dict[str, str],
    base_time: datetime | None,
) -> dict[str, Any] | None:
    """Parse a single transcript entry to internal format."""
    text = entry.get("text", "").strip()
    if not text:
        return None

    # Resolve participant name
    participant_ref = entry.get("participant", "")
    # Extract participant ID from resource name
    # Format: conferenceRecords/{id}/participants/{id}
    participant_id = participant_ref.split("/")[-1] if "/" in participant_ref else participant_ref
    speaker = participant_names.get(participant_id, participant_names.get(participant_ref, "Unknown"))

    # Calculate relative timestamps
    start_str = entry.get("startTime", "")
    end_str = entry.get("endTime", "")

    start_time = 0.0
    end_time = 0.0

    if start_str and base_time:
        start_dt = _parse_timestamp(start_str)
        if start_dt:
            start_time = (start_dt - base_time).total_seconds()

    if end_str and base_time:
        end_dt = _parse_timestamp(end_str)
        if end_dt:
            end_time = (end_dt - base_time).total_seconds()

    return {
        "participant": speaker,
        "text": text,
        "start_timestamp": max(0.0, start_time),
        "end_timestamp": max(0.0, end_time),
    }


def _build_participant_map(participants: list[dict[str, Any]]) -> dict[str, str]:
    """
    Build a mapping from participant resource name/ID to display name.

    Participant format from Meet API:
    {
        "name": "conferenceRecords/{id}/participants/{id}",
        "signedinUser": {
            "user": "users/{id}",
            "displayName": "John Doe"
        }
    }
    """
    name_map: dict[str, str] = {}

    for p in participants:
        resource_name = p.get("name", "")
        # Extract just the participant ID
        participant_id = resource_name.split("/")[-1] if "/" in resource_name else resource_name

        # Try different user info fields
        display_name = "Unknown"

        signed_in = p.get("signedinUser", {})
        if signed_in.get("displayName"):
            display_name = signed_in["displayName"]

        anonymous = p.get("anonymousUser", {})
        if anonymous.get("displayName"):
            display_name = anonymous["displayName"]

        phone = p.get("phoneUser", {})
        if phone.get("displayName"):
            display_name = phone["displayName"]

        # Map both full resource name and just the ID
        name_map[resource_name] = display_name
        if participant_id:
            name_map[participant_id] = display_name

    return name_map


def _merge_consecutive_segments(
    segments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Merge consecutive segments from the same speaker.

    Meet API returns fine-grained entries (per-utterance). Merging
    consecutive same-speaker segments produces cleaner transcripts.
    """
    if not segments:
        return []

    merged = [segments[0].copy()]

    for seg in segments[1:]:
        prev = merged[-1]

        if seg["participant"] == prev["participant"]:
            # Same speaker — merge text and extend end time
            prev["text"] = f"{prev['text']} {seg['text']}"
            prev["end_timestamp"] = seg["end_timestamp"]
        else:
            merged.append(seg.copy())

    return merged


def _parse_timestamp(ts: str | None) -> datetime | None:
    """Parse an ISO timestamp string to datetime."""
    if not ts:
        return None

    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def meet_transcript_to_text(segments: list[dict[str, Any]]) -> str:
    """
    Convert parsed segments to a plain text transcript.

    Useful for LLM processing.

    Args:
        segments: Parsed transcript segments

    Returns:
        Formatted text transcript
    """
    lines = []
    for seg in segments:
        speaker = seg.get("participant", "Unknown")
        text = seg.get("text", "")
        lines.append(f"{speaker}: {text}")

    return "\n\n".join(lines)
