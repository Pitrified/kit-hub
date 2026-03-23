"""Webapp parameters with environment-aware loading.

Parameters are actual values loaded from environment variables.
Supports ENV_STAGE_TYPE (dev/prod) and ENV_LOCATION_TYPE (local/render).
"""

import os
import secrets

from fastapi_tools.config.webapp_config import CORSConfig
from fastapi_tools.config.webapp_config import GoogleOAuthConfig
from fastapi_tools.config.webapp_config import RateLimitConfig
from fastapi_tools.config.webapp_config import SessionConfig
from fastapi_tools.config.webapp_config import WebappConfig
from loguru import logger as lg

from kit_hub.params.env_type import EnvLocationType
from kit_hub.params.env_type import EnvStageType


class WebappParams:
    """Webapp parameters loaded from environment variables."""

    def __init__(
        self,
        stage: EnvStageType | None = None,
        location: EnvLocationType | None = None,
    ) -> None:
        """Load webapp params from environment.

        Args:
            stage: Environment stage (dev/prod). Loaded from env if None.
            location: Environment location (local/render). Loaded from env if None.
        """
        lg.info("Loading WebappParams")

        self.stage = stage or EnvStageType.from_env_var()
        self.location = location or EnvLocationType.from_env_var()

        self._load_params()

    def _load_params(self) -> None:
        """Load all parameters from environment."""
        # Server settings
        self.host: str = os.getenv("WEBAPP_HOST", "0.0.0.0")  # noqa: S104
        self.port: int = int(os.getenv("WEBAPP_PORT", "8000"))
        self.debug: bool = os.getenv("WEBAPP_DEBUG", "false").lower() == "true"
        self.app_name: str = os.getenv("WEBAPP_APP_NAME", "Kit Hub API")
        self.app_version: str = os.getenv("WEBAPP_APP_VERSION", "0.1.0")

        # Session settings - avoid eager evaluation of _generate_dev_secret()
        self.session_secret_key: str = os.getenv("SESSION_SECRET_KEY", "")
        if not self.session_secret_key and self.stage == EnvStageType.DEV:
            self.session_secret_key = self._generate_dev_secret()

        self.session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "session")
        self.session_max_age: int = int(os.getenv("SESSION_MAX_AGE", "86400"))
        self.session_same_site: str = os.getenv("SESSION_SAME_SITE", "lax")

        # CORS settings
        cors_origins_str = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
        self.cors_allowed_origins: list[str] = [
            origin.strip() for origin in cors_origins_str.split(",")
        ]

        # Rate limit settings
        self.rate_limit_requests_per_minute: int = int(
            os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "100")
        )
        self.rate_limit_burst_size: int = int(os.getenv("RATE_LIMIT_BURST_SIZE", "10"))
        self.rate_limit_auth_requests_per_minute: int = int(
            os.getenv("RATE_LIMIT_AUTH_REQUESTS_PER_MINUTE", "10")
        )

        # Public base URL for building absolute links (not used for OAuth)
        self.public_base_url: str | None = os.getenv("PUBLIC_BASE_URL") or None

        # Google OAuth settings
        self.google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
        self.google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
        # Avoid eager evaluation of _get_default_redirect_uri()
        self.google_redirect_uri: str = (
            os.getenv("GOOGLE_REDIRECT_URI") or self._get_default_redirect_uri()
        )

        # Apply environment-specific overrides
        self._apply_overrides()

    def _generate_dev_secret(self) -> str:
        """Generate a development-only secret key with warning."""
        lg.warning(
            "SESSION_SECRET_KEY not set, generating random key. "
            "This is only acceptable in development!"
        )
        return secrets.token_hex(32)

    def _get_default_redirect_uri(self) -> str:
        """Get default redirect URI based on location."""
        if self.location == EnvLocationType.RENDER:
            # Will be overridden by GOOGLE_REDIRECT_URI env var in production
            return "https://your-app.onrender.com/auth/google/callback"
        return f"http://localhost:{self.port}/auth/google/callback"

    def _apply_overrides(self) -> None:
        """Apply environment-specific configuration overrides."""
        is_prod = self.stage == EnvStageType.PROD
        is_render = self.location == EnvLocationType.RENDER

        # Production overrides
        if is_prod:
            self.debug = False
            self.session_https_only = True
            if not self.session_secret_key:
                msg = "SESSION_SECRET_KEY is required in production"
                raise ValueError(msg)
            if not self.google_client_id:
                msg = "GOOGLE_CLIENT_ID is required in production"
                raise ValueError(msg)
        else:
            self.session_https_only = False

        # Render-specific overrides
        if is_render:
            # Render provides PORT env var
            render_port = os.getenv("PORT")
            if render_port:
                self.port = int(render_port)

    def to_config(self) -> WebappConfig:
        """Convert params to WebappConfig."""
        return WebappConfig(
            host=self.host,
            port=self.port,
            debug=self.debug,
            app_name=self.app_name,
            app_version=self.app_version,
            public_base_url=self.public_base_url,
            cors=CORSConfig(
                allow_origins=self.cors_allowed_origins,
            ),
            session=SessionConfig(
                secret_key=self.session_secret_key,
                session_cookie_name=self.session_cookie_name,
                max_age=self.session_max_age,
                same_site=self.session_same_site,  # type: ignore[arg-type]
                https_only=self.session_https_only,
            ),
            rate_limit=RateLimitConfig(
                requests_per_minute=self.rate_limit_requests_per_minute,
                burst_size=self.rate_limit_burst_size,
                auth_requests_per_minute=self.rate_limit_auth_requests_per_minute,
            ),
            google_oauth=GoogleOAuthConfig(
                client_id=self.google_client_id,
                client_secret=self.google_client_secret,
                redirect_uri=self.google_redirect_uri,
            ),
        )

    def __str__(self) -> str:
        """Return string representation."""
        s = "WebappParams:"
        s += f"\n  stage: {self.stage.value}"
        s += f"\n  location: {self.location.value}"
        s += f"\n  host: {self.host}"
        s += f"\n  port: {self.port}"
        s += f"\n  debug: {self.debug}"
        s += (
            f"\n  google_client_id: {'[SET]' if self.google_client_id else '[NOT SET]'}"
        )
        return s
