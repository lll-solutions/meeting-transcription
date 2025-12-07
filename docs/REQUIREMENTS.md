# Functional Requirements Document

**Project**: Meeting Transcription & Summarization Pipeline  
**Version**: 1.0  
**Date**: December 2025  
**Author**: LLL Solutions

---

## 1. Executive Summary

This document outlines the functional requirements for an open-source meeting transcription and summarization system. The system enables users to automatically record, transcribe, and summarize video meetings (Zoom, Google Meet, Microsoft Teams) into structured study guides and PDF documents.

### 1.1 Goals

- Provide an easy-to-deploy, self-hosted meeting transcription solution
- Support multiple LLM providers (Google Gemini, Azure OpenAI, OpenAI, Anthropic)
- Generate educational study guides from meeting content
- Enable one-click deployment to Google Cloud Platform

### 1.2 Non-Goals (v1.0)

- Real-time transcription display during meetings
- Video recording storage/playback
- Multi-language transcription (English only for v1.0)
- Mobile applications

---

## 2. User Personas

### 2.1 Educator/Instructor
- **Needs**: Record classes, generate study materials for students
- **Technical Level**: Low to Medium
- **Primary Use**: Post-class summary generation

### 2.2 Corporate Training Manager
- **Needs**: Document training sessions, create reference materials
- **Technical Level**: Medium
- **Primary Use**: Training documentation and compliance

### 2.3 Developer/Self-Hoster
- **Needs**: Deploy and customize for organization
- **Technical Level**: High
- **Primary Use**: Integration with existing systems

---

## 3. Functional Requirements

### 3.1 Meeting Bot Management

#### FR-3.1.1: Schedule Bot to Join Meeting
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | User can schedule a bot to join a meeting at a specific time |
| Input | Meeting URL, Join Time (or "join now"), Bot Display Name |
| Output | Confirmation with Bot ID and scheduled join time |
| Acceptance Criteria | Bot appears in meeting within 30 seconds of scheduled time |

**API Endpoint**:
```
POST /api/meetings
{
  "meeting_url": "https://zoom.us/j/123456789",
  "join_at": "2025-12-07T14:00:00Z",  // or "now"
  "bot_name": "Meeting Assistant"
}
```

#### FR-3.1.2: Join Meeting Immediately
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | User can make bot join a meeting immediately |
| Input | Meeting URL, Bot Display Name (optional) |
| Output | Confirmation with Bot ID |
| Acceptance Criteria | Bot joins within 30 seconds of request |

#### FR-3.1.3: Remove Bot from Meeting
**Priority**: P1 (Should Have)

| Attribute | Description |
|-----------|-------------|
| Description | User can remove bot from an active meeting |
| Input | Bot ID or Meeting ID |
| Output | Confirmation of bot removal |
| Acceptance Criteria | Bot leaves meeting within 10 seconds |

#### FR-3.1.4: List Active Bots
**Priority**: P1 (Should Have)

| Attribute | Description |
|-----------|-------------|
| Description | User can see all active bots and their status |
| Input | None |
| Output | List of bots with status, meeting info, duration |

---

### 3.2 Transcription

#### FR-3.2.1: Automatic Transcription on Meeting End
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | System automatically generates transcript when meeting ends |
| Input | Recording from meeting |
| Output | JSON transcript with speaker labels and timestamps |
| Acceptance Criteria | Transcript available within 5 minutes of meeting end |

**Transcript Format**:
```json
{
  "meeting_id": "uuid",
  "duration_seconds": 3600,
  "participants": [
    {"id": "p1", "name": "John Doe"}
  ],
  "segments": [
    {
      "participant": {"id": "p1", "name": "John Doe"},
      "text": "Welcome to today's class...",
      "start_timestamp": {"relative_time_s": 0.0},
      "end_timestamp": {"relative_time_s": 5.2},
      "words": [...]
    }
  ]
}
```

#### FR-3.2.2: Speaker Identification
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Transcript includes speaker identification |
| Input | Audio with multiple speakers |
| Output | Labeled transcript segments per speaker |
| Acceptance Criteria | 90%+ accuracy on speaker identification |

---

### 3.3 AI Summarization Pipeline

#### FR-3.3.1: Chunk-Based Processing
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Break transcript into time-based chunks for LLM processing |
| Input | Combined transcript JSON |
| Output | Chunked transcript (default: 10-minute segments) |
| Config | Chunk size configurable (5-15 minutes) |

#### FR-3.3.2: LLM Provider Selection
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Support multiple LLM providers |
| Providers | Google Gemini, Azure OpenAI, OpenAI, Anthropic Claude |
| Config | Provider and model configurable via environment variables |

