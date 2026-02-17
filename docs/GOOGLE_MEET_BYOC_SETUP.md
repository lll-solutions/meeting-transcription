# Google Meet Integration: BYOC OAuth Setup

Self-hosted deployments use **BYOC (Bring Your Own Credentials)** mode, where you create your own Google Cloud OAuth app in Internal mode for your Workspace domain.

> **Note:** The `setup.sh` script already enables the required GCP APIs (Meet, Pub/Sub, Workspace Events) and creates the Pub/Sub topic and push subscription. This guide only covers the OAuth app setup that must be done manually in the Google Cloud Console.

## Prerequisites

- Google Workspace account (Google Meet transcripts require Workspace, not personal Gmail)
- Completed `setup.sh` (which provisions APIs, Pub/Sub, and all other infrastructure)

## Step 1: Create a Google Cloud OAuth App

1. Go to [Google Cloud Console](https://console.cloud.google.com) and select your project
2. Navigate to **APIs & Services > OAuth consent screen**
3. Select **Internal** user type (restricts access to your Workspace domain)
4. Fill in the app details:
   - App name: "Meeting Transcription" (or your preferred name)
   - User support email: your admin email
   - Authorized domain: your domain
5. On the Scopes page, add these scopes:

| Scope | Purpose |
|-------|---------|
| `openid` | User identity |
| `userinfo.email` | User email for account linking |
| `userinfo.profile` | Display name |
| `meetings.space.readonly` | Read Meet conference records and transcripts |
| `meetings.space.created` | Access transcripts from meetings the user created |

6. Click **Save and Continue**, then **Back to Dashboard**

## Step 2: Create OAuth Credentials

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

## Step 3: Configure Environment Variables

Add these to your Cloud Run service (or `.env` for local dev):

```bash
# Required: OAuth credentials from Step 2
GOOGLE_OAUTH_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

# Required: Set mode to BYOC
GOOGLE_OAUTH_MODE=byoc
```

The remaining settings (`SERVICE_URL`, `GOOGLE_CLOUD_PROJECT`, Pub/Sub config) are already configured by `setup.sh`.

## Step 4: Connect Your Google Account

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
