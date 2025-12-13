"""
Meeting data models.

Defines the structure of meeting/bot data throughout the application.
"""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Meeting:
    """
    Meeting bot data.

    Represents a bot that joins a meeting to record and transcribe.
    """

    id: str
    user: str
    meeting_url: str
    bot_name: str
    status: str
    created_at: str  # ISO format datetime
    instructor_name: str | None = None
    recording_id: str | None = None
    transcript_id: str | None = None
    outputs: dict[str, str] = field(default_factory=dict)
    completed_at: str | None = None
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Meeting":
        """
        Create Meeting from storage dictionary.

        Args:
            data: Dictionary from storage (Firestore or local JSON)

        Returns:
            Meeting instance
        """
        # Handle optional outputs field
        outputs = data.get("outputs", {})
        if outputs is None:
            outputs = {}

        return cls(
            id=data["id"],
            user=data["user"],
            meeting_url=data["meeting_url"],
            bot_name=data["bot_name"],
            status=data["status"],
            created_at=data["created_at"],
            instructor_name=data.get("instructor_name"),
            recording_id=data.get("recording_id"),
            transcript_id=data.get("transcript_id"),
            outputs=outputs,
            completed_at=data.get("completed_at"),
            error=data.get("error"),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Convert Meeting to dictionary for storage/JSON serialization.

        Returns:
            Dictionary representation
        """
        return asdict(self)
