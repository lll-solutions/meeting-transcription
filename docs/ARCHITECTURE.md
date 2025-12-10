# Architecture Guide

This document describes the technical architecture of the Meeting Transcription service.

## Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           MEETING TRANSCRIPTION                             │
│                              ARCHITECTURE                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐  │
│   │   User      │────▶│  Cloud Run  │────▶│     Recall.ai               │  │
│   │  (Browser)  │     │  (Service)  │◀────│  (Meeting Bot + Recording)  │  │
│   └─────────────┘     └──────┬──────┘     └─────────────────────────────┘  │
│          │                   │                                              │
│          │                   │                                              │
│          ▼                   ▼                                              │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────────────────────┐  │
│   │    IAP      │     │  Firestore  │     │       Vertex AI             │  │
│   │   (Auth)    │     │  (Metadata) │     │  (Gemini Summarization)     │  │
│   └─────────────┘     └─────────────┘     └─────────────────────────────┘  │
│                              │                                              │
│                              ▼                                              │
│                       ┌─────────────┐                                       │
│                       │Cloud Storage│                                       │
│                       │   (Files)   │                                       │
│                       └─────────────┘                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Authentication Layer

### Overview

The service uses **Google Cloud Identity-Aware Proxy (IAP)** to secure access. This provides:

- Zero-code authentication
- Automatic Google account integration
- Only users with GCP project access can use the service
- No passwords or API keys to manage

### How IAP Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. User visits service URL                                                │
│      https://meeting-transcription-xxxxx-uc.a.run.app                      │
│                              │                                              │
│                              ▼                                              │
│   2. IAP intercepts request                                                 │
│      ┌─────────────────────────────────────────────┐                       │
│      │  Is user signed in with Google?             │                       │
│      │  Does user have IAM access to project?      │                       │
│      └─────────────────────────────────────────────┘                       │
│                              │                                              │
│              ┌───────────────┴───────────────┐                             │
│              ▼                               ▼                              │
│   3a. NO: Redirect to              3b. YES: Add headers and                │
│       Google Sign-In                   forward to Cloud Run                 │
│                                                                             │
│   4. Request reaches Cloud Run with IAP headers:                           │
│      X-Goog-Authenticated-User-Email: accounts.google.com:user@example.com │
│      X-Goog-Authenticated-User-Id: 12345678901234567890                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Configuration

IAP is enabled by setting Cloud Run to require authentication:

```yaml
# In Cloud Run deployment (app.json)
"options": {
  "allow-unauthenticated": false  # Enables IAP requirement
}
```

### Granting Access

By default, only the project owner has access. To add more users:

```bash
# Grant access to a specific user
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="user:colleague@example.com" \
  --role="roles/run.invoker"

# Grant access to a Google Group
gcloud projects add-iam-policy-binding PROJECT_ID \
  --member="group:team@example.com" \
  --role="roles/run.invoker"
```

### Webhook Exception

The `/webhook/recall` endpoint must be accessible without authentication (for Recall.ai to send events). This is handled by:

1. Cloud Run allows the webhook path specifically, OR
2. Webhook signature verification (recommended for production)

### Code Implementation

```python
def get_current_user() -> str:
    """
    Get the current authenticated user from IAP headers.
    
    Returns:
        str: User email or 'anonymous' for webhooks
    """
    # IAP adds these headers automatically
    iap_email = request.headers.get('X-Goog-Authenticated-User-Email', '')
    if iap_email:
        # Format: "accounts.google.com:user@example.com"
        return iap_email.split(':')[-1]
    
    return 'anonymous'  # Webhook requests
```

### Enterprise Extension Points

The code includes hooks for future enterprise auth:

```python
# Future: Firebase Auth / OAuth validation
# auth_header = request.headers.get('Authorization', '')
# if auth_header.startswith('Bearer '):
#     token = auth_header[7:]
#     user = validate_firebase_token(token)
#     return user['email']
```

---

