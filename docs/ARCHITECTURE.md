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
│          │                   │                      │                       │
│          │                   │                      ▼                       │
│          ▼                   ▼              ┌──────────────┐                │
│   ┌─────────────┐     ┌─────────────┐      │ Cloud Tasks  │                │
│   │    IAP      │     │  Firestore  │◀─────│  (Async      │                │
│   │   (Auth)    │     │  (Metadata) │      │   Pipeline)  │                │
│   └─────────────┘     └─────────────┘      └──────┬───────┘                │
│                              │                     │                        │
│                              │                     ▼                        │
│                              │              ┌─────────────────────────────┐ │
│                              │              │       Vertex AI             │ │
│                              │              │  (Gemini Summarization)     │ │
│                              │              └─────────────────────────────┘ │
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

The service uses **JWT-based authentication** with database-stored user credentials. This provides:

- Email and password authentication
- Secure JWT tokens with httpOnly cookies
- OIDC token verification for internal service-to-service calls
- Webhook signature verification for Recall.ai events

### How Authentication Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AUTHENTICATION FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. User visits service URL                                                │
│      https://meeting-transcription-xxxxx-uc.a.run.app                      │
│                              │                                              │
│                              ▼                                              │
│   2. Login page (if not authenticated)                                      │
│      User enters email + password                                           │
│      POST /api/auth/login                                                   │
│                              │                                              │
│                              ▼                                              │
│   3. Server validates credentials                                           │
│      - Check password hash (bcrypt)                                         │
│      - Generate JWT token (signed with JWT_SECRET)                          │
│      - Set httpOnly cookie                                                  │
│                              │                                              │
│                              ▼                                              │
│   4. Subsequent requests include cookie                                     │
│      - Middleware validates JWT token                                       │
│      - Extracts user email from token                                       │
│      - Sets g.user for request context                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Configuration

Cloud Run is deployed with `--allow-unauthenticated` to handle authentication in application code:

```bash
gcloud run deploy meeting-transcription \
    --allow-unauthenticated \
    --set-secrets="JWT_SECRET=JWT_SECRET:latest,..."
```

### User Management

**Admin User Setup:**

During initial setup, an admin user is created via the `/api/auth/setup` endpoint:

```bash
curl -X POST https://your-service.run.app/api/auth/setup \
  -H "Content-Type: application/json" \
  -H "X-Setup-Key: ${SETUP_API_KEY}" \
  -d '{"email": "admin@example.com", "password": "...", "name": "Admin"}'
```

This endpoint is secured with a setup API key and can only be called once.

**Additional Users:**

Currently single-user deployment. Multi-user features planned for future releases.

### Protected Endpoints

Most API endpoints require authentication:

- `/api/meetings/*` - Meeting management
- `/api/transcripts/*` - Transcript operations
  - `POST /api/transcripts/upload` - Upload transcript file (JSON, VTT, or TXT)
- `/api/users/*` - User profile and settings

### Public Endpoints

These endpoints are accessible without authentication:

- `/health` - Health check
- `/webhook/recall` - Recall.ai webhook (verified via OIDC or signature)
- `/api/auth/login` - Login endpoint
- `/api/auth/setup` - One-time admin setup (requires setup key)

### Webhook Authentication

The `/webhook/recall` endpoint uses multiple verification methods:

1. **OIDC Token Verification** - For Cloud Tasks calling the service
2. **Webhook Signature** - Optional verification of Recall.ai webhook signatures

### Code Implementation

```python
from src.api.auth import AuthMiddleware

# Initialize auth middleware
auth = AuthMiddleware()

@app.before_request
def authenticate():
    """Authenticate requests before processing."""
    if auth.is_public_endpoint(request.path):
        return None

    # Verify JWT token from cookie
    user = auth.verify_jwt_token(request)
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    # Set user context
    g.user = user
```

### OIDC Verification (Service-to-Service)

Cloud Tasks uses OIDC tokens when calling back to the service:

```python
def verify_oidc_token(request, expected_audience):
    """Verify OIDC token from Cloud Tasks."""
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return False

    token = auth_header[7:]
    # Verify token signature and audience
    # Only accept tokens from our project's service account
    return validate_token(token, expected_audience)
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

#### 1. `bot.joining_call`

**Trigger**: Bot is joining/has joined the meeting
**Purpose**: Update status to show bot is active in the meeting
**Database Update**: Sets status to `in_meeting`

```json
{
  "event": "bot.joining_call",
  "data": {
    "bot": {
      "id": "bot-uuid"
    }
  }
}
```

**Handler**:
```python
if event == 'bot.joining_call':
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
**Purpose**: Queue the summarization pipeline via Cloud Tasks
**Database Update**: `status: "queued"` → `status: "processing"` (when task starts)

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

