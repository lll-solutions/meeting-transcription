"""
Recall.ai API wrapper module
Handles bot creation, management, and transcript retrieval.
"""

import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Configuration
RECALL_API_KEY = os.getenv("RECALL_API_KEY")
BASE_URL = os.getenv("RECALL_API_BASE_URL", "https://us-west-2.recall.ai/api/v1")


def create_bot(meeting_url: str, webhook_url: str, bot_name: str = "Meeting Assistant Bot") -> dict | None:
    """
    Create a bot to join a meeting and record/transcribe.
    
    Args:
        meeting_url: The Zoom/Teams/Meet meeting URL
        webhook_url: The webhook endpoint to receive events
        bot_name: Display name for the bot in the meeting
    
    Returns:
        dict: Bot data including bot ID, or None if creation failed
    """
    if not RECALL_API_KEY:
        print("❌ RECALL_API_KEY not configured")
        return None
        
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "meeting_url": meeting_url,
        "bot_name": bot_name,
        "webhook_url": webhook_url,
        "automatic_leave": {
            "waiting_room_timeout": 600,    # Stay in waiting room for 10 mins
            "noone_joined_timeout": 600,    # Wait 10 mins if no one joins
            "everyone_left_timeout": 2      # Leave 2 secs after everyone leaves
        },
        "recording_config": {
            "recording_mode": "speaker_view"
        }
    }

    response = requests.post(f"{BASE_URL}/bot/", json=payload, headers=headers)

    if response.status_code == 201:
        bot_data = response.json()
        print(f"✅ Bot created successfully! ID: {bot_data['id']}")
        return bot_data
    else:
        print(f"❌ Error creating bot: {response.status_code}")
        print(response.text)
        return None


def create_async_transcript(recording_id: str) -> dict | None:
    """
    Generate a high-quality async transcript using AssemblyAI.
    
    Args:
        recording_id: The recording's UUID
    
    Returns:
        dict: Transcript data including transcript ID, or None if creation failed
    """
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "provider": {
            "assembly_ai_async": {
                "language_code": "en_us",
                "punctuate": True,
                "format_text": True,
                "speaker_labels": True,
                "disfluencies": False,
                "sentiment_analysis": True,
                "auto_chapters": True,
                "entity_detection": True
            }
        }
    }

    response = requests.post(
        f"{BASE_URL}/recording/{recording_id}/create_transcript/",
        json=payload,
        headers=headers
    )

    if response.status_code == 200:
        transcript_data = response.json()
        print(f"✅ Async transcript requested! ID: {transcript_data['id']}")
        return transcript_data
    else:
        print(f"❌ Error creating async transcript: {response.status_code}")
        print(response.text)
        return None


def get_transcript(transcript_id: str) -> dict | None:
    """
    Retrieve the completed async transcript.
    
    Args:
        transcript_id: The transcript's UUID
    
    Returns:
        dict: Transcript data, or None if retrieval failed
    """
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Accept": "application/json"
    }

    response = requests.get(
        f"{BASE_URL}/transcript/{transcript_id}/",
        headers=headers
    )

    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error getting transcript: {response.status_code}")
        return None


def download_transcript(transcript_id: str, output_file: str = "transcript.json") -> str | None:
    """
    Download the transcript JSON file.
    
    Args:
        transcript_id: The transcript's UUID
        output_file: Path where transcript should be saved
    
    Returns:
        str: Path to downloaded file, or None if failed
    """
    transcript = get_transcript(transcript_id)

    if transcript and transcript.get('data', {}).get('download_url'):
        download_url = transcript['data']['download_url']
        response = requests.get(download_url)

        if response.status_code == 200:
            with open(output_file, 'w') as f:
                f.write(response.text)
            print(f"✅ Transcript downloaded to {output_file}")
            return output_file

    print("❌ Could not download transcript")
    return None


def get_bot_status(bot_id: str) -> dict | None:
    """
    Check the current status of a bot.
    
    Args:
        bot_id: The bot's UUID
    
    Returns:
        dict: Bot status data, or None if retrieval failed
    """
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Accept": "application/json"
    }

    response = requests.get(f"{BASE_URL}/bot/{bot_id}/", headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error getting bot status: {response.status_code}")
        return None


def list_bots() -> list | None:
    """
    List all bots.
    
    Returns:
        list: List of bot data, or None if retrieval failed
    """
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Accept": "application/json"
    }

    response = requests.get(f"{BASE_URL}/bot/", headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"❌ Error listing bots: {response.status_code}")
        return None


def leave_meeting(bot_id: str) -> bool:
    """
    Make a bot leave the meeting it's currently in.
    
    Args:
        bot_id: The bot's UUID
    
    Returns:
        bool: True if leave command succeeded, False otherwise
    """
    headers = {
        "Authorization": f"Token {RECALL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    response = requests.post(
        f"{BASE_URL}/bot/{bot_id}/leave_call/",
        headers=headers
    )

    if response.status_code == 200:
        print(f"✅ Bot {bot_id} is leaving the meeting")
        return True
    else:
        print(f"❌ Error making bot leave: {response.status_code}")
        return False

