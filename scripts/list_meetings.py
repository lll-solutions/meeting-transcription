#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from meeting_transcription.api.storage import MeetingStorage

storage = MeetingStorage(bucket_name=os.getenv("OUTPUT_BUCKET"))
meetings = storage.list_meetings(limit=20)

print(f"\nFound {len(meetings)} meeting(s):\n")
for i, m in enumerate(meetings, 1):
    print(f"{i}. {m.get('bot_name', 'Unknown')}")
    print(f"   ID: {m['id']}")
    print(f"   Status: {m.get('status', 'unknown')}")
    print(f"   Transcript ID: {m.get('transcript_id', 'None')}")
    print(f"   Recording ID: {m.get('recording_id', 'None')}")
    print(f"   Created: {m.get('created_at', 'Unknown')}")
    print()
