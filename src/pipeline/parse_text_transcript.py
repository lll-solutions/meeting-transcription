#!/usr/bin/env python3
"""
Parse text-based transcripts into combined format.

Supports formats:
1. VTT (WebVTT) - Zoom's native format:
   WEBVTT
   00:00:05.000 --> 00:00:08.000
   Sarah Chen: Good morning everyone

2. Bracketed timestamps - Google Meet style:
   [00:00:08]
   Attorney Sarah Chen: Please state your name for the record.
"""
import re
from typing import List, Dict, Any


def parse_timestamp(timestamp_str: str) -> float:
    """
    Parse timestamp string to seconds.

    Supports formats:
    - [00:00:08] -> 8.0
    - [00:01:23] -> 83.0
    - [01:23:45] -> 5025.0

    Args:
        timestamp_str: Timestamp in [HH:MM:SS] or [MM:SS] format

    Returns:
        Total seconds as float
    """
    # Remove brackets and split
    time_str = timestamp_str.strip('[]')
    parts = time_str.split(':')

    if len(parts) == 2:  # MM:SS
        minutes, seconds = parts
        return int(minutes) * 60 + int(seconds)
    elif len(parts) == 3:  # HH:MM:SS
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp_str}")


def parse_vtt_timestamp(timestamp_str: str) -> float:
    """
    Parse VTT timestamp to seconds.

    Supports formats:
    - 00:00:05.000 -> 5.0
    - 00:01:23.500 -> 83.5
    - 01:23:45.123 -> 5025.123

    Args:
        timestamp_str: Timestamp in HH:MM:SS.mmm format

    Returns:
        Total seconds as float
    """
    # Format: HH:MM:SS.mmm
    time_part, ms_part = timestamp_str.split('.')
    hours, minutes, seconds = time_part.split(':')

    total_seconds = int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    total_seconds += float(f"0.{ms_part}")

    return total_seconds


def detect_text_transcript_format(text: str) -> Dict[str, Any]:
    """
    Detect if text is in transcript format and identify the variant.

    Args:
        text: Raw text content

    Returns:
        Dict with 'is_transcript' bool and 'format' string
    """
    # VTT format detection
    vtt_header = text.strip().startswith('WEBVTT')
    vtt_timestamp_pattern = r'\d{2}:\d{2}:\d{2}\.\d{3}\s+-->\s+\d{2}:\d{2}:\d{2}\.\d{3}'
    has_vtt_timestamps = bool(re.search(vtt_timestamp_pattern, text))

    if vtt_header and has_vtt_timestamps:
        return {
            'is_transcript': True,
            'format': 'vtt',
            'has_timestamps': True,
            'has_speakers': True  # VTT lines typically include speaker names
        }

    # Bracketed timestamp format like [00:00:08]
    bracketed_timestamp_pattern = r'\[\d{2}:\d{2}:\d{2}\]|\[\d{2}:\d{2}\]'
    has_bracketed_timestamps = bool(re.search(bracketed_timestamp_pattern, text))

    # Look for speaker patterns like "Name: text"
    speaker_pattern = r'^[A-Z][^:\n]+:\s+.+$'
    has_speakers = bool(re.search(speaker_pattern, text, re.MULTILINE))

    is_transcript = has_bracketed_timestamps and has_speakers

    # Detect specific formats
    format_type = 'unknown'
    if is_transcript:
        if 'Google Meet Transcript' in text:
            format_type = 'google_meet'
        elif 'Zoom' in text or 'zoom' in text.lower():
            format_type = 'zoom_text'
        else:
            format_type = 'generic_text'

    return {
        'is_transcript': is_transcript,
        'format': format_type,
        'has_timestamps': has_bracketed_timestamps,
        'has_speakers': has_speakers
    }