## Persistence Layer

### Overview

The service uses a two-tier storage architecture:

| Data Type | Storage | Purpose |
|-----------|---------|---------|
| Meeting Metadata | Firestore | Status, IDs, user info, timestamps |
| Output Files | Cloud Storage (GCS) | Transcripts, summaries, PDFs |

### Why This Split?

- **Firestore**: Fast queries, real-time updates, automatic indexing
- **GCS**: Cheap blob storage, handles large files, signed URLs for downloads

### Firestore Schema

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         FIRESTORE STRUCTURE                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Collection: meetings                                                      │
│   └── Document: {meeting_id}                                               │
│       │                                                                     │
│       ├── id: string              # Recall.ai bot ID                       │
│       ├── user: string            # Email of user who created              │
│       ├── meeting_url: string     # Original meeting URL                   │
│       ├── bot_name: string        # Display name in meeting                │
│       │                                                                     │
│       ├── status: string          # Current state (see below)              │
│       ├── error: string | null    # Error message if failed                │
│       │                                                                     │
│       ├── recording_id: string    # Recall.ai recording ID                 │
│       ├── transcript_id: string   # Recall.ai transcript ID                │
│       │                                                                     │
│       ├── outputs: map            # Paths to output files                  │
│       │   ├── transcript: string  # GCS path to transcript.json            │
│       │   ├── summary: string     # GCS path to summary.json               │
│       │   ├── study_guide_md: string                                       │
│       │   └── study_guide_pdf: string                                      │
│       │                                                                     │
│       ├── created_at: string      # ISO timestamp                          │
│       ├── updated_at: string      # ISO timestamp                          │
│       ├── completed_at: string    # ISO timestamp (when done)              │
│       └── expires_at: string      # ISO timestamp (for retention)          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Meeting Status Flow

```
┌──────────┐    ┌────────┐    ┌──────────────┐    ┌────────────┐    ┌───────────┐
│ joining  │───▶│ ended  │───▶│ transcribing │───▶│ processing │───▶│ completed │
└──────────┘    └────────┘    └──────────────┘    └────────────┘    └───────────┘
     │               │               │                  │
     │               │               │                  │
     ▼               ▼               ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                              failed                                          │
│                     (with error message)                                     │
└──────────────────────────────────────────────────────────────────────────────┘
```

### Cloud Storage Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      CLOUD STORAGE STRUCTURE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Bucket: {project-id}-meeting-outputs                                      │
│   │                                                                         │
│   └── meetings/                                                             │
│       ├── {meeting_id_prefix}/          # First 8 chars of meeting ID      │
│       │   ├── transcript_raw.json       # Raw transcript from Recall.ai    │
│       │   ├── summary.json              # LLM-generated summary            │
│       │   ├── study_guide.md            # Markdown study guide             │
│       │   └── study_guide.pdf           # PDF version                      │
│       │                                                                     │
│       ├── a1b2c3d4/                                                        │
│       │   ├── transcript_raw.json                                          │
│       │   ├── summary.json                                                 │
│       │   ├── study_guide.md                                               │
│       │   └── study_guide.pdf                                              │
│       │                                                                     │
│       └── ...                                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### File Access

Files are accessed via signed URLs (secure, time-limited):

```python
# Generate a download URL (expires in 60 minutes)
url = storage.get_download_url(meeting_id, "study_guide.pdf", expires_minutes=60)

# Returns: https://storage.googleapis.com/bucket/path?X-Goog-Signature=...
```

### Retention Policy

Retention is configurable via environment variable:

```bash
RETENTION_DAYS=0    # Keep forever (default)
RETENTION_DAYS=30   # Delete after 30 days
RETENTION_DAYS=7    # Delete after 1 week
```

When retention is configured:
- `expires_at` field is set on meeting creation
- Cleanup job deletes expired meetings and files
- Can be triggered manually or via Cloud Scheduler

### Local Fallback

