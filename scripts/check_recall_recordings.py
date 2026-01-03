#!/usr/bin/env python3
"""Check if Recall has recordings for ended meetings without transcripts."""
import os
import sys
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
from meeting_transcription.api.storage import MeetingStorage
from meeting_transcription.api import recall

storage = MeetingStorage(bucket_name=os.getenv("OUTPUT_BUCKET"))
meetings = storage.list_meetings(limit=20)

print("\n🔍 Checking Recall for recordings...\n")

for m in meetings:
    if m.get('status') == 'ended' and not m.get('transcript_id'):
        bot_id = m['id']
        print(f"Meeting: {m.get('bot_name', 'Unknown')}")
        print(f"  Bot ID: {bot_id}")

        # Get bot info from Recall
        try:
            bot_info = recall.get_bot_status(bot_id)
            if bot_info:
                status_changes = bot_info.get('status_changes', [])
                latest_status = status_changes[-1].get('code') if status_changes else 'unknown'
                print(f"  Recall status: {latest_status}")

                # Get recording ID from recordings array
                recordings = bot_info.get('recordings', [])
                if recordings:
                    recording_id = recordings[0].get('id')
                    recording_status = recordings[0].get('status', {}).get('code', 'unknown')
                    print(f"  Recording ID: {recording_id}")
                    print(f"  Recording status: {recording_status}")
                else:
                    recording_id = None
                    print(f"  Recording ID: None")

                if recording_id:
                    print(f"  ✅ Recording exists! We can request transcript.")

                    # Try to request async transcript
                    print(f"  📝 Requesting transcript...")
                    result = recall.create_async_transcript(recording_id)
                    if result:
                        transcript_id = result.get('id')
                        print(f"  ✅ Transcript requested: {transcript_id}")

                        # Update meeting with transcript_id and recording_id
                        storage.update_meeting(bot_id, {
                            'recording_id': recording_id,
                            'transcript_id': transcript_id,
                            'status': 'transcribing'
                        })
                        print(f"  ✅ Meeting updated with transcript ID")
                    else:
                        print(f"  ❌ Failed to request transcript")
                else:
                    print(f"  ❌ No recording found")
            else:
                print(f"  ❌ Bot not found in Recall")
        except Exception as e:
            print(f"  ❌ Error: {e}")

        print()
