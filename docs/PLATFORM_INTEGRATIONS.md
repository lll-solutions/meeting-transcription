# Design Doc: Replace Recall.ai with Direct Meeting Platform Integrations

## Overview

Replace the Recall.ai dependency in the [meeting-transcription OSS project](https://github.com/lll-solutions/meeting-transcription) with direct integrations to Google Meet and Zoom APIs for automatic transcript retrieval. This enables HIPAA-compliant meeting transcription without requiring a BAA from Recall.ai.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Code location | OSS meeting-transcription repo | Aligns with OSS approach, benefits community |
| Manual upload | Keep as fallback | For users on lower Workspace tiers |
| OAuth model | **Hybrid** | Shared subdomain OAuth + BYOC option |
| Timing | Google Meet first, Zoom later | Leverage existing Google OAuth |

## Current State

- **therapy-assistant-platform**: Manual transcript upload (VTT/JSON/TXT files), React frontend
- **meeting-transcription** (OSS): Uses Recall.ai bot for meeting capture, Flask web UI
- **Google OAuth**: Already implemented for user authentication (basic scopes only)

## Repo Relationship

```
meeting-transcription (OSS)          therapy-assistant-platform
├── src/providers/     ◄──────────── imports as dependency
├── Flask UI (standalone users)      ├── React UI (SaaS users)
└── Recall.ai, Google, Zoom          └── Uses same providers
```

Both repos need UI changes, but they share the backend provider code.

## Target Architecture

```
User schedules meeting → Platform monitors via webhooks →
Meeting ends → Transcript becomes available →
Platform fetches transcript → Processes via existing pipeline
```

---

## OAuth Deployment Model (Hybrid)

### For SaaS Customers (Shared OAuth)
- All customers on subdomains: `drsmith.therapy-platform.com`
- Single OAuth app with one callback URL
- You complete Google OAuth verification once
- Stays under Google's 10-domain limit

### For Enterprise / Self-Hosters (BYOC)
- Customer provides their own Google Cloud OAuth credentials
- Uses **Internal mode** on their Workspace domain
- **No verification required** - works immediately
- Full isolation and control

### Implementation
```python
# Environment variables per deployment
GOOGLE_CLIENT_ID=...           # Default: your verified app
GOOGLE_CLIENT_SECRET=...       # Default: your verified app
GOOGLE_OAUTH_MODE=shared|byoc  # Which mode
```

---

## Google Meet Integration (Epic 1 - Priority)

### API Approach

| Component | API | Purpose |
|-----------|-----|---------|
| Subscribe to events | [Google Workspace Events API v1](https://developers.google.com/workspace/events) | Webhook notifications |
| Get transcript data | [Meet REST API v2](https://developers.google.com/workspace/meet/api/guides/overview) | Fetch transcript entries |
| Event type | `google.workspace.meet.transcript.v2.fileGenerated` | Triggers when transcript ready |

### OAuth Scopes Required

```
https://www.googleapis.com/auth/meetings.space.readonly  # Read transcripts
https://www.googleapis.com/auth/meetings.space.created   # Alternative scope
```

### Verification Requirements by Deployment Mode

| Mode | Verification | Wait Time | Notes |
|------|--------------|-----------|-------|
| **BYOC + Internal** | None | Immediate | Workspace users only, no warnings |
| **BYOC + Testing** | None | Immediate | 100 user limit, "unverified" warning |
| **Shared (SaaS)** | Full verification | 4-7 weeks | One-time, benefits all customers |

**Workspace tier requirement**: Business Standard, Enterprise, or Education Plus (for transcript access)

### Implementation Tasks

1. **Extend OAuth flow** - Add Meet scopes to existing Google OAuth
2. **Create Pub/Sub subscription** - Receive transcript events via Cloud Pub/Sub
3. **Implement transcript fetcher** - Call Meet API when event received
4. **Map to existing format** - Convert Meet transcript to VTT/JSON format
5. **Trigger processing pipeline** - Feed into existing SOAP generation

### Data Flow

```
1. User links Google account (OAuth with Meet scopes)
2. App subscribes to user's meeting space events via Workspace Events API
3. User conducts meeting with transcription enabled
4. Meeting ends → Google processes transcript
5. Pub/Sub receives `transcript.v2.fileGenerated` event
6. Backend fetches transcript via Meet REST API
7. Transcript parsed and fed to existing pipeline
```

### Limitations

- **Post-meeting only** - No live transcription access
- **Workspace tier requirement** - Business Standard, Enterprise, or Education Plus
- **30-day retention** - Transcript entries expire after 30 days
- **Organizer ownership** - Transcripts stored in organizer's Drive

---

## Zoom Integration (Epic 2)

### API Approach

| Component | API | Purpose |
|-----------|-----|---------|
| Webhook events | [Zoom Webhooks](https://developers.zoom.us/docs/api/rest/webhook-reference/) | `recording.transcript_completed` |
| Get transcript | [Recordings API](https://developers.zoom.us/docs/api/rest/reference/zoom-api/methods/#operation/recordingGet) | Download VTT file |

### App Type & Scopes

**Must use General App** (not Server-to-Server OAuth):
- `cloud_recording:read:list_recording_files`
- `recording:read:admin`

**Marketplace Requirements**:
- Create General App (unlisted for private use)
- Zoom app review process (~4 weeks)
- Users must OAuth the Zoom app

### Implementation Tasks

1. **Create Zoom Marketplace app** - General app type, unlisted
2. **Implement OAuth flow** - Separate from Google OAuth
3. **Register webhook endpoint** - For `recording.transcript_completed`
4. **Download transcript** - VTT file from Zoom's CDN
5. **Parse and process** - Feed to existing pipeline

### Prerequisites for Users

- Zoom Cloud Recording enabled (not local recording)
- Audio transcript setting enabled in Zoom account
- Only host can initiate cloud recording

### Processing Time

Transcripts take ~2x meeting duration to process (30-min meeting = ~1 hour wait). Can take up to 24 hours under high load.

---

## Epic Breakdown

### Epic 1: Google Meet Transcript Integration
**Issue**: `meeting-transcription-zko`
**Complexity**: High | **Priority**: P1

| Task | Type | Description |
|------|------|-------------|
| 1.1 | Backend | Implement hybrid OAuth config (shared vs BYOC mode) |
| 1.2 | Backend | Extend Google OAuth to include Meet scopes |
| 1.3 | Infra | Set up Cloud Pub/Sub topic and subscription |
| 1.4 | Backend | Implement Workspace Events API subscription manager |
| 1.5 | Backend | Create Pub/Sub push handler for transcript events |
| 1.6 | Backend | Implement Meet REST API client for transcript fetch |
| 1.7 | Backend | Parse Meet transcript format to internal format |
| 1.8 | Backend | Auto-trigger session creation from transcript |
| 1.9 | Frontend | UI for linking/unlinking Google Meet integration |
| 1.10 | Frontend | Display pending transcripts and processing status |
| 1.11 | Testing | Integration tests with mock Pub/Sub |
| 1.12 | Docs | Self-hoster guide: BYOC OAuth setup (Internal mode) |
| 1.13 | Docs | SaaS guide: How transcript sync works |

### Epic 2: Zoom Transcript Integration
**Issue**: `meeting-transcription-cjf`
**Complexity**: High | **Priority**: P2 (after Google Meet works)

| Task | Type | Description |
|------|------|-------------|
| 2.1 | Setup | Create Zoom Marketplace app (unlisted/internal) |
| 2.2 | Backend | Implement Zoom OAuth flow (separate from Google) |
| 2.3 | Backend | Store Zoom OAuth tokens per user (encrypted) |
| 2.4 | Backend | Create webhook endpoint for `recording.transcript_completed` |
| 2.5 | Backend | Implement transcript download from Zoom CDN |
| 2.6 | Backend | Parse Zoom VTT format to internal format |
| 2.7 | Backend | Auto-trigger session creation from Zoom transcript |
| 2.8 | Frontend | UI for connecting/disconnecting Zoom account |
| 2.9 | Frontend | Zoom connection status indicator |
| 2.10 | Testing | Integration tests with webhook simulation |
| 2.11 | Docs | Zoom integration guide for self-hosters |

### Epic 3: OSS Architecture Refactoring (Backend)
**Issue**: `meeting-transcription-76x`
**Complexity**: Medium | **Priority**: P1 (foundation for Epics 1 & 2)

| Task | Type | Description |
|------|------|-------------|
| 3.1 | Refactor | Define `TranscriptProvider` interface (abstract base) |
| 3.2 | Refactor | Extract Recall.ai code into `RecallProvider` class |
| 3.3 | Feature | Implement `GoogleMeetProvider` class |
| 3.4 | Feature | Implement `ZoomProvider` class |
| 3.5 | Feature | Implement `ManualUploadProvider` (existing behavior) |
| 3.6 | Config | Provider selection via environment variable |
| 3.7 | Docs | Update README with provider options and setup guides |

### Epic 4: Maintain Manual Upload Fallback
**Issue**: `THERAPY-zub` (therapy-assistant-platform repo)
**Complexity**: Low | **Priority**: P2

| Task | Type | Description |
|------|------|-------------|
| 4.1 | UI | Keep existing upload dialog for users without integrations |
| 4.2 | UI | Add "Connect Google Meet" / "Connect Zoom" CTAs |
| 4.3 | Backend | Ensure both paths (manual + auto) feed same pipeline |

### Epic 5: OSS Flask UI Updates
**Issue**: `meeting-transcription-nyo`
**Complexity**: Medium | **Priority**: P1 (required for standalone OSS users)

| Task | Type | Description |
|------|------|-------------|
| 5.1 | Backend | Add Flask routes for Google OAuth flow |
| 5.2 | Backend | Add Flask routes for Zoom OAuth flow |
| 5.3 | Backend | Store OAuth tokens in Firestore (encrypted) |
| 5.4 | UI | Settings page: provider selector (Recall / Google / Zoom) |
| 5.5 | UI | "Connect Google Meet" button + OAuth redirect |
| 5.6 | UI | "Connect Zoom" button + OAuth redirect |
| 5.7 | UI | Account connection status indicators |
| 5.8 | UI | Pending transcripts list (meetings awaiting processing) |
| 5.9 | UI | BYOC credentials input (for self-hosters using own OAuth app) |
| 5.10 | Docs | Setup guide for standalone deployers

---

## Implementation Order

```
Epic 3 (OSS Backend Refactoring)   ← Foundation: provider abstraction
    ↓
Epic 5 (OSS Flask UI)              ← UI for OAuth + config (standalone users)
    ↓
Epic 1 (Google Meet Provider)      ← Primary integration
    ↓
Epic 4 (Manual Upload Fallback)    ← Ensure fallback works
    ↓
Epic 2 (Zoom Provider)             ← Secondary integration
```

**Rationale**:
- Epic 3 creates the provider abstraction that all others depend on
- Epic 5 gives OSS standalone users a working UI for OAuth
- Epic 1 (Google Meet) comes before Epic 2 (Zoom) since you already have Google OAuth
- therapy-assistant-platform can reuse provider code but builds its own React UI

---

## Key Files to Modify

### meeting-transcription OSS repo (Backend)
- `src/providers/` (new) - Provider interface and implementations
- `src/bot/` - Extract Recall.ai code into RecallProvider
- `src/auth/` (new) - Google/Zoom OAuth handlers
- `pyproject.toml` - Optional Google/Zoom dependencies
- `README.md` - Provider documentation

### meeting-transcription OSS repo (Flask UI)
- `templates/settings.html` (new) - Provider configuration page
- `templates/components/` - OAuth buttons, status indicators
- `static/js/oauth.js` (new) - OAuth redirect handling
- `main.py` - Add OAuth routes
- `src/storage/` - OAuth token storage

### therapy-assistant-platform
- `backend/app/auth/google_oauth.py` - Add Meet scopes
- `backend/app/settings.py` - BYOC OAuth config
- `frontend/src/lib/auth.ts` - Extended OAuth flow
- `frontend/src/components/settings/` (new) - Integration connection UI

---

## Verification Plan

1. **Unit tests**: Mock provider interfaces
2. **Integration tests**: Mock Pub/Sub and webhook endpoints
3. **Manual testing**:
   - Create test meeting with transcription enabled
   - End meeting, wait for transcript processing
   - Verify transcript appears in platform automatically
4. **BYOC testing**: Deploy with customer-provided OAuth credentials

---

## Sources

- [Google Workspace Events API](https://developers.google.com/workspace/events)
- [Subscribe to Google Meet events](https://developers.google.com/workspace/events/guides/events-meet)
- [Google Meet REST API overview](https://developers.google.com/workspace/meet/api/guides/overview)
- [Working with Meet artifacts](https://developers.google.com/workspace/meet/api/guides/artifacts)
- [When Google verification is not needed](https://support.google.com/cloud/answer/13464323)
- [Google OAuth domain limit](https://support.google.com/cloud/answer/7650096)
- [Zoom Cloud Recording API tutorial](https://www.recall.ai/blog/zoom-transcript-api)
- [Zoom OAuth scopes by app type](https://www.recall.ai/blog/why-some-zoom-api-scopes-are-only-available-in-certain-app-types)
- [Zoom internal apps](https://developers.zoom.us/docs/internal-apps/s2s-oauth/)
- [Getting transcripts from Zoom](https://www.recall.ai/blog/how-to-get-transcripts-from-zoom)