If GCP services aren't available (local development), the storage module falls back to:

- Meeting metadata: JSON files in `outputs/meetings/`
- Output files: Local filesystem in `outputs/{meeting_id}/`

```python
# Automatic fallback
storage = MeetingStorage(
    bucket_name=os.getenv("OUTPUT_BUCKET"),  # None = local
    local_dir="outputs"
)
```

---

## Recall.ai Webhooks

### Overview

The service receives real-time event notifications from Recall.ai via webhooks. These events drive the meeting lifecycle and trigger the transcription pipeline.

### Webhook Configuration

When creating a bot, the webhook URL is registered with Recall.ai:

```python
# In src/api/recall.py
payload = {
    "meeting_url": meeting_url,
    "bot_name": bot_name,
    "webhook_url": webhook_url,  # e.g., https://your-app.run.app/webhook/recall
    # ...
}
```

### Webhook Endpoint

**POST** `/webhook/recall`

- **Authentication**: Public endpoint (Recall.ai needs access)
- **Security**: Consider webhook signature verification for production
- **Handler**: `main.py:784-871`

### Supported Events

The service handles the following Recall.ai webhook events:

#### 1. `bot.joined`

**Trigger**: Bot successfully joins the meeting
**Purpose**: Update status to show bot is active in the meeting
**Database Update**: Sets status to `in_meeting`

```json
{
  "event": "bot.joined",
  "data": {
    "bot": {
      "id": "bot-uuid"
    }
  }
}
```

**Handler**:
```python
if event == 'bot.joined':
    bot_id = data.get('data', {}).get('bot', {}).get('id')
    storage.update_meeting(bot_id, {"status": "in_meeting"})
```

**UI Impact**: Users will see the meeting status change from "joining" to "in_meeting"

#### 2. `bot.done` / `bot.call_ended`

**Trigger**: Meeting ends and bot leaves
**Purpose**: Initiate transcript request
**Database Update**: Sets status to `ended`, stores recording ID

```json
{
  "event": "bot.done",
  "data": {
    "bot": {
      "id": "bot-uuid"
    },
    "recording": {
      "id": "recording-uuid"
    }
  }
}
```

**Handler**:
```python
elif event in ['bot.done', 'bot.call_ended']:
    bot_id = data.get('data', {}).get('bot', {}).get('id')
    recording_id = data.get('data', {}).get('recording', {}).get('id')

    # Update meeting status
    storage.update_meeting(bot_id, {
        "status": "ended",
        "recording_id": recording_id
    })

    # Request async transcript
    if recording_id:
        time.sleep(5)  # Wait for recording to finalize
        transcript_result = recall.create_async_transcript(recording_id)
        if transcript_result:
            storage.update_meeting(bot_id, {
                "transcript_id": transcript_result['id'],
                "status": "transcribing"
            })
```

#### 3. `recording.done`

**Trigger**: Recording processing is complete
**Purpose**: Alternative trigger for transcript request (if not already requested)
**Database Update**: None (transcript request only)

```json
{
  "event": "recording.done",
  "data": {
    "recording": {
      "id": "recording-uuid"
    }
  }
}
```

#### 4. `transcript.done`

**Trigger**: Transcript is ready for download
**Purpose**: Start the summarization pipeline
**Database Update**: Status changes throughout pipeline execution

```json
{
  "event": "transcript.done",
  "data": {
    "transcript": {
      "id": "transcript-uuid"
    },
    "recording": {
      "id": "recording-uuid"
    }
  }
}
```

**Handler**: This triggers the complete processing pipeline:
```python
elif event == 'transcript.done':
    transcript_id = data.get('data', {}).get('transcript', {}).get('id')
    recording_id = data.get('data', {}).get('recording', {}).get('id')

    # Process through entire pipeline
    process_transcript(transcript_id, recording_id)
```

