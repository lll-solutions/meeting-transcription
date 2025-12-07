# Contributing to Meeting Transcription

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Code of Conduct

Please be respectful and constructive in all interactions. We're building something useful together.

## How to Contribute

### Reporting Issues

1. Check if the issue already exists
2. Use the issue template
3. Include:
   - Clear description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)

### Suggesting Features

1. Open a Discussion first to gauge interest
2. Describe the use case
3. Explain why existing features don't solve it

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Add tests if applicable
5. Ensure all tests pass
6. Submit a pull request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/lll-solutions/meeting-transcription.git
cd meeting-transcription

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # dev dependencies

# Copy environment file
cp .env.example .env
# Edit .env with your API keys

# Run tests
pytest

# Run locally
python main.py
```

### Code Style

- Follow PEP 8
- Use type hints where practical
- Write docstrings for public functions
- Keep functions focused and small

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add support for Google Meet
fix: handle empty transcripts gracefully
docs: update deployment guide for Azure
refactor: simplify chunk processing logic
```

## License

By contributing, you agree that your contributions will be licensed under the [Elastic License 2.0](LICENSE).

## Questions?

Open a Discussion or contact kurt@lll-solutions.com.

