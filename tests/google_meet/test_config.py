"""Tests for Google OAuth configuration."""

import os
from unittest.mock import patch

from meeting_transcription.google_meet.config import (
    GOOGLE_MEET_SCOPES,
    GoogleOAuthConfig,
    GoogleOAuthMode,
)


class TestGoogleOAuthConfig:
    """Tests for GoogleOAuthConfig."""

    def test_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            config = GoogleOAuthConfig()
            assert config.client_id == ""
            assert config.client_secret == ""
            assert config.mode == GoogleOAuthMode.SHARED
            assert not config.is_configured

    def test_configured_from_env(self):
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "test-client-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "test-secret",
            "GOOGLE_OAUTH_MODE": "byoc",
            "SERVICE_URL": "https://example.com",
        }
        with patch.dict(os.environ, env, clear=True):
            config = GoogleOAuthConfig()
            assert config.client_id == "test-client-id"
            assert config.client_secret == "test-secret"
            assert config.mode == GoogleOAuthMode.BYOC
            assert config.is_configured
            assert config.redirect_uri == "https://example.com/oauth/google/callback"

    def test_validate_missing_fields(self):
        with patch.dict(os.environ, {}, clear=True):
            config = GoogleOAuthConfig()
            errors = config.validate()
            assert len(errors) >= 3
            assert any("CLIENT_ID" in e for e in errors)
            assert any("CLIENT_SECRET" in e for e in errors)

    def test_validate_all_configured(self):
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret",
            "SERVICE_URL": "https://example.com",
            "GOOGLE_CLOUD_PROJECT": "my-project",
        }
        with patch.dict(os.environ, env, clear=True):
            config = GoogleOAuthConfig()
            errors = config.validate()
            assert errors == []

    def test_pubsub_paths(self):
        env = {
            "GOOGLE_CLOUD_PROJECT": "my-project",
            "GOOGLE_PUBSUB_TOPIC": "my-topic",
            "GOOGLE_PUBSUB_SUBSCRIPTION": "my-sub",
        }
        with patch.dict(os.environ, env, clear=True):
            config = GoogleOAuthConfig()
            assert config.pubsub_topic_path == "projects/my-project/topics/my-topic"
            assert config.pubsub_subscription_path == "projects/my-project/subscriptions/my-sub"

    def test_scopes_include_meet(self):
        with patch.dict(os.environ, {}, clear=True):
            config = GoogleOAuthConfig()
            assert "https://www.googleapis.com/auth/meetings.space.readonly" in config.scopes
            assert "https://www.googleapis.com/auth/meetings.space.created" in config.scopes

    def test_to_dict_no_secrets(self):
        env = {
            "GOOGLE_OAUTH_CLIENT_ID": "secret-id",
            "GOOGLE_OAUTH_CLIENT_SECRET": "secret-value",
        }
        with patch.dict(os.environ, env, clear=True):
            config = GoogleOAuthConfig()
            d = config.to_dict()
            assert "secret-value" not in str(d)
            assert "secret-id" not in str(d)
            assert "mode" in d
            assert "configured" in d

    def test_invalid_mode_defaults_to_shared(self):
        env = {"GOOGLE_OAUTH_MODE": "invalid"}
        with patch.dict(os.environ, env, clear=True):
            config = GoogleOAuthConfig()
            assert config.mode == GoogleOAuthMode.SHARED


class TestGoogleMeetScopes:
    """Tests for scope constants."""

    def test_scopes_not_empty(self):
        assert len(GOOGLE_MEET_SCOPES) > 0

    def test_includes_openid(self):
        assert "openid" in GOOGLE_MEET_SCOPES
