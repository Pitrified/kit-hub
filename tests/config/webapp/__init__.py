"""Tests for webapp configuration models."""

from fastapi_tools.config.webapp_config import CORSConfig
from fastapi_tools.config.webapp_config import GoogleOAuthConfig
from fastapi_tools.config.webapp_config import RateLimitConfig
from fastapi_tools.config.webapp_config import SessionConfig
from fastapi_tools.config.webapp_config import WebappConfig
from pydantic import ValidationError
import pytest


def test_cors_config_defaults() -> None:
    """Test CORSConfig default values."""
    config = CORSConfig()
    assert "http://localhost:3000" in config.allow_origins
    assert "GET" in config.allow_methods
    assert config.allow_credentials is True


def test_session_config_requires_secret_key() -> None:
    """Test SessionConfig requires secret_key."""
    with pytest.raises(ValidationError):
        SessionConfig()  # type: ignore[call-arg]


def test_session_config_with_secret_key() -> None:
    """Test SessionConfig with valid secret_key."""
    config = SessionConfig(secret_key="test_secret_key_123")  # noqa: S106 # pragma: allowlist secret
    assert config.secret_key == "test_secret_key_123"  # noqa: S105 # pragma: allowlist secret
    assert config.max_age == 86400  # Default 24 hours
    assert config.same_site == "lax"


def test_session_config_same_site_values() -> None:
    """Test SessionConfig same_site accepts valid values."""
    for same_site in ["lax", "strict", "none"]:
        config = SessionConfig(secret_key="test", same_site=same_site)  # type: ignore[arg-type]  # noqa: S106
        assert config.same_site == same_site


def test_rate_limit_config_defaults() -> None:
    """Test RateLimitConfig default values."""
    config = RateLimitConfig()
    assert config.requests_per_minute == 100
    assert config.burst_size == 10
    assert config.auth_requests_per_minute == 10


def test_google_oauth_config_requires_client_id() -> None:
    """Test GoogleOAuthConfig requires client_id."""
    with pytest.raises(ValidationError):
        GoogleOAuthConfig()  # type: ignore[call-arg]


def test_google_oauth_config_with_client_id() -> None:
    """Test GoogleOAuthConfig with valid client_id."""
    config = GoogleOAuthConfig(client_id="test_client_id")
    assert config.client_id == "test_client_id"
    assert "openid" in config.scopes
    assert "email" in config.scopes


def test_webapp_config_nested() -> None:
    """Test WebappConfig with nested configs."""
    config = WebappConfig(
        host="0.0.0.0",  # noqa: S104
        port=8080,
        session=SessionConfig(secret_key="test_secret"),  # noqa: S106
        google_oauth=GoogleOAuthConfig(client_id="test_client"),
    )
    assert config.host == "0.0.0.0"  # noqa: S104
    assert config.port == 8080
    assert config.session.secret_key == "test_secret"  # noqa: S105 # pragma: allowlist secret
    assert config.google_oauth.client_id == "test_client"
    assert config.cors.allow_credentials is True  # Default


def test_webapp_config_to_kw() -> None:
    """Test WebappConfig to_kw method."""
    config = WebappConfig(
        session=SessionConfig(secret_key="test"),  # noqa: S106
        google_oauth=GoogleOAuthConfig(client_id="test"),
    )
    kw = config.to_kw()
    assert "host" in kw
    assert "port" in kw
    assert "session" in kw