**Environment Variables**:
```bash
# Google Gemini (recommended for GCP deployment)
GOOGLE_API_KEY=your_gemini_api_key
LLM_PROVIDER=gemini
LLM_MODEL=gemini-1.5-pro

# Azure OpenAI
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-4o
LLM_PROVIDER=azure_openai

# OpenAI
OPENAI_API_KEY=your_key
LLM_PROVIDER=openai
LLM_MODEL=gpt-4-turbo

# Anthropic
ANTHROPIC_API_KEY=your_key
LLM_PROVIDER=anthropic
LLM_MODEL=claude-3-5-sonnet-20241022
```

#### FR-3.3.3: Educational Summary Generation
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Generate structured educational summary from transcript |
| Input | Chunked transcript |
| Output | JSON summary with structured fields |

**Summary Structure**:
```json
{
  "metadata": {
    "instructor": "Name",
    "duration_minutes": 60,
    "meeting_date": "2025-12-07"
  },
  "overall_summary": {
    "executive_summary": "...",
    "learning_objectives": [...],
    "key_concepts": [
      {
        "name": "Concept Name",
        "definition": "...",
        "examples": [...]
      }
    ],
    "tools_frameworks": [...],
    "qa_exchanges": [...]
  },
  "action_items": {
    "student_assignments": [...],
    "instructor_commitments": [...],
    "preparation_for_next_class": [...]
  },
  "chunk_analyses": [...]
}
```

---

### 3.4 Output Generation

#### FR-3.4.1: Markdown Study Guide
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Generate formatted Markdown study guide |
| Input | Summary JSON |
| Output | .md file with structured content |
| Sections | Executive Summary, Key Concepts, Tools, Q&A, Timeline, Action Items |

#### FR-3.4.2: PDF Generation
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Convert Markdown to professional PDF |
| Input | Markdown study guide |
| Output | .pdf file |
| Styling | Professional typography, headers, table of contents |

---

### 3.5 Deployment & Configuration

#### FR-3.5.1: Google Cloud Deployment
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | One-click deployment to Google Cloud |
| Components | Cloud Run (API), Secret Manager (keys), Cloud Storage (output) |
| Config | Terraform or Deployment Manager templates |

#### FR-3.5.2: Secret Management
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Secure storage of API keys |
| Implementation | Google Secret Manager |
| Keys Stored | Recall.ai API key, LLM provider keys |

#### FR-3.5.3: Webhook Endpoint
**Priority**: P0 (Must Have)

| Attribute | Description |
|-----------|-------------|
| Description | Receive webhook events from Recall.ai |
| Events | bot.done, transcript.done, recording.done |
| Security | Webhook signature verification |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Requirement | Target |
|-------------|--------|
| Bot join latency | < 30 seconds |
| Transcript availability | < 5 minutes after meeting end |
| Summary generation | < 10 minutes for 2-hour meeting |
| API response time | < 500ms for status checks |

### 4.2 Scalability

| Requirement | Target |
|-------------|--------|
| Concurrent meetings | 10+ (limited by Recall.ai account) |
| Meeting duration | Up to 4 hours |
| Cloud Run scaling | 0-10 instances (auto) |

### 4.3 Security

| Requirement | Implementation |
|-------------|----------------|
| API Keys | Stored in Secret Manager, never in code |
| HTTPS | Required for all endpoints |
| Webhook Security | Signature verification |
| Data Retention | Configurable (default: 30 days) |

### 4.4 Availability

| Requirement | Target |
|-------------|--------|
| Service Uptime | 99.5% (Cloud Run SLA) |
| Recovery Time | < 5 minutes (auto-restart) |

---

## 5. User Interface Requirements

### 5.1 Web Dashboard (v1.0 - Minimal)
**Priority**: P2 (Nice to Have)

| Feature | Description |
|---------|-------------|
| Schedule Meeting | Form to input meeting URL and time |
| View Status | List of active/completed meetings |
| Download Output | Links to PDF/Markdown files |

### 5.2 CLI Interface (v1.0)
**Priority**: P1 (Should Have)

```bash
# Schedule a meeting
meeting-bot schedule --url "https://zoom.us/j/123" --time "2025-12-07T14:00:00Z"

# Join immediately
meeting-bot join --url "https://zoom.us/j/123"

# Check status
meeting-bot status

# List outputs
meeting-bot outputs --meeting-id <id>
```

---

## 6. API Specification

### 6.1 Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/meetings | Schedule/join a meeting |
| GET | /api/meetings | List all meetings |
| GET | /api/meetings/{id} | Get meeting status |
| DELETE | /api/meetings/{id} | Remove bot from meeting |
| GET | /api/meetings/{id}/transcript | Get transcript |
| GET | /api/meetings/{id}/summary | Get summary JSON |
| GET | /api/meetings/{id}/study-guide | Get Markdown |
| GET | /api/meetings/{id}/pdf | Get PDF |
| POST | /webhook/recall | Recall.ai webhook endpoint |

### 6.2 Request/Response Examples

**Schedule Meeting**:
```bash
curl -X POST https://your-service.run.app/api/meetings \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://zoom.us/j/123456789",
    "join_at": "now",
    "bot_name": "Study Bot"
  }'
```

