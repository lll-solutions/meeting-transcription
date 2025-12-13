"""
URL validation utilities for meeting platforms.

This module provides security validation for meeting URLs:
- Domain whitelisting (SSRF prevention)
- Protocol validation
- Subdomain handling

Supported meeting platforms:
- Google Meet (meet.google.com)
- Zoom (zoom.us, zoomgov.com)
- Microsoft Teams (teams.microsoft.com, teams.live.com)
"""

from typing import ClassVar
from urllib.parse import urlparse


class UrlValidator:
    """Validator for meeting URLs with security domain whitelisting."""

    # Security: Only allow meetings from trusted platforms
    # Only Google Meet, Zoom, and Microsoft Teams are supported
    ALLOWED_DOMAINS: ClassVar[list[str]] = [
        # Zoom
        "zoom.us",
        "zoomgov.com",
        # Google Meet
        "meet.google.com",
        # Microsoft Teams
        "teams.microsoft.com",
        "teams.live.com",
    ]

    @staticmethod
    def validate_meeting_url(url: str) -> tuple[bool, str]:
        """
        Validate that a meeting URL is from an allowed domain.

        Args:
            url: The meeting URL to validate

        Returns:
            Tuple of (is_valid, error_message)
            - If valid: (True, "")
            - If invalid: (False, "reason")

        Examples:
            >>> UrlValidator.validate_meeting_url("https://zoom.us/j/123")
            (True, "")

            >>> UrlValidator.validate_meeting_url("https://webex.com/meet")
            (False, "Meeting URL domain not supported...")
        """
        if not url:
            return False, "Meeting URL is required"

        try:
            parsed = urlparse(url)

            # Only allow http/https protocols
            if parsed.scheme not in ("http", "https"):
                return False, "Meeting URL must use http or https"

            # Extract domain (remove port if present)
            domain = parsed.netloc.lower()
            if ":" in domain:
                domain = domain.split(":")[0]

            # Check against whitelist (including subdomains)
            is_allowed = any(
                domain == allowed or domain.endswith("." + allowed)
                for allowed in UrlValidator.ALLOWED_DOMAINS
            )

            if not is_allowed:
                allowed_str = ", ".join(UrlValidator.ALLOWED_DOMAINS)
                return False, f"Meeting URL domain not supported. Allowed: {allowed_str}"

            return True, ""

        except Exception as e:
            return False, f"Invalid URL format: {e!s}"
