"""Shared test fixtures for webapp tests."""

from collections.abc import Generator
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_tools import create_app
from fastapi_tools.config.webapp_config import CORSConfig
from fastapi_tools.config.webapp_config import GoogleOAuthConfig
from fastapi_tools.config.webapp_config import RateLimitConfig
from fastapi_tools.config.webapp_config import SessionConfig
from fastapi_tools.config.webapp_config import WebappConfig
from fastapi_tools.schemas.auth import GoogleUserInfo
from fastapi_tools.schemas.auth import SessionData
import pytest

from kit_hub.webapp.routers.pages_router import router as pages_router

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_STATIC_DIR = _PROJECT_ROOT / "static"
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"


@pytest.fixture
def test_config() -> WebappConfig:
    """Create test webapp configuration."""
    return WebappConfig(
        host="127.0.0.1",
        port=8000,
        debug=True,
        app_name="Test API",
        app_version="0.1.0-test",
        cors=CORSConfig(
            allow_origins=["http://localhost:3000"],
        ),
        session=SessionConfig(
            secret_key="test_secret_key_for_testing_only_do_not_use_in_prod",  # noqa: S106 # pragma: allowlist secret
            max_age=3600,
        ),
        rate_limit=RateLimitConfig(
            requests_per_minute=100,
        ),
        google_oauth=GoogleOAuthConfig(
            client_id="test_client_id",
            client_secret="test_client_secret",  # noqa: S106 # pragma: allowlist secret
            redirect_uri="http://localhost:8000/auth/google/callback",
        ),
    )


@pytest.fixture
def app(test_config: WebappConfig) -> FastAPI:
    """Create test FastAPI application."""
    return create_app(
        config=test_config,
        extra_routers=[pages_router],
        static_dir=_STATIC_DIR,
        templates_dir=_TEMPLATES_DIR,
    )


@pytest.fixture
def client(app: FastAPI) -> Generator[TestClient]:
    """Create test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_google_user_info() -> GoogleUserInfo:
    """Create mock Google user info."""
    return GoogleUserInfo(
        sub="google_user_123",
        email="test@example.com",
        email_verified=True,
        name="Test User",
        picture="https://example.com/photo.jpg",
        given_name="Test",
        family_name="User",
    )


@pytest.fixture
def mock_session_data() -> SessionData:
    """Create mock session data."""
    now = datetime.now(UTC)
    return SessionData(
        session_id="test_session_id_123",
        user_id="google_user_123",
        email="test@example.com",
        name="Test User",
        picture="https://example.com/photo.jpg",
        created_at=now,
        expires_at=datetime(2099, 12, 31, tzinfo=UTC),  # Far future
    )


@pytest.fixture
def authenticated_client(
    app: FastAPI,
    mock_session_data: SessionData,
) -> Generator[TestClient]:
    """Create test client with authenticated session."""
    with TestClient(app) as test_client:
        # Access session store from app state and add the mock session
        session_store = app.state.session_store
        session_store.create_session(mock_session_data)

        # Set session cookie
        test_client.cookies.set(
            "session",
            mock_session_data.session_id,
        )

        yield test_client


@pytest.fixture
def mock_google_oauth() -> Generator[MagicMock]:
    """Mock Google OAuth HTTP calls."""
    with patch("fastapi_tools.auth.google.httpx.AsyncClient") as mock:
        mock_client = AsyncMock()
        mock.return_value.__aenter__.return_value = mock_client

        # Mock token exchange response
        mock_token_response = MagicMock()
        mock_token_response.json.return_value = {
            "access_token": "mock_access_token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }
        mock_token_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_token_response

        # Mock user info response
        mock_userinfo_response = MagicMock()
        mock_userinfo_response.json.return_value = {
            "sub": "google_user_123",
            "email": "test@example.com",
            "email_verified": True,
            "name": "Test User",
            "picture": "https://example.com/photo.jpg",
        }
        mock_userinfo_response.raise_for_status = MagicMock()
        mock_client.get.return_value = mock_userinfo_response

        yield mock
