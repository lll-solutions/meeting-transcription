#!/usr/bin/env python3
"""Quick script to check scheduled meetings in Firestore."""

from google.cloud import firestore
from datetime import datetime
from zoneinfo import ZoneInfo

db = firestore.Client()

# Get all scheduled meetings
meetings = db.collection("scheduled_meetings").stream()

print("\n=== Scheduled Meetings in Firestore ===\n")

count = 0
for doc in meetings:
    count += 1
    data = doc.to_dict()
    print(f"ID: {doc.id}")
    print(f"  User: {data.get('user')}")
    print(f"  Meeting URL: {data.get('meeting_url')}")
    print(f"  Scheduled Time: {data.get('scheduled_time')}")
    print(f"  Status: {data.get('status')}")
    print(f"  Bot Name: {data.get('bot_name')}")

    # Check if it's past the scheduled time
    sched_time = data.get('scheduled_time')
    if sched_time:
        now = datetime.now(ZoneInfo("UTC"))
        if isinstance(sched_time, datetime):
            if sched_time <= now:
                print(f"  ⏰ SHOULD HAVE STARTED (was scheduled for {sched_time})")
            else:
                print(f"  ⏳ Scheduled for future ({sched_time})")
    print()

if count == 0:
    print("No scheduled meetings found in Firestore!")
else:
    print(f"Total: {count} scheduled meeting(s)")