**Response**:
```json
{
  "id": "meeting-uuid",
  "bot_id": "bot-uuid",
  "status": "joining",
  "meeting_url": "https://zoom.us/j/123456789",
  "created_at": "2025-12-07T14:00:00Z"
}
```

---

## 7. Data Flow

```
1. User submits meeting URL
         │
         ▼
2. System calls Recall.ai to create bot
         │
         ▼
3. Bot joins meeting at scheduled time
         │
         ▼
4. Meeting ends, Recall.ai triggers webhook
         │
         ▼
5. System requests async transcript from Recall.ai
         │
         ▼
6. Transcript ready, webhook received
         │
         ▼
7. Pipeline processes transcript:
   a. Combine words into segments
   b. Create time-based chunks
   c. Analyze each chunk with LLM
   d. Generate overall summary
   e. Extract action items
         │
         ▼
8. Generate Markdown study guide
         │
         ▼
9. Convert to PDF
         │
         ▼
10. Store outputs, notify user
```

---

## 8. Configuration Options

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| RECALL_API_KEY | Recall.ai API key | - | Yes |
| LLM_PROVIDER | gemini, azure_openai, openai, anthropic | gemini | Yes |
| LLM_MODEL | Model name | Provider default | No |
| GOOGLE_API_KEY | Gemini API key | - | If using Gemini |
| AZURE_OPENAI_API_KEY | Azure OpenAI key | - | If using Azure |
| AZURE_OPENAI_ENDPOINT | Azure endpoint | - | If using Azure |
| AZURE_OPENAI_DEPLOYMENT | Deployment name | gpt-4o | If using Azure |
| OPENAI_API_KEY | OpenAI key | - | If using OpenAI |
| ANTHROPIC_API_KEY | Anthropic key | - | If using Claude |
| CHUNK_SIZE_MINUTES | Transcript chunk size | 10 | No |
| WEBHOOK_SECRET | Webhook verification | - | Recommended |
| OUTPUT_BUCKET | GCS bucket for outputs | - | For GCP deploy |

---

## 9. Future Enhancements (Post v1.0)

### 9.1 Free & Open Source Alternatives (High Priority)

| Feature | Priority | Description |
|---------|----------|-------------|
| **Whisper Transcription** | P1 | Use OpenAI Whisper (open source) instead of AssemblyAI |
| **Local LLM Support** | P1 | Use Ollama/llama.cpp for summarization without API costs |
| **File Upload Mode** | P1 | Upload recordings from Google Drive, Dropbox, or local files |
| **Open Source Bot** | P2 | Alternative to Recall.ai using open source meeting SDKs |

### 9.2 Zero-Cost Mode

Enable users to run the entire pipeline with no API costs:
- **Input**: Upload recording file (MP4, WebM, MP3, WAV)
- **Transcription**: Whisper running locally or on Cloud Run
- **Summarization**: Local LLM via Ollama
- **Output**: Same Markdown/PDF study guides

### 9.3 Additional Features

| Feature | Priority | Description |
|---------|----------|-------------|
| Real-time transcription | P2 | Stream transcript during meeting |
| Multi-language | P2 | Support non-English transcription |
| Custom prompts | P2 | User-configurable summarization prompts |
| Quiz generation | P3 | Auto-generate quizzes from content |
| Slide integration | P3 | Sync with presentation slides |
| Calendar integration | P2 | Auto-schedule from Google/Outlook calendar |
| Mobile app | P3 | iOS/Android companion app |
| HIPAA compliance | P1 | For healthcare use cases |

---

## 10. Success Metrics

| Metric | Target |
|--------|--------|
| Deployment success rate | > 95% of users can deploy in < 30 min |
| Transcription accuracy | > 95% word accuracy |
| Summary usefulness | > 4.0/5.0 user rating |
| System reliability | > 99% successful meeting captures |

---

## Appendix A: Supported Meeting Platforms

| Platform | Support Level | Notes |
|----------|---------------|-------|
| Zoom | Full | Tested extensively |
| Google Meet | Full | Requires guest access |
| Microsoft Teams | Full | Requires guest access |
| Webex | Partial | Basic support via Recall.ai |

---

## Appendix B: LLM Provider Comparison

| Provider | Model | Context | Cost/1K tokens | Best For |
|----------|-------|---------|----------------|----------|
| Google Gemini | gemini-1.5-pro | 1M tokens | $0.00125 | GCP users, cost |
| Azure OpenAI | gpt-4o | 128K tokens | $0.005-0.015 | Enterprise, Azure users |
| OpenAI | gpt-4-turbo | 128K tokens | $0.01-0.03 | General purpose |
| Anthropic | claude-3.5-sonnet | 200K tokens | $0.003-0.015 | Long context, accuracy |

---

*Document Version: 1.0*  
*Last Updated: December 2025*