**Handler**: This queues processing via Cloud Tasks (async):
```python
elif event == 'transcript.done':
    transcript_id = data.get('data', {}).get('transcript', {}).get('id')
    recording_id = data.get('data', {}).get('recording', {}).get('id')

    # Find meeting ID for this transcript
    meeting_id = # ... lookup by transcript_id

    # Queue processing via Cloud Tasks (won't block webhook)
    create_cloud_task(
        url=f"/api/transcripts/process-recall/{meeting_id}",
        payload={"transcript_id": transcript_id, "recording_id": recording_id}
    )

    # Update status to queued
    storage.update_meeting(meeting_id, {"status": "queued"})
```

**Processing Flow**:
1. Webhook receives `transcript.done` → creates Cloud Task → returns immediately ✅
2. Cloud Tasks calls `/api/transcripts/process-recall/<meeting_id>` endpoint
3. Endpoint calls `process_transcript()` which runs the pipeline:
   - `status: "processing"` - Download transcript from Recall API
   - Combine words into sentences
   - Create educational chunks
   - LLM summarization (Vertex AI)
   - Generate study guide (Markdown)
   - Convert to PDF
   - `status: "completed"` - Upload all outputs to GCS

**Why Cloud Tasks?**
- Webhooks should respond quickly (< 10 seconds)
- Processing can take 1-5 minutes depending on transcript length
- Cloud Tasks handles retries and provides better observability

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
│   2. Webhook: bot.joining_call                                              │
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
| `joining` | `bot.joining_call` | `in_meeting` | Bot successfully entered |
| `in_meeting` | `bot.done` | `ended` | Meeting finished |
| `ended` | (internal) | `transcribing` | Transcript requested |
| `transcribing` | `transcript.done` | `processing` | Pipeline starts |
| `processing` | (internal) | `completed` | All outputs ready |
| Any | `transcript.failed` | `failed` | Error occurred |

---

## Data Flow

### Complete Pipeline Flow

#### Flow 1: Bot-Based Meeting Capture (Original)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BOT-BASED DATA FLOW                                 │
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

#### Flow 2: Direct Transcript Upload (New)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TRANSCRIPT UPLOAD DATA FLOW                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   1. USER UPLOADS TRANSCRIPT                                                │
│      POST /api/transcripts/upload                                          │
│      { transcript: "..." (JSON/VTT/TXT), title: "..." }                    │
│      │                                                                      │
│      ▼                                                                      │
│   2. FORMAT DETECTION & PARSING                                             │
│      ┌─────────────────────────────────────────────────────────┐           │
│      │  • Detect format (Recall JSON, VTT, or bracketed text)  │           │
│      │  • Parse to unified combined format                     │           │
│      │  • Validate structure and extract metadata              │           │
│      └─────────────────────────────────────────────────────────┘           │
│      → Firestore: save meeting (status: queued, id: upload-*)              │
│      → Cloud Tasks: enqueue processing task                                │
│      │                                                                      │
│      ▼                                                                      │
│   3. SUMMARIZATION PIPELINE                                                 │
│      ┌─────────────────────────────────────────────────────────┐           │
│      │  a. Load transcript from Firestore                      │           │
│      │  b. Combine words into sentences (or pass-through)      │           │
│      │  c. Create time-based chunks (10 min each)              │           │
│      │  d. Send each chunk to LLM (Gemini/OpenAI/Anthropic)    │           │
│      │  e. Generate overall summary                            │           │
│      │  f. Create Markdown study guide                         │           │
│      │  g. Convert to PDF                                      │           │
│      └─────────────────────────────────────────────────────────┘           │
│      │                                                                      │
│      ▼                                                                      │
│   4. SAVE OUTPUTS                                                           │
│      → Cloud Storage: upload all files                                     │
│      → Firestore: update (status: completed, outputs: {...})               │
│      │                                                                      │
│      ▼                                                                      │
│   5. USER DOWNLOADS                                                         │
│      GET /api/meetings/{id}/outputs                                        │
│      → Returns signed URLs for each file                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Supported Upload Formats**:
- **Recall.ai JSON** - Unified format with word-level timestamps
- **VTT (WebVTT)** - Zoom's native transcript export format
- **Bracketed Text** - Google Meet, legal depositions with `[HH:MM:SS]` timestamps

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