def parse_vtt_to_combined_format(text: str) -> List[Dict[str, Any]]:
    """
    Parse VTT (WebVTT) transcript into combined JSON format.

    VTT format:
    WEBVTT

    00:00:05.000 --> 00:00:08.000
    Sarah Chen: Good morning everyone

    Args:
        text: Raw VTT transcript

    Returns:
        List of segments in combined format
    """
    lines = text.split('\n')

    # Pattern to match VTT timestamps: 00:00:05.000 --> 00:00:08.000
    vtt_timestamp_pattern = re.compile(
        r'^(\d{2}:\d{2}:\d{2}\.\d{3})\s+-->\s+(\d{2}:\d{2}:\d{2}\.\d{3})$'
    )

    # Pattern to match speaker lines: "Speaker Name: text"
    speaker_pattern = re.compile(r'^([^:\n]+):\s+(.+)$')

    segments = []
    current_start = None
    current_end = None
    current_speaker = None
    current_text = []

    participants = {}
    participant_id = 100

    for line in lines:
        line = line.strip()

        if not line or line == 'WEBVTT':
            continue

        # Check if it's a timestamp line
        timestamp_match = vtt_timestamp_pattern.match(line)
        if timestamp_match:
            # Save previous segment if exists
            if current_speaker and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'start': current_start,
                    'end': current_end,
                    'text': ' '.join(current_text)
                })
                current_text = []

            current_start = parse_vtt_timestamp(timestamp_match.group(1))
            current_end = parse_vtt_timestamp(timestamp_match.group(2))
            continue

        # Check if it's a speaker line
        speaker_match = speaker_pattern.match(line)
        if speaker_match:
            current_speaker = speaker_match.group(1).strip()
            text_part = speaker_match.group(2).strip()
            current_text = [text_part]

            # Track participant
            if current_speaker not in participants:
                participants[current_speaker] = participant_id
                participant_id += 1

            continue

        # Otherwise, it's a continuation or caption without speaker
        # In VTT, sometimes text appears without speaker prefix
        if current_start is not None:
            if not current_speaker:
                # If no speaker detected, try to extract from this line
                speaker_match = speaker_pattern.match(line)
                if speaker_match:
                    current_speaker = speaker_match.group(1).strip()
                    text_part = speaker_match.group(2).strip()
                    current_text = [text_part]

                    if current_speaker not in participants:
                        participants[current_speaker] = participant_id
                        participant_id += 1
                else:
                    # Plain text line without speaker - use "Unknown Speaker"
                    if not current_speaker:
                        current_speaker = "Unknown Speaker"
                        if current_speaker not in participants:
                            participants[current_speaker] = participant_id
                            participant_id += 1
                    current_text.append(line)
            else:
                current_text.append(line)

    # Don't forget the last segment
    if current_speaker and current_text:
        segments.append({
            'speaker': current_speaker,
            'start': current_start,
            'end': current_end,
            'text': ' '.join(current_text)
        })

    # Convert to combined transcript format
    combined_transcript = []
    for segment in segments:
        word_count = len(segment['text'].split())

        combined_segment = {
            'participant': {
                'id': participants[segment['speaker']],
                'name': segment['speaker'],
                'is_host': None,
                'platform': 'zoom',
                'email': None,
                'extra_data': None
            },
            'text': segment['text'],
            'start_timestamp': {
                'relative': segment['start'],
                'absolute': None
            },
            'end_timestamp': {
                'relative': segment['end'],
                'absolute': None
            },
            'word_count': word_count
        }

        combined_transcript.append(combined_segment)

    return combined_transcript


