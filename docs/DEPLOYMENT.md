# Deployment Guide

Deploy Meeting Transcription to Google Cloud Platform with **one click**.

## Prerequisites

You need 3 things before deploying. Use our **[Setup Helper](setup.html)** to guide you through each step!

### 1. Google Cloud Account (2 minutes)

**New to Google Cloud?** Get $300 in free credits:

[![Start Free Trial](https://img.shields.io/badge/Google%20Cloud-Start%20Free%20Trial-4285F4?style=for-the-badge&logo=google-cloud)](https://cloud.google.com/free)

This gives you:
- ✅ $300 free credits (valid 90 days)
- ✅ Always-free tier for Cloud Run
- ✅ No charge until you exceed free tier

**Already have Google Cloud?** Make sure billing is enabled on your project.

### 2. Recall.ai Account + API Key (2 minutes)

Sign up at [recall.ai](https://recall.ai) and get your API key from the Dashboard.

> 💡 **Free trial available!** Recall.ai offers free credits to get started.

### 3. AssemblyAI API Key (2 minutes)

Sign up at [assemblyai.com](https://www.assemblyai.com/) and get your API key.

> 💡 **Free trial available!** AssemblyAI includes free transcription hours.

**Important:** Configure your AssemblyAI key in your Recall.ai dashboard:
1. Go to [Recall.ai Dashboard](https://recall.ai/dashboard)
2. Navigate to Settings → Transcription
3. Paste your AssemblyAI API key

> 💡 AI summarization uses Google's Vertex AI which is automatically configured - no extra setup needed!

---

## One-Click Deploy to Google Cloud

### Step 1: Click the Button

[![Run on Google Cloud](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run)

This opens Google Cloud Console in your browser.

### Step 2: Sign In & Authorize

- Sign in with your Google account
- Authorize Cloud Shell to access your account
- Select or create a GCP project

### Step 3: Enter Your Recall.ai Key

You'll see a simple form with just 1 field:

| Field | What to Enter |
|-------|---------------|
| RECALL_API_KEY | Paste your Recall.ai API key |

That's all you need! Vertex AI (for Gemini) is automatically enabled in your project.

### Step 4: Deploy

Click **Deploy** and wait ~3 minutes.

### Step 5: Copy Your Service URL

When done, you'll see:

```
✓ Service deployed!
Service URL: https://meeting-transcription-abc123-uc.a.run.app
```

**Copy this URL** - you'll need it next.

---

## Configure Recall.ai Webhook

### Step 1: Go to Recall.ai Dashboard

Open [recall.ai/dashboard](https://recall.ai/dashboard) and sign in.

### Step 2: Add Webhook

Navigate to **Settings → Webhooks** and add:

```
https://YOUR-SERVICE-URL/webhook/recall
```

### Step 3: Enable Events

Check these webhook events:
- ✅ `bot.done`
- ✅ `transcript.done`  
- ✅ `recording.done`

### Step 4: Save

Click **Save** and you're done!

---

## Test Your Deployment

### Health Check

```bash
curl https://YOUR-SERVICE-URL/health
```

Should return: `{"status": "ok"}`

### Join a Test Meeting

```bash
curl -X POST https://YOUR-SERVICE-URL/api/meetings \
  -H "Content-Type: application/json" \
  -d '{
    "meeting_url": "https://zoom.us/j/YOUR_MEETING_ID",
    "join_at": "now"
  }'
```

The bot should join your meeting within 30 seconds!

---

## That's It! 🎉

Your meeting transcription service is now running. When the bot joins a meeting and the meeting ends:

1. Transcript is automatically generated
2. AI summarizes the content
3. PDF study guide is created

---

## Costs

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run | $0-5 (scales to zero) |
| Recall.ai | ~$0.02-0.05/minute recorded |
| Gemini | ~$0.001/1K tokens |

**Typical 1-hour meeting: ~$2-5 total**

---

## Updating Your Deployment

To update environment variables (like API keys):

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click on `meeting-transcription`
3. Click **Edit & Deploy New Revision**
4. Update variables under **Variables & Secrets**
5. Click **Deploy**

---

## Troubleshooting

### "Bot won't join meeting"
- Check Recall.ai API key is correct
- Verify meeting URL format
- Check [Cloud Run logs](https://console.cloud.google.com/run) → your service → Logs

### "Webhook not working"
- Verify webhook URL in Recall.ai dashboard
- Make sure you copied the full URL including `https://`
- Check that `/webhook/recall` is at the end

### "No summary generated"
- Check LLM provider API key
- Verify you have quota/credits with your LLM provider
- Check Cloud Run logs for errors

### View Logs

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Click `meeting-transcription`
3. Click **Logs** tab

---

## Deleting the Deployment

To remove everything:

1. Go to [Cloud Run Console](https://console.cloud.google.com/run)
2. Select `meeting-transcription`
3. Click **Delete**

---

## Need Help?

- 📚 [Documentation](../README.md)
- 🐛 [Report Issues](https://github.com/yourusername/meeting-transcription/issues)
- 📧 [Contact](mailto:kurt@lll-solutions.com)
