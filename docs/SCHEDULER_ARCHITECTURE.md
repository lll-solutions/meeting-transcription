# Scheduler Architecture for Cloud Run

## Overview

The scheduled meeting functionality uses **Cloud Scheduler** (GCP's cron service) instead of a background thread running in the Flask app. This architecture is optimized for Cloud Run's serverless, scale-to-zero model.

## Why Cloud Scheduler?

Cloud Run instances scale to zero when not handling requests, which means background threads would stop running and miss scheduled meetings. Cloud Scheduler solves this by:

1. Running as a managed GCP service (always available)
2. Triggering the app every 2 minutes via HTTP
3. Waking up Cloud Run when needed
4. Allowing the app to scale to zero between checks

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Cloud Scheduler                           │
│                                                              │
│   Cron: */2 * * * * (every 2 minutes)                       │
│   Action: POST /api/scheduled-meetings/execute              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ HTTP POST with OIDC token
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Cloud Run Service                         │
│  (meeting-transcription)                                     │
│                                                              │
│  Route: /api/scheduled-meetings/execute                     │
│    1. Verify OIDC token from Cloud Scheduler                │
│    2. Query Firestore for pending meetings                  │
│    3. Join meetings via Recall.ai API                       │
│    4. Update meeting status in Firestore                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ Read/Write
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                       Firestore                              │
│                                                              │
│  Collection: scheduled_meetings                             │
│    - status: "scheduled" | "completed" | "failed"           │
│    - scheduled_time: UTC timestamp                          │
│    - user, meeting_url, bot_name, etc.                      │
└─────────────────────────────────────────────────────────────┘
```

## How It Works

### 1. User Schedules a Meeting

```javascript
// Frontend sends POST to /api/scheduled-meetings
{
  "meeting_url": "https://zoom.us/j/123456789",
  "scheduled_time": "2024-12-10T15:30:00",  // In user's timezone
  "bot_name": "My Bot"
}
```

Backend:
- Converts time to UTC
- Stores in Firestore with `status: "scheduled"`
- Returns confirmation

### 2. Cloud Scheduler Triggers (Every 2 Minutes)

Cloud Scheduler sends:
```
POST https://YOUR-SERVICE-URL/api/scheduled-meetings/execute
Authorization: Bearer <OIDC-TOKEN>
```

### 3. Endpoint Executes Pending Meetings

The endpoint (`main.py:582`):
1. Verifies the request is from Cloud Scheduler (OIDC token)
2. Queries Firestore for meetings where:
   - `status == "scheduled"`
   - `scheduled_time <= now()`
3. For each pending meeting:
   - Calls `join_meeting_for_scheduler()` to create bot via Recall.ai
   - Updates status to "completed" or "failed"
   - Links to actual meeting record if successful

### 4. User Views Status

Frontend polls `/api/scheduled-meetings` to see:
- Upcoming scheduled meetings
- Completed meetings with links to recordings
- Failed meetings with error messages

## Implementation Details

### Endpoint: `/api/scheduled-meetings/execute`

**File:** `main.py:582-683`

**Authentication:**
- Public endpoint (no user auth required)
- Verifies `Authorization: Bearer <token>` header
- In production, should verify OIDC token signature

**Query:**
```python
# Get meetings ready to execute
now = utc_now()
pending = storage.get_pending(before_time=now)

# Query: WHERE status="scheduled" AND scheduled_time <= now
```

**Execution:**
```python
for meeting in pending:
    meeting_id = join_meeting_for_scheduler(
        meeting.meeting_url,
        meeting.bot_name,
        meeting.user
    )

    if meeting_id:
        # Update to completed with link to actual meeting
        storage.update(meeting.id, {
            "status": "completed",
            "actual_meeting_id": meeting_id
        })
```

### Cloud Scheduler Configuration

**Schedule:** `*/2 * * * *` (every 2 minutes)

**Target:** Cloud Run service endpoint

**Authentication:** OIDC token with service account:
```
{PROJECT_NUMBER}-compute@developer.gserviceaccount.com
```

**Setup Script:** `scripts/setup-scheduler.sh`

**Auto-configured in:** `deploy.sh` (lines 143-187)

## Timing & Precision

### Granularity
- Checks every **2 minutes**
- Meetings may start up to 2 minutes late (acceptable for most use cases)

### Example Timeline

```
User schedules meeting for 2:30 PM
  ↓
Stored in Firestore: 2024-12-10T14:30:00Z (UTC)
  ↓
Cloud Scheduler checks at:
- 2:28 PM → Not yet time, no action
- 2:30 PM → Time to execute!
  ↓
Endpoint creates bot, joins meeting
  ↓
Status updated to "completed"
```

### Why Not Every Minute?
- **Cost:** Each invocation has a small cost
- **Load:** Reduces unnecessary Firestore queries
- **Precision:** 2-minute window is acceptable for meeting joins

## Cost Analysis

### Cloud Scheduler
- **Free tier:** 3 jobs free per month
- **Cost:** $0.10 per job per month after free tier
- **Our setup:** 1 job = Free

### Cloud Run Invocations
- **Frequency:** 720 times/day (every 2 minutes)
- **Duration:** ~100ms per check (no pending meetings)
- **Cost:** ~$0.50/month (well within free tier)

### Total Incremental Cost
**~$0-1/month** (likely free with GCP free tier)

## Deployment

### Initial Setup

```bash
# Included in deploy.sh automatically
./deploy.sh
```

### Manual Setup (if needed)

```bash
# Run standalone scheduler setup
./scripts/setup-scheduler.sh
```

### Verify Setup

```bash
# Check scheduler job
gcloud scheduler jobs describe meeting-scheduler --location=us-central1

# Manually trigger (for testing)
gcloud scheduler jobs run meeting-scheduler --location=us-central1

# View logs
gcloud run logs read --service=meeting-transcription --region=us-central1 --limit=50
```

## Monitoring

### View Scheduler Logs

```bash
# In Cloud Console
# Navigation → Cloud Scheduler → meeting-scheduler → View Logs

# Or via gcloud
gcloud logging read "resource.type=cloud_scheduler_job" --limit=20
```

### View Execution Results

```bash
# Cloud Run logs show execution details
gcloud run logs read --service=meeting-transcription --region=us-central1 \
  --filter='textPayload:"Cloud Scheduler"'
```

### Success Indicators

Look for log entries like:
```
⏰ Cloud Scheduler: Found 1 pending meeting(s) to execute
🤖 Executing scheduled meeting: abc-123-def
✅ Successfully joined meeting: meeting-456
```

### Failure Indicators

```
❌ Failed to join scheduled meeting: abc-123-def
Error: Invalid meeting URL
```

## Troubleshooting

### Meetings Not Executing

**Check 1: Is Cloud Scheduler running?**
```bash
gcloud scheduler jobs describe meeting-scheduler --location=us-central1
# Look for: state: ENABLED
```

**Check 2: Are there pending meetings?**
```bash
# Query Firestore directly (or via web UI)
# Look for documents with status="scheduled" and scheduled_time in the past
```

**Check 3: Check Cloud Scheduler logs**
```bash
gcloud logging read "resource.type=cloud_scheduler_job" --limit=10
# Look for HTTP 200 responses
```

**Check 4: Check Cloud Run logs**
```bash
gcloud run logs read --service=meeting-transcription --region=us-central1 --limit=50
# Look for "Cloud Scheduler" entries
```

### Common Issues

**Issue:** "Unauthorized - missing Bearer token"
- **Cause:** Cloud Scheduler OIDC not configured
- **Fix:** Run `scripts/setup-scheduler.sh`

**Issue:** Meetings execute but fail to join
- **Cause:** RECALL_API_KEY or WEBHOOK_URL not configured
- **Fix:** Check environment variables in Cloud Run

**Issue:** Scheduler job not found
- **Cause:** Cloud Scheduler API not enabled or job not created
- **Fix:** Run `gcloud services enable cloudscheduler.googleapis.com` then `./deploy.sh`

## Alternative Approaches (Not Used)

### Option 1: Background Thread (Not Recommended)
- ❌ Stops when Cloud Run scales to zero
- ❌ Misses scheduled meetings
- ✅ Would work with `--min-instances=1` (but costs more)

### Option 2: Cloud Tasks (More Complex)
- ✅ Exact timing (no polling)
- ✅ Individual task per meeting
- ❌ More complex setup
- ❌ Need to manage task lifecycle (create/cancel)

### Option 3: Cloud Functions + Pub/Sub
- ✅ Serverless
- ❌ Additional moving parts
- ❌ Unnecessary complexity for this use case

## Security Considerations

### OIDC Token Verification

The endpoint currently accepts any Bearer token. For production, consider verifying the OIDC token:

```python
from google.auth import jwt

def verify_cloud_scheduler_token(token):
    """Verify OIDC token from Cloud Scheduler."""
    try:
        # Decode and verify token
        claims = jwt.decode(token, verify=True)

        # Check email matches Cloud Scheduler service account
        expected_email = f"{PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
        if claims.get('email') != expected_email:
            return False

        return True
    except Exception:
        return False
```

### Rate Limiting

Cloud Scheduler provides natural rate limiting (max 1 request per 2 minutes), but consider adding additional protection if needed.

### Firestore Security Rules

Ensure Firestore rules allow the service account to read/write scheduled_meetings:

```javascript
match /scheduled_meetings/{meeting} {
  allow read, write: if request.auth != null;
}
```

## Summary

**Pros:**
- ✅ Works with Cloud Run's scale-to-zero model
- ✅ Minimal cost (~$0-1/month)
- ✅ Reliable (GCP-managed cron)
- ✅ Simple to understand and maintain
- ✅ Auto-configured during deployment

**Cons:**
- ❌ 2-minute granularity (not instant)
- ❌ Requires Cloud Scheduler API enabled

**Best for:**
- Serverless deployments on Cloud Run
- Meeting scheduling (2-minute precision is fine)
- Cost-sensitive projects
