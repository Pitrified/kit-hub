"""Tests for WebappParams."""

from collections.abc import Generator
import os

import pytest

from kit_hub.params.env_type import EnvLocationType
from kit_hub.params.env_type import EnvStageType
from kit_hub.params.webapp import WebappParams


@pytest.fixture
def clean_env() -> Generator[None]:
    """Remove webapp-related environment variables."""
    webapp_vars = [
        "WEBAPP_HOST",
        "WEBAPP_PORT",
        "WEBAPP_DEBUG",
        "SESSION_SECRET_KEY",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "CORS_ALLOWED_ORIGINS",
    ]
    original = {k: os.environ.get(k) for k in webapp_vars}

    for var in webapp_vars:
        if var in os.environ:
            del os.environ[var]

    yield

    # Restore original values
    for var, value in original.items():
        if value is not None:
            os.environ[var] = value


def test_webapp_params_dev_defaults(clean_env: None) -> None:
    """Test WebappParams uses defaults in dev mode."""
    params = WebappParams(
        stage=EnvStageType.DEV,
        location=EnvLocationType.LOCAL,
    )

    assert params.host == "0.0.0.0"  # noqa: S104
    assert params.port == 8000
    assert params.debug is False  # Default from env
    assert params.session_secret_key  # Should auto-generate in dev


def test_webapp_params_from_env(clean_env: None) -> None:
    """Test WebappParams loads from environment variables."""
    os.environ["WEBAPP_HOST"] = "127.0.0.1"
    os.environ["WEBAPP_PORT"] = "9000"
    os.environ["WEBAPP_DEBUG"] = "true"
    os.environ["SESSION_SECRET_KEY"] = "test_secret_key"  # noqa: S105 # pragma: allowlist secret
    os.environ["GOOGLE_CLIENT_ID"] = "test_client_id"

    params = WebappParams(
        stage=EnvStageType.DEV,
        location=EnvLocationType.LOCAL,
    )

    assert params.host == "127.0.0.1"
    assert params.port == 9000
    assert params.debug is True
    assert params.session_secret_key == "test_secret_key"  # noqa: S105 # pragma: allowlist secret
    assert params.google_client_id == "test_client_id"


def test_webapp_params_cors_from_env(clean_env: None) -> None:
    """Test CORS origins parsed from comma-separated string."""
    os.environ["CORS_ALLOWED_ORIGINS"] = "http://localhost:3000,https://example.com"

    params = WebappParams(
        stage=EnvStageType.DEV,
        location=EnvLocationType.LOCAL,
    )

    assert "http://localhost:3000" in params.cors_allowed_origins
    assert "https://example.com" in params.cors_allowed_origins


def test_webapp_params_prod_requires_secrets(clean_env: None) -> None:
    """Test WebappParams raises error in prod without required secrets."""
    with pytest.raises(ValueError, match="SESSION_SECRET_KEY"):
        WebappParams(
            stage=EnvStageType.PROD,
            location=EnvLocationType.RENDER,
        )


def test_webapp_params_prod_with_secrets(clean_env: None) -> None:
    """Test WebappParams works in prod with required secrets."""
    os.environ["SESSION_SECRET_KEY"] = "production_secret_key"  # noqa: S105 # pragma: allowlist secret
    os.environ["GOOGLE_CLIENT_ID"] = "production_client_id"

    params = WebappParams(
        stage=EnvStageType.PROD,
        location=EnvLocationType.RENDER,
    )

    assert params.debug is False  # Forced in prod
    assert params.session_https_only is True  # Forced in prod


def test_webapp_params_to_config(clean_env: None) -> None:
    """Test WebappParams.to_config() creates valid WebappConfig."""
    os.environ["SESSION_SECRET_KEY"] = "test_secret"  # noqa: S105 # pragma: allowlist secret
    os.environ["GOOGLE_CLIENT_ID"] = "test_client"

    params = WebappParams(
        stage=EnvStageType.DEV,
        location=EnvLocationType.LOCAL,
    )

    config = params.to_config()

    assert config.host == params.host
    assert config.port == params.port
    assert config.session.secret_key == params.session_secret_key
    assert config.google_oauth.client_id == params.google_client_id


def test_webapp_params_render_port_override(clean_env: None) -> None:
    """Test Render PORT environment variable overrides WEBAPP_PORT."""
    os.environ["WEBAPP_PORT"] = "8000"
    os.environ["PORT"] = "10000"  # Render sets this
    os.environ["SESSION_SECRET_KEY"] = "test_secret"  # noqa: S105 # pragma: allowlist secret
    os.environ["GOOGLE_CLIENT_ID"] = "test_client"

    params = WebappParams(
        stage=EnvStageType.PROD,
        location=EnvLocationType.RENDER,
    )

    assert params.port == 10000


def test_webapp_params_str(clean_env: None) -> None:
    """Test WebappParams string representation."""
    params = WebappParams(
        stage=EnvStageType.DEV,
        location=EnvLocationType.LOCAL,
    )

    s = str(params)
    assert "WebappParams" in s
    assert "dev" in s
    assert "local" in s
