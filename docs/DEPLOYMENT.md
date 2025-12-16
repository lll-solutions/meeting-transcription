# Deployment Guide

Deploy Meeting Transcription to Google Cloud Platform in about 15 minutes using our automated setup wizard.

## Prerequisites

### 1. Google Cloud Account

**New to Google Cloud?** Get $300 in free credits:

[![Start Free Trial](https://img.shields.io/badge/Google%20Cloud-Start%20Free%20Trial-4285F4?style=for-the-badge&logo=google-cloud)](https://cloud.google.com/free)

This gives you:
- ✅ $300 free credits (valid 90 days)
- ✅ Always-free tier for Cloud Run
- ✅ No charge until you exceed free tier

**Already have Google Cloud?** Make sure billing is enabled on your project.

### 2. Recall.ai Account + API Key (Optional)

**Only needed if you want the bot to join live meetings.**

Sign up at [recall.ai](https://recall.ai) and get your API key from the Dashboard.

> 💡 **Free trial available!** Recall.ai offers free credits to get started.

**Configure transcription:** The setup uses Recall.ai's built-in transcription. Optionally configure AssemblyAI in your Recall.ai dashboard for higher quality transcripts:
1. Go to [Recall.ai Dashboard](https://recall.ai/dashboard)
2. Navigate to Settings → Transcription
3. Add your AssemblyAI API key (optional)

> 💡 AI summarization uses Google's Vertex AI which is automatically configured during setup!

---

## Deploy to Google Cloud

### Step 1: Open in Google Cloud Shell

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/lll-solutions/meeting-transcription.git&cloudshell_open_in_editor=README.md&cloudshell_workspace=.)

This opens the repository in Google Cloud Shell (a browser-based terminal).

### Step 2: Run the Setup Script

Once Cloud Shell opens, run:

```bash
./setup.sh
```

### Step 3: Follow the Setup Wizard

The wizard will guide you through:

**Project Setup:**
- Create a new GCP project or use an existing one
- Link billing account
- Enable required APIs (Cloud Run, Firestore, Vertex AI, etc.)

**Feature Configuration:**
- **Bot Joining**: Choose whether to enable live meeting bots (requires Recall.ai) or upload-only mode
- **LLM Provider**: Select Vertex AI (Gemini) or Azure OpenAI for AI summarization

**Admin User:**
- Set up initial admin account (email and password)
- Creates secure JWT secret and API keys

**Deployment:**
- Deploys to Cloud Run (~5 minutes)
- Sets up Cloud Tasks for background processing
- Creates Firestore indexes

**Total time: ~15 minutes**

### Step 4: Copy Your Service URL

When complete, you'll see:

```
╔═══════════════════════════════════════════════════════════════╗
║                    🎉 SETUP COMPLETE! 🎉                       ║
╚═══════════════════════════════════════════════════════════════╝

Your service is live at:

  https://meeting-transcription-abc123-uc.a.run.app

🔐 Login Credentials:
  Email:    admin@example.com
  Password: your-password
```

**Save these credentials!** You'll need them to log in.

---

## Configure Recall.ai Webhook

**Note:** Only needed if you enabled bot joining during setup.

### Step 1: Go to Recall.ai Dashboard

Open [recall.ai/dashboard](https://recall.ai/dashboard) and sign in.

### Step 2: Add Webhook

Navigate to **Settings → Webhooks** and add:

```
https://YOUR-SERVICE-URL/webhook/recall
```

Replace `YOUR-SERVICE-URL` with your actual Cloud Run URL from the setup output.

### Step 3: Enable Events

Check these webhook events:
- ✅ `bot.joining_call` - Updates status when bot enters meeting
- ✅ `bot.done` - Triggers transcript request when meeting ends
- ✅ `bot.call_ended` - Alternative meeting end event
- ✅ `recording.done` - Recording processing complete
- ✅ `transcript.done` - Triggers AI processing pipeline
- ✅ `transcript.failed` - Alerts when transcription fails

### Step 4: Save

Click **Save** and you're done!

> 💡 **Optional:** For additional security, you can configure a webhook secret. See the setup script output for instructions.

---

## Test Your Deployment

### Web Interface

1. Open your service URL in a browser:
   ```
   https://YOUR-SERVICE-URL
   ```

2. Log in with your admin credentials (from setup output)

3. Try the features:
   - **Upload a transcript** (if you have a test transcript file)
   - **Schedule a bot** to join a meeting (if bot joining is enabled)
   - View your meetings and download outputs

### Health Check (API)

```bash
curl https://YOUR-SERVICE-URL/health
```

Should return: `{"status": "ok"}`

---

## That's It! 🎉

Your meeting transcription service is now running. Depending on your configuration:

**With Bot Joining Enabled:**
1. Bot joins your meeting automatically
2. Records and transcribes with speaker identification
3. AI generates comprehensive study guide
4. Outputs available as Markdown and PDF

**Upload-Only Mode:**
1. Upload meeting transcript files
2. AI processes and generates study guide
3. Download Markdown and PDF outputs

---

## Costs

| Component | Monthly Cost |
|-----------|-------------|
| Cloud Run | $0-5 (scales to zero) |
| Recall.ai | ~$0.02-0.05/minute recorded |
| Gemini | ~$0.001/1K tokens |

**Typical 1-hour meeting: ~$2-5 total**

---

## Rate Limiting & Scaling

### Default Setup (Recommended for Most Users)

Your deployment includes **built-in rate limiting** to protect against abuse:
- Login attempts: 5 per minute
- Meeting creation: 10 per hour
- Uploads: 10 per hour

**How it works:** Each Cloud Run instance tracks rate limits in memory.

**Cost: $0** ✅

### When Memory-Based Rate Limiting is Sufficient

The default setup works great for:
- ✅ **Single user or small team** (< 10 users)
- ✅ **Low to moderate traffic** (< 100 requests/hour)
- ✅ **Development and testing**
- ✅ **Personal use**

**Why?** Cloud Run auto-scales instances, and each instance provides rate limiting. Unless you have many concurrent users hitting the same endpoint simultaneously, the default is perfectly adequate.

### When to Upgrade to Redis

Consider adding Redis/Memorystore only if:
- ❗ **High concurrent traffic** (100+ requests/second)
- ❗ **Many simultaneous users** (50+ active users)
- ❗ **Strict rate limits** needed across all instances
- ❗ **You're seeing rate limit bypass** in logs

### Cost of Redis Upgrade

**Memorystore for Redis pricing:**
- Basic tier (1 GB): **~$49/month** 💰
- Standard tier (1 GB): **~$98/month** 💰💰

**Why we don't recommend it at first:**
- Adds 10-20x to your monthly costs
- Most deployments never need it
- Memory-based limiting is sufficient for 95% of use cases

### How to Upgrade (If Needed)

If you determine you need distributed rate limiting:

1. **Create Redis instance:**
```bash
gcloud redis instances create rate-limiter \
  --size=1 \
  --region=us-central1 \
  --tier=basic \
  --redis-version=redis_7_0
```

2. **Get Redis IP:**
```bash
gcloud redis instances describe rate-limiter \
  --region=us-central1 \
  --format="value(host)"
```

3. **Update Cloud Run service:**
```bash
gcloud run services update meeting-transcription \
  --set-env-vars RATE_LIMIT_STORAGE_URI=redis://[REDIS_IP]:6379
```

**That's it!** The application automatically detects and uses Redis. No code changes needed.

### Monitoring Rate Limiting

Check your Cloud Run logs to see if rate limiting is working:
```
⚠️  WARNING: Rate limiting using in-memory storage. Not shared across Cloud Run instances!
```

This warning is normal and expected for the default setup. It just reminds you that limits aren't shared across instances (which is fine for most use cases).

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

### "Can't log in"
- Verify you're using the correct email and password from setup output
- Check that JWT_SECRET is configured in Cloud Run secrets
- Try resetting password via the setup API endpoint
- Check Cloud Run logs for authentication errors

### "Bot won't join meeting"
- Verify bot joining feature was enabled during setup
- Check Recall.ai API key is correct in Cloud Run secrets
- Verify meeting URL format (must be valid Zoom/Meet/Teams URL)
- Check [Cloud Run logs](https://console.cloud.google.com/run) → your service → Logs

### "Webhook not working"
- Verify webhook URL in Recall.ai dashboard matches your Cloud Run URL
- Make sure you copied the full URL including `https://`
- Check that `/webhook/recall` is at the end
- Verify all required events are enabled in Recall.ai webhook settings

### "No summary generated" or "Transcript stuck in processing"
- **Using Vertex AI (default):** Verify Vertex AI API is enabled in your GCP project
- **Using Azure OpenAI:** Check Azure API key, endpoint, and deployment name are correct
- Verify you have quota/credits with your LLM provider
- Check Cloud Run logs for LLM API errors
- For uploaded transcripts: Verify Cloud Tasks is configured and compute service account has `roles/run.invoker`

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