**Pipeline Steps**:
1. `status: "processing"` - Download transcript
2. Combine words into sentences
3. Create educational chunks
4. LLM summarization
5. Generate study guide (Markdown)
6. Convert to PDF
7. `status: "completed"` - Upload all outputs

#### 5. `transcript.failed`

**Trigger**: Transcript generation failed
**Purpose**: Alert that manual intervention may be needed
**Database Update**: Should update to failed status

```json
{
  "event": "transcript.failed",
  "data": {
    "transcript": {
      "id": "transcript-uuid",
      "error": "..."
    }
  }
}
```

### Event Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          WEBHOOK EVENT FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. Bot Created                                                            │
│      status: "joining"                                                      │
│      │                                                                      │
│      ▼                                                                      │
│   2. Webhook: bot.joined                                                    │
│      status: "in_meeting"                                                   │
│      │                                                                      │
│      │... meeting happens ...                                              │
│      │                                                                      │
│      ▼                                                                      │
│   3. Webhook: bot.done / bot.call_ended                                    │
│      status: "ended"                                                        │
│      → Trigger: Request async transcript                                   │
│      status: "transcribing"                                                 │
│      │                                                                      │
│      ▼                                                                      │
│   4. Webhook: transcript.done                                               │
│      status: "processing"                                                   │
│      → Trigger: Start summarization pipeline                               │
│      │                                                                      │
│      ▼                                                                      │
│   5. Pipeline completes                                                     │
│      status: "completed"                                                    │
│                                                                             │
│   Alternative Error Path:                                                  │
│      ▼                                                                      │
│   X. Webhook: transcript.failed                                             │
│      status: "failed"                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Webhook Security

#### Current Implementation
- Endpoint is public (no authentication required)
- Suitable for development and private deployments

#### Production Recommendations
- Implement webhook signature verification
- Use Recall.ai's webhook secret to validate requests
- Example implementation:

```python
import hmac
import hashlib

def verify_webhook_signature(request, webhook_secret):
    """Verify webhook is from Recall.ai"""
    signature = request.headers.get('X-Recall-Signature')
    if not signature:
        return False

    payload = request.get_data()
    computed = hmac.new(
        webhook_secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(signature, computed)
```

### Status Transitions

| From Status | Webhook Event | To Status | Notes |
|------------|---------------|-----------|-------|
| `joining` | `bot.joined` | `in_meeting` | Bot successfully entered |
| `in_meeting` | `bot.done` | `ended` | Meeting finished |
| `ended` | (internal) | `transcribing` | Transcript requested |
| `transcribing` | `transcript.done` | `processing` | Pipeline starts |
| `processing` | (internal) | `completed` | All outputs ready |
| Any | `transcript.failed` | `failed` | Error occurred |

---

## Data Flow

### Complete Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           COMPLETE DATA FLOW                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. USER CREATES MEETING                                                   │
│      POST /api/meetings { meeting_url: "https://zoom.us/j/123" }           │
│      │                                                                      │
│      ▼                                                                      │
│   2. SERVICE CREATES BOT                                                    │
│      → Recall.ai API: create bot                                           │
│      → Firestore: save meeting (status: joining)                           │
│      │                                                                      │
│      ▼                                                                      │
│   3. BOT JOINS MEETING                                                      │
│      → Bot appears in Zoom/Meet/Teams                                      │
│      → Records audio/video                                                  │
│      │                                                                      │
│      ▼                                                                      │
│   4. MEETING ENDS                                                           │
│      → Recall.ai webhook: bot.done                                         │
│      → Firestore: update (status: ended)                                   │
│      → Request async transcript                                             │
│      │                                                                      │
│      ▼                                                                      │
│   5. TRANSCRIPT READY                                                       │
│      → Recall.ai webhook: transcript.done                                  │
│      → Firestore: update (status: processing)                              │
│      │                                                                      │
│      ▼                                                                      │
│   6. SUMMARIZATION PIPELINE                                                 │
│      ┌─────────────────────────────────────────────────────────┐           │
│      │  a. Download transcript from Recall.ai                  │           │
│      │  b. Combine words into sentences                        │           │
│      │  c. Create time-based chunks (10 min each)              │           │
│      │  d. Send each chunk to Vertex AI (Gemini)               │           │
│      │  e. Generate overall summary                            │           │
│      │  f. Create Markdown study guide                         │           │
│      │  g. Convert to PDF                                      │           │
│      └─────────────────────────────────────────────────────────┘           │
│      │                                                                      │
│      ▼                                                                      │
│   7. SAVE OUTPUTS                                                           │
│      → Cloud Storage: upload all files                                     │
│      → Firestore: update (status: completed, outputs: {...})               │
│      │                                                                      │
│      ▼                                                                      │
│   8. USER DOWNLOADS                                                         │
│      GET /api/meetings/{id}/outputs                                        │
│      → Returns signed URLs for each file                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Considerations

