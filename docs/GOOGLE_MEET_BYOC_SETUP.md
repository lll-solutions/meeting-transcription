# Google Meet Integration: BYOC OAuth Setup

Self-hosted deployments use **BYOC (Bring Your Own Credentials)** mode, where you create your own Google Cloud OAuth app in Internal mode for your Workspace domain.

## Prerequisites

- Google Workspace account (Google Meet transcripts require Workspace, not personal Gmail)
- Google Cloud project with billing enabled
- Admin access to Google Workspace (for Internal OAuth app approval)

## Step 1: Create a Google Cloud OAuth App

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Select or create a project
3. Navigate to **APIs & Services > OAuth consent screen**
4. Select **Internal** user type (restricts access to your Workspace domain)
5. Fill in the app details:
   - App name: "Meeting Transcription" (or your preferred name)
   - User support email: your admin email
   - Authorized domain: your domain
6. Click **Save and Continue**

## Step 2: Configure OAuth Scopes

Add these scopes on the Scopes page:

| Scope | Purpose |
|-------|---------|
| `openid` | User identity |
| `userinfo.email` | User email for account linking |
| `userinfo.profile` | Display name |
| `meetings.space.readonly` | Read Meet conference records and transcripts |
| `meetings.space.created` | Access transcripts from meetings the user created |

Click **Save and Continue**, then **Back to Dashboard**.

## Step 3: Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **+ Create Credentials > OAuth client ID**
3. Application type: **Web application**
4. Name: "Meeting Transcription"
5. Add **Authorized redirect URIs**:
   ```
   https://YOUR_SERVICE_URL/oauth/google/callback
   ```
   For local development:
   ```
   http://localhost:8080/oauth/google/callback
   ```
6. Click **Create** and note the **Client ID** and **Client Secret**

## Step 4: Enable Required APIs

In the Google Cloud Console, enable these APIs:

```bash
gcloud services enable meet.googleapis.com
gcloud services enable pubsub.googleapis.com
gcloud services enable workspaceevents.googleapis.com
```

Or search for each in **APIs & Services > Library**:
- Google Meet REST API
- Cloud Pub/Sub API
- Google Workspace Events API

## Step 5: Set Up Pub/Sub

The app auto-creates Pub/Sub resources on first use, but you can pre-create them:

```bash
# Create topic
gcloud pubsub topics create meet-transcript-events

# Create push subscription pointing to your service
gcloud pubsub subscriptions create meet-transcript-push \
  --topic=meet-transcript-events \
  --push-endpoint=https://YOUR_SERVICE_URL/webhook/google-meet
```

## Step 6: Configure Environment Variables

Set these environment variables in your deployment:

```bash
# Required: OAuth credentials from Step 3
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Required: Set mode to BYOC
GOOGLE_OAUTH_MODE=byoc

# Required: Your service URL (used for OAuth redirect and Pub/Sub push)
SERVICE_URL=https://your-service.example.com

# Optional: Override auto-detected redirect URI
# GOOGLE_OAUTH_REDIRECT_URI=https://your-service.example.com/oauth/google/callback

# Required: GCP project (usually already set for Cloud Run/GKE)
GOOGLE_CLOUD_PROJECT=your-gcp-project-id

# Optional: Override Pub/Sub defaults
# GOOGLE_PUBSUB_PROJECT_ID=your-gcp-project-id
# GOOGLE_PUBSUB_TOPIC=meet-transcript-events
# GOOGLE_PUBSUB_SUBSCRIPTION=meet-transcript-push
```

## Step 7: Connect Your Google Account

1. Open your deployment at `https://YOUR_SERVICE_URL/settings`
2. Click **Connect Google Meet**
3. Complete the OAuth consent flow
4. The app automatically creates a Workspace Events subscription for your account

## How It Works

Once connected:

1. You join or host a Google Meet with transcription enabled
2. When the meeting ends, Google generates the transcript
3. Google Workspace Events sends a notification to your Pub/Sub topic
4. Pub/Sub pushes the event to `/webhook/google-meet`
5. The app fetches the transcript via the Meet REST API
6. The transcript is processed through the AI pipeline automatically

## Troubleshooting

### "Google OAuth is not configured"
Verify `GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET` are set.

### OAuth redirect mismatch
Ensure the redirect URI in Google Cloud Console matches exactly:
`https://YOUR_SERVICE_URL/oauth/google/callback`

### No transcripts appearing
- Confirm transcription was enabled in the Google Meet settings
- Check that the Pub/Sub push subscription is healthy: `gcloud pubsub subscriptions describe meet-transcript-push`
- Verify your Workspace Events subscription hasn't expired (they last 7 days and auto-renew)
- Check the `/webhook/google-meet` endpoint logs for incoming events

### "Internal" app limitations
Internal OAuth apps are restricted to users within your Workspace domain. External users cannot connect. This is the recommended mode for self-hosted deployments.
