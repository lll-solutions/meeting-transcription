#!/usr/bin/env python3
"""
Script to manually trigger transcript processing for meetings that ended
but didn't get processed (e.g., before Cloud Tasks were implemented).

Usage:
    python trigger_ended_meetings.py
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.api.storage import MeetingStorage
from main import process_transcript


def main():
    """Find ended meetings and trigger processing."""

    # Initialize storage
    bucket_name = os.getenv("OUTPUT_BUCKET")
    storage = MeetingStorage(bucket_name=bucket_name)

    print("🔍 Looking for ended meetings with transcripts...")

    # Get all meetings
    meetings = storage.list_meetings(limit=100)

    # Find meetings that are "ended" and have a transcript_id
    ended_with_transcripts = []
    for meeting in meetings:
        status = meeting.get('status')
        transcript_id = meeting.get('transcript_id')
        recording_id = meeting.get('recording_id')

        if status == 'ended' and transcript_id:
            ended_with_transcripts.append({
                'id': meeting['id'],
                'transcript_id': transcript_id,
                'recording_id': recording_id,
                'bot_name': meeting.get('bot_name', 'Unknown'),
                'created_at': meeting.get('created_at', 'Unknown')
            })

    if not ended_with_transcripts:
        print("✅ No ended meetings found that need processing")
        return

    print(f"\n📋 Found {len(ended_with_transcripts)} meeting(s) to process:\n")
    for i, meeting in enumerate(ended_with_transcripts, 1):
        print(f"  {i}. {meeting['bot_name']}")
        print(f"     Meeting ID: {meeting['id']}")
        print(f"     Transcript ID: {meeting['transcript_id']}")
        print(f"     Created: {meeting['created_at']}")
        print()

    # Confirm with user
    response = input("Process these meetings? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("❌ Cancelled")
        return

    # Process each meeting
    print("\n🔄 Processing meetings...\n")
    for meeting in ended_with_transcripts:
        print(f"Processing: {meeting['bot_name']}")
        print(f"  Meeting ID: {meeting['id']}")
        print(f"  Transcript ID: {meeting['transcript_id']}")

        try:
            # Call the process_transcript function directly
            process_transcript(
                transcript_id=meeting['transcript_id'],
                recording_id=meeting['recording_id']
            )
            print(f"  ✅ Processing completed!\n")
        except Exception as e:
            print(f"  ❌ Error: {e}\n")
            import traceback
            traceback.print_exc()

    print("✅ All done!")


if __name__ == '__main__':
    main()