### Authentication
- IAP ensures only authorized Google accounts can access
- Webhook endpoint is the only unauthenticated path
- Consider webhook signature verification for production

### Data Privacy
- All data stored in user's own GCP project
- No data leaves their cloud environment (except to Recall.ai/Vertex AI)
- Retention policy helps with compliance

### API Keys
- Stored in environment variables (Cloud Run secrets)
- Never logged or exposed in responses
- Recall.ai key is the only external service key

### Network Security
- All traffic over HTTPS
- Cloud Run provides automatic TLS
- No need for VPC for basic deployment

---

## Scaling Considerations

### Cloud Run
- Scales to zero when idle (cost savings)
- Auto-scales based on requests
- Max instances configurable (default: 10)

### Firestore
- Automatically scales
- No connection limits
- Consider indexes for high-volume queries

### Cloud Storage
- Unlimited storage
- No performance limits for typical usage
- Consider lifecycle rules for cost optimization

### Pipeline Processing
- Currently synchronous (blocking)
- For high volume, consider Cloud Tasks for async processing
- Each meeting processes independently

---

## Local Development

### Running Locally

```bash
# Clone and setup
git clone https://github.com/yourusername/meeting-transcription.git
cd meeting-transcription
pip install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your Recall.ai key

# Run
python main.py
```

### Local Storage

Without GCP credentials, the service uses local storage:
- Meetings: `outputs/meetings/*.json`
- Files: `outputs/{meeting_id}/*`

### Testing Webhooks

Use ngrok or similar to expose local server:

```bash
ngrok http 8080
# Use the ngrok URL as webhook in Recall.ai
```

---

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `RECALL_API_KEY` | Recall.ai API key | Required |
| `OUTPUT_BUCKET` | GCS bucket name | None (local) |
| `RETENTION_DAYS` | Days to keep data | 0 (forever) |
| `LLM_PROVIDER` | AI provider | vertex_ai |
| `GCP_PROJECT` | GCP project ID | Auto-detected |
| `GCP_REGION` | Region for Vertex AI | us-central1 |
| `PORT` | Server port | 8080 |
| `DEBUG` | Enable debug mode | false |

---

## Future Architecture (Enterprise)

The current architecture supports extension for enterprise features:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENTERPRISE EXTENSIONS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   MULTI-TENANT AUTH                                                         │
│   └── Firebase Auth / Okta / Azure AD                                      │
│       - Replace IAP with token-based auth                                  │
│       - User management, teams, roles                                      │
│       - SSO integration                                                     │
│                                                                             │
│   ADVANCED STORAGE                                                          │
│   └── Per-tenant isolation                                                 │
│       - Separate buckets per organization                                  │
│       - Encryption at rest with customer keys                              │
│       - Audit logging                                                       │
│                                                                             │
│   COMPLIANCE                                                                │
│   └── HIPAA, SOC2, GDPR                                                    │
│       - Data residency options                                             │
│       - Enhanced audit trails                                              │
│       - Data export/deletion APIs                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*Last updated: December 2025*

