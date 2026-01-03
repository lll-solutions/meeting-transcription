"""
Background scheduler for executing scheduled meeting joins.

Runs in a background thread and checks periodically for meetings
that are ready to be joined.
"""

import os
import time
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Callable, Optional

from .scheduled_meetings import get_scheduled_meeting_storage
from .timezone_utils import utc_now


class MeetingScheduler:
    """Background scheduler for joining meetings at scheduled times."""

    def __init__(
        self,
        join_callback: Callable[[str, str, str], Optional[str]],
        check_interval: int = 60
    ):
        """
        Initialize the scheduler.

        Args:
            join_callback: Function to call when a meeting should be joined.
                           Should accept (meeting_url, bot_name, user) and return meeting_id or None
            check_interval: How often to check for pending meetings (seconds)
        """
        self.join_callback = join_callback
        self.check_interval = check_interval
        self.storage = get_scheduled_meeting_storage()
        self.running = False
        self.thread = None

    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            print("⚠️ Scheduler already running")
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f"✅ Meeting scheduler started (checking every {self.check_interval}s)")

    def stop(self):
        """Stop the scheduler."""
        if not self.running:
            return

        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("🛑 Meeting scheduler stopped")

    def _run_loop(self):
        """Main scheduler loop."""
        while self.running:
            try:
                self._check_and_execute_pending()
            except Exception as e:
                print(f"❌ Scheduler error: {e}")

            time.sleep(self.check_interval)

    def _check_and_execute_pending(self):
        """Check for and execute pending scheduled meetings."""
        now = utc_now()
        pending_meetings = self.storage.get_pending(before_time=now)

        if not pending_meetings:
            return

        print(f"📅 Found {len(pending_meetings)} scheduled meeting(s) ready to join")

        for scheduled_meeting in pending_meetings:
            try:
                print(f"🤖 Joining scheduled meeting: {scheduled_meeting.id}")
                print(f"   URL: {scheduled_meeting.meeting_url}")
                print(f"   Scheduled: {scheduled_meeting.scheduled_time}")
                print(f"   User: {scheduled_meeting.user}")

                # Call the join callback
                meeting_id = self.join_callback(
                    scheduled_meeting.meeting_url,
                    scheduled_meeting.bot_name,
                    scheduled_meeting.user
                )

                if meeting_id:
                    # Update scheduled meeting as completed
                    self.storage.update(
                        scheduled_meeting.id,
                        {
                            "status": "completed",
                            "actual_meeting_id": meeting_id
                        }
                    )
                    print(f"✅ Scheduled meeting {scheduled_meeting.id} completed (meeting_id: {meeting_id})")
                else:
                    # Mark as failed
                    self.storage.update(
                        scheduled_meeting.id,
                        {
                            "status": "failed",
                            "error": "Failed to create bot"
                        }
                    )
                    print(f"❌ Failed to join scheduled meeting {scheduled_meeting.id}")

            except Exception as e:
                print(f"❌ Error executing scheduled meeting {scheduled_meeting.id}: {e}")
                # Mark as failed
                try:
                    self.storage.update(
                        scheduled_meeting.id,
                        {
                            "status": "failed",
                            "error": str(e)
                        }
                    )
                except Exception as update_error:
                    print(f"❌ Could not update scheduled meeting status: {update_error}")


# Global scheduler instance
_scheduler = None


def get_scheduler() -> Optional[MeetingScheduler]:
    """Get the global scheduler instance."""
    global _scheduler
    return _scheduler


def init_scheduler(join_callback: Callable[[str, str, str], Optional[str]]):
    """
    Initialize and start the global scheduler.

    Args:
        join_callback: Function to call when a meeting should be joined
    """
    global _scheduler
    if _scheduler is None:
        check_interval = int(os.getenv("SCHEDULER_CHECK_INTERVAL", "60"))
        _scheduler = MeetingScheduler(join_callback, check_interval)
        _scheduler.start()
    return _scheduler


def stop_scheduler():
    """Stop the global scheduler."""
    global _scheduler
    if _scheduler:
        _scheduler.stop()
        _scheduler = None
