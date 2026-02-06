# Google Meet Transcript Sync

This guide explains how automatic Google Meet transcript sync works for SaaS users.

## Overview

Google Meet transcript sync automatically captures and processes transcripts from your Google Meet calls. Unlike the Recall.ai bot-based approach, this integration works **passively** -- no bot joins your meeting. Instead, transcripts are fetched after the meeting ends via Google's APIs.

## Getting Started

1. Go to **Settings** in the app
2. Click **Connect Google Meet**
3. Sign in with your Google Workspace account and grant permissions
4. That's it -- transcripts from future meetings will sync automatically

## What Happens Behind the Scenes

```
You have a Google Meet call with transcription on
                    |
                    v
        Meeting ends, Google generates transcript
                    |
                    v
    Google Workspace Events sends notification
                    |
                    v
        App receives event via Pub/Sub push
                    |
                    v
     App fetches transcript from Meet REST API
                    |
                    v
     AI pipeline processes the transcript
        (chunking, summarization, study guide)
                    |
                    v
        Results appear on your dashboard
```

## Requirements

- **Google Workspace account** -- personal Gmail accounts don't have Meet transcript access
- **Transcription enabled** -- the meeting host must enable transcription in Google Meet settings or during the call
- **Connected account** -- you must connect your Google account in Settings

## What Gets Captured

When a transcript is available, the app fetches:

- **Full transcript text** with speaker attribution
- **Timestamps** for each spoken segment
- **Participant names** (signed-in users show display names; phone/anonymous users show as "Phone User" or "Anonymous")
- **Conference metadata** (meeting ID, start time)

The transcript is then processed through the same AI pipeline used for other transcript sources:
- Chunked into time-based segments
- Summarized by the configured LLM
- Study guide generated (if using the Educational plugin)
- PDF output (if enabled)

## Checking Status

Visit your **Dashboard** to see Google Meet transcripts and their processing status:

| Status | Meaning |
|--------|---------|
| Queued | Transcript received, waiting for processing |
| Processing | AI pipeline is running |
| Completed | Ready to view -- click to see outputs |
| Failed | Something went wrong -- click Retry to reprocess |

The dashboard auto-refreshes every 15 seconds when Google Meet transcripts are present.

## FAQ

**Q: Does a bot join my meeting?**
No. Google Meet integration is event-driven. No bot joins your call. Transcripts are fetched after the meeting ends through Google's official APIs.

**Q: Which meetings are captured?**
Only meetings where transcription was enabled AND the meeting generated a transcript. If transcription wasn't turned on, there's nothing to capture.

**Q: How long until the transcript appears?**
Typically 1-5 minutes after the meeting ends. Google needs time to finalize the transcript, then the event notification propagates, and the AI pipeline runs.

**Q: Can I disconnect Google Meet?**
Yes. Go to **Settings > Disconnect Google Meet**. This stops transcript sync immediately. Your existing processed transcripts remain available.

**Q: What permissions does the app need?**
The app requests read-only access to your Meet conference records and transcripts. It cannot modify your meetings, calendar, or any other Google data.

**Q: Does this work with Google Meet for personal accounts?**
No. Google Meet transcript APIs require a Google Workspace account (Business, Enterprise, Education, etc.). Personal Gmail accounts don't have programmatic transcript access.

**Q: What if a transcript fails to process?**
Click the **Retry** button on the dashboard. If it fails repeatedly, the raw transcript is still stored and can be reprocessed later.
