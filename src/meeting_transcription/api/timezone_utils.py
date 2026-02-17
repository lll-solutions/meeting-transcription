"""
Timezone utilities for handling conversions and common timezones.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

# Common US timezones
COMMON_TIMEZONES = [
    "America/New_York",      # Eastern (EST/EDT)
    "America/Chicago",       # Central (CST/CDT)
    "America/Denver",        # Mountain (MST/MDT)
    "America/Phoenix",       # Arizona (no DST)
    "America/Los_Angeles",   # Pacific (PST/PDT)
    "America/Anchorage",     # Alaska (AKST/AKDT)
    "Pacific/Honolulu",      # Hawaii (HST, no DST)
]

# Full list of common timezones
ALL_TIMEZONES = [*COMMON_TIMEZONES, "UTC", "Europe/London", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo", "Asia/Shanghai", "Asia/Dubai", "Asia/Kolkata", "Australia/Sydney"]


def utc_now() -> datetime:
    """Get current time in UTC."""
    return datetime.now(ZoneInfo("UTC"))


def to_utc(dt: datetime, from_timezone: str) -> datetime:
    """
    Convert a datetime from a specific timezone to UTC.

    Args:
        dt: Datetime object (naive or aware)
        from_timezone: Source timezone name (e.g., "America/New_York")

    Returns:
        Datetime in UTC
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(from_timezone))
    return dt.astimezone(ZoneInfo("UTC"))


def from_utc(dt: datetime, to_timezone: str) -> datetime:
    """
    Convert a UTC datetime to a specific timezone.

    Args:
        dt: Datetime in UTC
        to_timezone: Target timezone name (e.g., "America/New_York")

    Returns:
        Datetime in target timezone
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(to_timezone))


def format_datetime_for_user(dt: datetime, user_timezone: str, fmt: str = "%Y-%m-%d %I:%M %p %Z") -> str:
    """
    Format a datetime for display to user in their timezone.

    Args:
        dt: Datetime (assumed UTC if naive)
        user_timezone: User's timezone
        fmt: strftime format string

    Returns:
        Formatted datetime string
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    local_dt = dt.astimezone(ZoneInfo(user_timezone))
    return local_dt.strftime(fmt)


def parse_user_datetime(dt_str: str, user_timezone: str) -> datetime | None:
    """
    Parse a datetime string from user input and convert to UTC.

    Args:
        dt_str: Datetime string (e.g., "2024-12-10T15:30")
        user_timezone: User's timezone

    Returns:
        Datetime in UTC, or None if parsing fails
    """
    try:
        # Try ISO format first
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(user_timezone))
        return dt.astimezone(ZoneInfo("UTC"))
    except ValueError:
        return None


def is_valid_timezone(tz: str) -> bool:
    """
    Check if a timezone string is valid.

    Args:
        tz: Timezone name

    Returns:
        True if valid, False otherwise
    """
    try:
        ZoneInfo(tz)
        return True
    except Exception:
        return False