### Pipeline Modules

#### `src/pipeline/parse_text_transcript.py`

**Purpose**: Parse text-based transcript formats into unified combined format

**Functions**:
- `detect_text_transcript_format(text)` - Auto-detect transcript format (VTT, Google Meet, etc.)
- `parse_vtt_to_combined_format(text)` - Parse WebVTT format (Zoom native)
- `parse_bracketed_to_combined_format(text)` - Parse bracketed timestamp format (Google Meet)
- `parse_text_to_combined_format(text)` - Auto-detect and parse any supported text format

**Format Detection Logic**:
1. Check for `WEBVTT` header and VTT timestamp pattern → VTT format
2. Check for bracketed timestamps `[HH:MM:SS]` + speaker labels → Bracketed format
3. Otherwise → Unknown format (error)

**Output**: Unified combined format compatible with existing pipeline:
```python
[
  {
    "participant": {"id": 100, "name": "Speaker", ...},
    "text": "Full text of this segment",
    "start_timestamp": {"relative": 5.0, "absolute": None},
    "end_timestamp": {"relative": 8.0, "absolute": None},
    "word_count": 42
  }
]
```

#### `src/pipeline/combine_transcript_words.py`

**Purpose**: Convert word-level transcripts to sentence-level

**Smart Detection**:
- If transcript has `words` array → Combine words into text
- If transcript already has `text` field → Pass through unchanged

**Usage**:
```python
combine_transcript_words("raw.json", "combined.json")
# Auto-detects format and processes accordingly
```

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
| `RECALL_API_KEY` | Recall.ai API key (if bot joining enabled) | Optional |
| `JWT_SECRET` | Secret for signing JWT tokens | Required |
| `SETUP_API_KEY` | One-time setup endpoint key | Required |
| `OUTPUT_BUCKET` | GCS bucket name | None (local) |
| `RETENTION_DAYS` | Days to keep data | 0 (forever) |
| `LLM_PROVIDER` | AI provider (vertex_ai, azure_openai) | vertex_ai |
| `AUTH_PROVIDER` | Authentication provider | db |
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Auto-detected |
| `GCP_PROJECT_NUMBER` | GCP project number | Auto-detected |
| `GCP_REGION` | Region for Vertex AI | us-central1 |
| `SERVICE_URL` | Cloud Run service URL | Auto-detected |
| `FEATURES_BOT_JOINING` | Enable bot joining feature | true |
| `PORT` | Server port | 8080 |
| `DEBUG` | Enable debug mode | false |

---

## Future Architecture (Enterprise)

### Current Implementation (Single-User)

✅ **Already Implemented:**
- JWT-based authentication with secure httpOnly cookies
- Database-stored user credentials (bcrypt hashed)
- OIDC token verification for service-to-service calls
- Rate limiting (in-memory, per-instance)
- Plugin architecture for extensibility
- Optional bot joining (upload-only mode available)

### Planned Enterprise Extensions

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      ENTERPRISE EXTENSIONS                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   MULTI-TENANT AUTH                                                         │
│   └── SSO Integration (Okta / Azure AD / Google Workspace)                 │
│       - Multi-user teams and organizations                                 │
│       - Role-based access control (RBAC)                                   │
│       - User invitation and management APIs                                │
│       - Session management and activity logs                               │
│                                                                             │
│   ADVANCED STORAGE                                                          │
│   └── Per-organization isolation                                           │
│       - Separate buckets per organization                                  │
│       - Encryption at rest with customer-managed keys                      │
│       - Comprehensive audit logging                                         │
│       - Data retention policies per organization                           │
│                                                                             │
│   COMPLIANCE                                                                │
│   └── HIPAA, SOC2, GDPR                                                    │
│       - Data residency options (region selection)                          │
│       - Enhanced audit trails with tamper-proof logging                    │
│       - Data export/deletion APIs (GDPR right to be forgotten)             │
│       - BAA (Business Associate Agreement) support                         │
│                                                                             │
│   SCALABILITY                                                               │
│   └── Distributed rate limiting                                            │
│       - Redis/Memorystore for shared rate limits                           │
│       - Cloud CDN for static assets                                        │
│       - Multi-region deployment options                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

*Last updated: December 2025*

