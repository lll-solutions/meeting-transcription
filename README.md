# Meeting Transcription & Summarization Pipeline

Transform your video meetings into comprehensive, AI-powered study guides and summaries. Perfect for educational classes, workshops, training sessions, and any meeting worth remembering. Built with an **extensible plugin architecture** that enables custom post-meeting actions tailored to your domain—whether that's generating study guides, meeting summaries, or your own custom workflows.

[![License: ELv2](https://img.shields.io/badge/License-ELv2-blue.svg)](LICENSE)

## 🚀 Quick Start (15 minutes)

**Want to try it right now?** Click the button below to deploy your own instance in Google Cloud:

> 💡 **Before you start:** You'll need accounts with:
> - [Google Cloud](https://console.cloud.google.com/freetrial) with billing enabled ($300 free credits for new accounts)
> - [Recall.ai](https://recall.ai) for the meeting bot (free credits included)
> - [AssemblyAI](https://www.assemblyai.com/) for transcription (free hours included)
>
> **All services offer free trials**—you can test the entire system without paying anything!

### Step 1: Open in Google Cloud Shell

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/lll-solutions/meeting-transcription.git&cloudshell_open_in_editor=README.md&cloudshell_workspace=.)

### Step 2: Run the Setup Script

Once Cloud Shell opens, run:

```bash
./setup.sh
```

The setup wizard will guide you through everything:
- ✅ Creating a GCP project (or using existing)
- ✅ Enabling required APIs
- ✅ Deploying to Cloud Run
- ✅ Storing your API keys securely

**That's it!** In about 15 minutes, you'll have your own deployed service up and running.

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.

---

## 🎯 What This Does

1. **Join any meeting** (Zoom, Google Meet, Microsoft Teams)
2. **Record and transcribe** with speaker identification
3. **Process with AI** using extensible plugins for domain-specific outputs
4. **Generate comprehensive study guides** with key concepts, Q&A, and action items (via Educational Plugin)
5. **Execute custom post-meeting actions** tailored to your needs
6. **Export to Markdown and PDF** for easy sharing

```
Meeting URL → Bot Joins → Records → Transcribes → Plugin Processes → Custom Output
                                                    ↓
                                         (e.g., Study Guide with
                                          key concepts, Q&A, etc.)
```

## ✨ Features

- 🤖 **Automated Bot** - Joins meetings on schedule or on-demand
- 🎙️ **Speaker Diarization** - Knows who said what
- 🧠 **AI Summarization** - Extracts key concepts, Q&A, action items
- 📚 **Study Guide Generation** - Perfect for educational content
- 📄 **PDF Export** - Professional, shareable documents
- ☁️ **One-Click GCP Deploy** - Easy self-hosting on Google Cloud
- 🔌 **Plugin Architecture** - Extensible system for custom domain-specific processing

## 🔌 Plugin Architecture

The meeting-transcription system uses a **plugin architecture** to support different types of content while sharing common infrastructure (bot management, storage, authentication, deployment).

**Educational Plugin (Built-in):**
Generates comprehensive study guides from class recordings, workshops, and training sessions:
- **Key Concepts & Technical Topics** - Automatically identifies and explains main concepts
- **Q&A Exchanges** - Captures all questions and answers from the session
- **Tools & Frameworks** - Lists all technologies, tools, and frameworks discussed
- **Best Practices & Unique Insights** - Extracts actionable recommendations and key insights
- **Code Demonstrations** - Identifies and highlights code examples shown in class
- **Assignments & Action Items** - Captures homework, tasks, and follow-up actions
- **Configurable Analysis** - Time-based chunking (5-30 min segments), multi-stage processing with intelligent deduplication
- **Professional Output** - Generates both Markdown and PDF study guides

**Extensibility:**
Each plugin has full control over:
- **Chunking strategy** - How to divide the transcript (time-based, whole-session, by-topic)
- **LLM orchestration** - Processing approach (single-pass, multi-stage analysis, etc.)
- **Output format** - What gets generated (study guides, summaries, custom formats)
- **User settings** - Configurable options for your domain

**Build Your Own:**
Create custom plugins for your specific domain—legal case summaries, sales call analysis, medical consultations, or any other use case. The plugin system handles all the infrastructure while you focus on domain-specific processing logic.

See [Plugin Architecture Guide](docs/PLUGIN_ARCHITECTURE.md) for details on creating custom plugins.

## 📡 Transcript Providers

The system supports multiple transcript providers through a pluggable architecture:

| Provider | Value | Status | Description |
|----------|-------|--------|-------------|
| **Recall.ai** | `recall` | ✅ Active | Bot joins meeting to record/transcribe (default) |
| **Google Meet** | `google_meet` | 🔜 Coming | Direct API integration with Google Meet |
| **Zoom** | `zoom` | 🔜 Coming | Direct API integration with Zoom Cloud Recordings |
| **Manual Upload** | `manual` | ✅ Active | Upload transcripts directly (JSON, VTT, text) |

### Configuration

Set the `TRANSCRIPT_PROVIDER` environment variable to switch providers:

```bash
# Use Recall.ai bot (default)
TRANSCRIPT_PROVIDER=recall

# Use manual upload only
TRANSCRIPT_PROVIDER=manual
```

### Provider-specific Configuration

**Recall.ai** (default):
```bash
RECALL_API_KEY=your-api-key
RECALL_API_BASE_URL=https://us-west-2.recall.ai/api/v1  # optional
```

**Google Meet** (coming soon):
```bash
# OAuth2 credentials for Google API access
GOOGLE_CLIENT_ID=your-client-id
GOOGLE_CLIENT_SECRET=your-client-secret
```

**Zoom** (coming soon):
```bash
# Server-to-Server OAuth credentials
ZOOM_ACCOUNT_ID=your-account-id
ZOOM_CLIENT_ID=your-client-id
ZOOM_CLIENT_SECRET=your-client-secret
```

### Local Development (for developers)

```bash
# Clone the repository
git clone https://github.com/lll-solutions/meeting-transcription.git
cd meeting-transcription

# Install dependencies
pip install -r requirements.txt

# Configure your API keys
cp .env.example .env
# Edit .env with your keys

# Run the bot
python main.py
```

## 📋 Prerequisites

| Service | Purpose | Get Your Key | Free Trial |
|---------|---------|--------------|------------|
| [Google Cloud](https://cloud.google.com/free) | Hosting | [Start Free](https://cloud.google.com/free) | ✅ $300 credits |
| [Recall.ai](https://recall.ai) | Meeting Bot | [Sign up](https://recall.ai) | ✅ Free credits |
| [AssemblyAI](https://www.assemblyai.com/) | Transcription | [Sign up](https://www.assemblyai.com/) | ✅ Free hours |

> 💡 **All services offer free trials** — you can test the full pipeline without paying anything!

Google's Vertex AI (for summarization) uses your Cloud project's built-in authentication — no extra key needed.

<details>
<summary>🔧 Advanced: Use Azure OpenAI, OpenAI, or Anthropic instead</summary>

If you prefer a different LLM provider, you can configure:
- [Azure OpenAI](https://azure.microsoft.com/en-us/products/ai-services/openai-service)
- [OpenAI](https://openai.com)
- [Anthropic Claude](https://anthropic.com)

See [Configuration Guide](docs/CONFIGURATION.md) for setup instructions.
</details>

## 📖 Documentation

- [Plugin Architecture Guide](docs/PLUGIN_ARCHITECTURE.md) - How to create and use plugins
- [Deployment Guide](docs/DEPLOYMENT.md) - GCP setup instructions
- [Architecture Guide](docs/ARCHITECTURE.md) - System design, auth, and storage
- [Functional Requirements](docs/REQUIREMENTS.md) - What this system does
- [Setup Helper](docs/setup.html) - Interactive setup wizard

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────────┐
│   Meeting URL   │────▶│   Recall.ai     │────▶│   Cloud Run             │
│  (Zoom/Meet/    │     │   (Bot infra)   │     │  (Your Server)          │
│   Teams)        │     │                 │     │                         │
└─────────────────┘     └─────────────────┘     └──────────┬──────────────┘
                                                           │
                                                           ▼
                                                  ┌─────────────────┐
                                                  │ Base Pipeline   │
                                                  │ • Transcript    │
                                                  │ • Storage       │
                                                  │ • Auth          │
                                                  └────────┬────────┘
                                                           │
                                            ┌──────────────┴──────────────┐
                                            │   Plugin Architecture       │
                                            │  (Domain-Specific Process)  │
                                            └──────────────┬──────────────┘
                                                           │
                                    ┌──────────────────────┼──────────────────────┐
                                    ▼                      ▼                      ▼
                          ┌──────────────────┐   ┌──────────────────┐   ┌──────────────┐
                          │  Educational     │   │  Custom Plugin   │   │   Future     │
                          │  Plugin          │   │  (Your Domain)   │   │   Plugins    │
                          │                  │   │                  │   │              │
                          └────────┬─────────┘   └────────┬─────────┘   └──────┬───────┘
                                   │                      │                     │
                                   ▼                      ▼                     ▼
                          ┌─────────────────┐     ┌──────────────┐     ┌──────────────┐
                          │   LLM Provider  │     │  LLM Provider│     │ LLM Provider │
                          │ (Gemini/OpenAI/ │     │ (Your choice)│     │ (Your choice)│
                          │  Azure/Claude)  │     │              │     │              │
                          └────────┬────────┘     └──────┬───────┘     └──────┬───────┘
                                   │                     │                     │
                                   ▼                     ▼                     ▼
                          ┌─────────────────┐    ┌──────────────┐     ┌──────────────┐
                          │  Study Guide    │    │ Custom Output│     │    Custom    │
                          │  (MD + PDF)     │    │              │     │    Output    │
                          └─────────────────┘    └──────────────┘     └──────────────┘
```

## 💰 Cost Estimation

### Try It Free First! 🆓

| Service | Free Trial |
|---------|------------|
| Google Cloud | $300 credits (90 days) |
| Recall.ai | Free credits included |
| AssemblyAI | Free transcription hours |

**You can test the full pipeline without paying anything!**

### After Free Trials

| Component | Cost | Notes |
|-----------|------|-------|
| Recall.ai | ~$0.02-0.05/min | Bot + infrastructure |
| AssemblyAI | ~$0.01/min | Transcription |
| Vertex AI | ~$0.001/1K tokens | Summarization |
| Cloud Run | ~$0-5/month | Scales to zero |

**Typical 1-hour meeting**: ~$2-4 total

## 🗺️ Roadmap: Free & Open Source Options

We're working on reducing dependencies on paid services:

| Feature | Status | Description |
|---------|--------|-------------|
| **Free Transcription** | 🔜 Coming Soon | Use [OpenAI Whisper](https://github.com/openai/whisper) (open source, runs locally) |
| **Free Meeting Bot** | 🔜 Coming Soon | Open source bot alternative or bring-your-own recording |
| **File Upload** | 🔜 Coming Soon | Upload recordings from Google Drive, Dropbox, or local files |
| **Local LLM** | 🔜 Planned | Use [Ollama](https://ollama.ai) or other local models for summarization |

### Coming Soon: Zero-Cost Mode 🆓

Upload your own meeting recordings and process them with:
- **Whisper** for transcription (free, open source)
- **Local LLM** for summarization (free, runs on your machine)
- **No API keys required** (except for live meeting join)

Want to help build these features? See [Contributing](CONTRIBUTING.md)!

---

## 📜 License

This project is licensed under the [Elastic License 2.0 (ELv2)](LICENSE).

### What You CAN Do:
- ✅ Use for your own meetings
- ✅ Self-host for your company/organization
- ✅ Modify and customize
- ✅ Use for commercial internal purposes
- ✅ Learn from and study the code

### What You CANNOT Do:
- ❌ Offer this as a hosted/managed SaaS service
- ❌ Resell access to this software's functionality

### Want to Build a SaaS?

We're open to partnerships! If you want to offer this as a service, let's talk:

📧 **Contact**: kurt@lll-solutions.com  
🔗 **LinkedIn**: [Kurt Niemi](https://linkedin.com/in/kurtniemi)  
🌐 **Company**: [LLL Solutions](https://lll-solutions.com)

We offer:
- Commercial licensing for SaaS use
- White-label partnerships
- Custom development and integration
- Training and support

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) first.

## 🙏 Acknowledgments

Built with:
- [Recall.ai](https://recall.ai) - Meeting bot infrastructure
- [AssemblyAI](https://assemblyai.com) - Transcription (via Recall.ai)
- [Google Gemini](https://ai.google.dev) / [OpenAI](https://openai.com) / [Anthropic](https://anthropic.com) - AI summarization

## 📞 Support

- 📚 [Documentation](docs/)
- 🐛 [Issue Tracker](https://github.com/lll-solutions/meeting-transcription/issues)
- 💬 [Discussions](https://github.com/lll-solutions/meeting-transcription/discussions)

---

Made with ❤️ by [LLL Solutions](https://lll-solutions.com)

