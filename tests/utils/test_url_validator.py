"""
Tests for UrlValidator.

Test coverage:
- Happy path: Valid URLs from all supported platforms
- Edge cases: Invalid schemes, disallowed domains, malformed URLs
- Security: Port injection, subdomain handling
"""

import pytest

from src.utils.url_validator import UrlValidator


class TestValidateMeetingUrl:
    """Tests for validate_meeting_url method."""

    # =========================================================================
    # HAPPY PATH TESTS
    # =========================================================================

    def test_valid_zoom_url(self) -> None:
        """Valid Zoom URL should pass validation."""
        url = "https://zoom.us/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_valid_zoom_gov_url(self) -> None:
        """Valid Zoom Government URL should pass validation."""
        url = "https://zoomgov.com/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_valid_google_meet_url(self) -> None:
        """Valid Google Meet URL should pass validation."""
        url = "https://meet.google.com/abc-defg-hij"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_valid_teams_url(self) -> None:
        """Valid Microsoft Teams URL should pass validation."""
        url = "https://teams.microsoft.com/l/meetup-join/19%3ameeting"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_valid_teams_live_url(self) -> None:
        """Valid Microsoft Teams Live URL should pass validation."""
        url = "https://teams.live.com/meet/12345"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_valid_url_with_subdomain(self) -> None:
        """URL with subdomain should pass if base domain is allowed."""
        url = "https://company.zoom.us/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_valid_url_with_query_params(self) -> None:
        """URL with query parameters should pass validation."""
        url = "https://zoom.us/j/123456789?pwd=abc123"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    # =========================================================================
    # EDGE CASE TESTS
    # =========================================================================

    def test_empty_url(self) -> None:
        """Empty URL should fail validation."""
        is_valid, error = UrlValidator.validate_meeting_url("")

        assert is_valid is False
        assert "required" in error.lower()

    def test_none_url(self) -> None:
        """None URL should fail validation."""
        is_valid, error = UrlValidator.validate_meeting_url(None)  # type: ignore

        assert is_valid is False
        assert "required" in error.lower()

    def test_invalid_scheme_ftp(self) -> None:
        """FTP scheme should fail validation."""
        url = "ftp://zoom.us/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is False
        assert "http or https" in error.lower()

    def test_invalid_scheme_javascript(self) -> None:
        """JavaScript scheme should fail validation (XSS prevention)."""
        url = "javascript:alert(1)"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is False
        assert "http or https" in error.lower()

    def test_disallowed_domain_webex(self) -> None:
        """Webex URL should fail validation (not in allowed list)."""
        url = "https://webex.com/meet/room123"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is False
        assert "not supported" in error.lower()
        assert "zoom.us" in error

    def test_disallowed_domain_generic(self) -> None:
        """URL from disallowed domain should fail validation."""
        url = "https://evil.com/fake-meeting"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is False
        assert "not supported" in error.lower()

    def test_url_with_port(self) -> None:
        """URL with port should still validate correctly."""
        url = "https://zoom.us:443/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_malformed_url(self) -> None:
        """Malformed URL should fail validation gracefully."""
        url = "not-a-url"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is False
        # Malformed URLs fail on scheme validation
        assert "http or https" in error.lower() or "invalid" in error.lower()

    # =========================================================================
    # SECURITY TESTS
    # =========================================================================

    def test_subdomain_spoofing(self) -> None:
        """Subdomain spoofing attempt should fail."""
        # "zoom.us.evil.com" is NOT a subdomain of "zoom.us"
        url = "https://zoom.us.evil.com/fake"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is False
        assert "not supported" in error.lower()

    def test_case_insensitive_domain(self) -> None:
        """Domain validation should be case-insensitive."""
        url = "https://ZOOM.US/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""

    def test_http_scheme_allowed(self) -> None:
        """HTTP (not just HTTPS) should be allowed."""
        url = "http://zoom.us/j/123456789"
        is_valid, error = UrlValidator.validate_meeting_url(url)

        assert is_valid is True
        assert error == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
