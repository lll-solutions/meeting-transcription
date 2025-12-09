# Meeting Transcription & Summarization Pipeline

Transform your video meetings into comprehensive, AI-powered study guides and summaries. Perfect for educational classes, workshops, training sessions, and any meeting worth remembering.

[![License: ELv2](https://img.shields.io/badge/License-ELv2-blue.svg)](LICENSE)

## 🎯 What This Does

1. **Join any meeting** (Zoom, Google Meet, Microsoft Teams)
2. **Record and transcribe** with speaker identification
3. **Generate AI-powered summaries** with key concepts, action items, and study guides
4. **Export to Markdown and PDF** for easy sharing

```
Meeting URL → Bot Joins → Records → Transcribes → AI Summarizes → PDF Study Guide
```

## ✨ Features

- 🤖 **Automated Bot** - Joins meetings on schedule or on-demand
- 🎙️ **Speaker Diarization** - Knows who said what
- 🧠 **AI Summarization** - Extracts key concepts, Q&A, action items
- 📚 **Study Guide Generation** - Perfect for educational content
- 📄 **PDF Export** - Professional, shareable documents
- ☁️ **One-Click GCP Deploy** - Easy self-hosting on Google Cloud

## 🚀 Quick Start (5 minutes)

### Step 1: Open in Google Cloud Shell

[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://shell.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/lll-solutions/meeting-transcription.git&cloudshell_open_in_editor=README.md&cloudshell_workspace=.)

### Step 2: Run the Setup Script

Once Cloud Shell opens, run:

```bash
./setup.sh
```

The script will guide you through everything:
- ✅ Creating a GCP project (or using existing)
- ✅ Setting up billing ($300 free credits for new users!)
- ✅ Enabling required APIs
- ✅ Deploying to Cloud Run
- ✅ Storing your API keys securely

**That's it!** At the end, you'll get a URL for your deployed service.

See [Deployment Guide](docs/DEPLOYMENT.md) for detailed instructions.

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

- [Deployment Guide](docs/DEPLOYMENT.md) - GCP setup instructions
- [Architecture Guide](docs/ARCHITECTURE.md) - System design, auth, and storage
- [Functional Requirements](docs/REQUIREMENTS.md) - What this system does
- [Setup Helper](docs/setup.html) - Interactive setup wizard

## 🏗️ Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Meeting URL   │────▶│   Recall.ai     │────▶│   Cloud Run     │
│  (Zoom/Meet/    │     │   (Bot infra)   │     │  (Your Server)  │
│   Teams)        │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                        ┌─────────────────┐     ┌─────────────────┐
                        │   LLM Provider  │◀────│  Summarization  │
                        │ (Gemini/OpenAI/ │     │    Pipeline     │
                        │  Azure/Claude)  │     │                 │
                        └─────────────────┘     └────────┬────────┘
                                                         │
                                                         ▼
                                                ┌─────────────────┐
                                                │  Study Guide    │
                                                │  (MD + PDF)     │
                                                └─────────────────┘
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