def parse_bracketed_to_combined_format(text: str) -> List[Dict[str, Any]]:
    """
    Parse bracketed timestamp transcript into combined JSON format.

    Format:
    [00:00:08]
    Sarah Chen: Good morning everyone

    Args:
        text: Raw text transcript

    Returns:
        List of segments in combined format
    """
    # Split into lines
    lines = text.split('\n')

    # Pattern to match timestamps
    timestamp_pattern = re.compile(r'^\[(\d{2}:\d{2}:\d{2}|\d{2}:\d{2})\]$')

    # Pattern to match speaker lines: "Speaker Name: text"
    speaker_pattern = re.compile(r'^([^:\n]+):\s+(.+)$')

    segments = []
    current_timestamp = None
    current_speaker = None
    current_text = []

    participants = {}  # Track unique speakers
    participant_id = 100

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # Check if it's a timestamp
        timestamp_match = timestamp_pattern.match(line)
        if timestamp_match:
            # Save previous segment if exists
            if current_speaker and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'timestamp': current_timestamp,
                    'text': ' '.join(current_text)
                })
                current_text = []

            current_timestamp = timestamp_match.group(1)
            continue

        # Check if it's a speaker line
        speaker_match = speaker_pattern.match(line)
        if speaker_match:
            # Save previous segment if exists
            if current_speaker and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'timestamp': current_timestamp,
                    'text': ' '.join(current_text)
                })
                current_text = []

            current_speaker = speaker_match.group(1).strip()
            text_part = speaker_match.group(2).strip()
            current_text = [text_part]

            # Track participant
            if current_speaker not in participants:
                participants[current_speaker] = participant_id
                participant_id += 1

            continue

        # Otherwise, it's a continuation of the current speaker's text
        if current_speaker:
            current_text.append(line)

    # Don't forget the last segment
    if current_speaker and current_text:
        segments.append({
            'speaker': current_speaker,
            'timestamp': current_timestamp,
            'text': ' '.join(current_text)
        })

    # Convert to combined transcript format
    combined_transcript = []

    for i, segment in enumerate(segments):
        # Calculate timestamps
        if segment['timestamp']:
            start_seconds = parse_timestamp(f"[{segment['timestamp']}]")
        else:
            # If no timestamp, estimate based on previous segment
            start_seconds = combined_transcript[-1]['end_timestamp']['relative'] if combined_transcript else 0

        # End timestamp is either the next segment's start or estimated from text length
        if i + 1 < len(segments) and segments[i + 1]['timestamp']:
            end_seconds = parse_timestamp(f"[{segments[i + 1]['timestamp']}]")
        else:
            # Estimate 2 seconds per sentence
            estimated_duration = max(len(segment['text'].split('.')), 1) * 2
            end_seconds = start_seconds + estimated_duration

        word_count = len(segment['text'].split())

        combined_segment = {
            'participant': {
                'id': participants[segment['speaker']],
                'name': segment['speaker'],
                'is_host': None,
                'platform': None,
                'email': None,
                'extra_data': None
            },
            'text': segment['text'],
            'start_timestamp': {
                'relative': start_seconds,
                'absolute': None
            },
            'end_timestamp': {
                'relative': end_seconds,
                'absolute': None
            },
            'word_count': word_count
        }

        combined_transcript.append(combined_segment)

    return combined_transcript


def parse_text_to_combined_format(text: str) -> List[Dict[str, Any]]:
    """
    Auto-detect format and parse text transcript into combined JSON format.

    Supports:
    - VTT (Zoom native format)
    - Bracketed timestamps (Google Meet, etc.)

    Args:
        text: Raw text transcript

    Returns:
        List of segments in combined format

    Raises:
        ValueError: If format is not recognized
    """
    detection = detect_text_transcript_format(text)

    if not detection['is_transcript']:
        raise ValueError("Text does not appear to be a valid transcript format")

    if detection['format'] == 'vtt':
        print(f"📄 Parsing VTT (Zoom) format...")
        return parse_vtt_to_combined_format(text)
    elif detection['format'] in ['google_meet', 'generic_text', 'zoom_text']:
        print(f"📄 Parsing bracketed timestamp format ({detection['format']})...")
        return parse_bracketed_to_combined_format(text)
    else:
        raise ValueError(f"Unsupported transcript format: {detection['format']}")
