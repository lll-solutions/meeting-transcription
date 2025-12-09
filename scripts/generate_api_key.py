#!/usr/bin/env python3
"""
Generate API keys for the Meeting Transcription API.

Usage:
    python generate_api_key.py                     # Generate key for default user
    python generate_api_key.py user@example.com   # Generate key for specific user
    python generate_api_key.py --list             # Show format for adding to .env

The generated key should be added to your .env file:
    API_KEY=<key>                                 # Single key
    API_KEYS=<key>:user@example.com               # Multiple keys with user mapping
"""

import sys
import secrets


def generate_api_key(length: int = 32) -> str:
    """Generate a secure random API key."""
    return secrets.token_urlsafe(length)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--list':
        print("API Key Configuration Examples:")
        print("=" * 50)
        print()
        print("Single API Key (simple setup):")
        print(f"  API_KEY={generate_api_key()}")
        print()
        print("Multiple API Keys with user mapping:")
        key1 = generate_api_key()
        key2 = generate_api_key()
        print(f"  API_KEYS={key1}:admin@example.com,{key2}:user@example.com")
        print()
        print("Add these to your .env file or set as environment variables.")
        return
    
    user = sys.argv[1] if len(sys.argv) > 1 else "api-user"
    key = generate_api_key()
    
    print()
    print("🔑 Generated API Key")
    print("=" * 50)
    print(f"User:     {user}")
    print(f"API Key:  {key}")
    print()
    print("Add to your .env file:")
    print()
    if user == "api-user":
        print(f"  API_KEY={key}")
    else:
        print(f"  # For single user:")
        print(f"  API_KEY={key}")
        print()
        print(f"  # For multiple users (comma-separated):")
        print(f"  API_KEYS={key}:{user}")
    print()
    print("Usage in requests:")
    print(f"  curl -H 'X-API-Key: {key}' https://your-api.com/api/meetings")
    print()


if __name__ == "__main__":
    main()


