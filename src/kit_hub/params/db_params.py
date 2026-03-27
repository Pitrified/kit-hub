"""Database parameters - loads actual DB connection values.

Follows the Config / Params pattern: this class loads real values and
constructs a ``DbConfig`` via ``to_config()``.  No Pydantic models here.

The DB URL differs by stage:
- DEV: ``kit_hub_dev.db`` to avoid polluting the production database.
- PROD: ``kit_hub.db``.

Both resolve to files inside ``data/`` in the project root.  The path is
computed from ``KitHubPaths`` so it stays correct in all environments.

See Also:
    ``DbConfig`` - the paired config model in ``src/kit_hub/config/``.
    ``docs/guides/params_config.md`` - full guide with rationale.
"""

from pathlib import Path

from kit_hub.config.db_config import DbConfig
from kit_hub.params.env_type import EnvLocationType
from kit_hub.params.env_type import EnvStageType
from kit_hub.params.env_type import EnvType
from kit_hub.params.env_type import UnknownEnvLocationError
from kit_hub.params.env_type import UnknownEnvStageError


class DbParams:
    """Database parameters for the given deployment environment.

    Loads the appropriate SQLite file path based on env stage and
    constructs a ``DbConfig`` via ``to_config()``.

    Args:
        env_type: Deployment environment (stage + location).  If ``None``,
            inferred from ``ENV_STAGE_TYPE`` and ``ENV_LOCATION_TYPE``
            environment variables (defaults: ``dev`` / ``local``).
        data_fol: Root data folder for the SQLite files.  If ``None``,
            the caller is responsible for setting ``self.data_fol`` before
            calling ``_load_params()``.  In normal use, ``KitHubParams``
            passes the precomputed path from ``KitHubPaths``.
    """

    def __init__(
        self,
        env_type: EnvType | None = None,
        data_fol: Path | None = None,
    ) -> None:
        """Load DB params for the given environment.

        Args:
            env_type: Deployment environment (stage + location).
                If ``None``, inferred from environment variables.
            data_fol: Root data folder.  Used to construct the SQLite URL.
                Falls back to ``Path("data")`` (relative) when ``None``.
        """
        self.env_type: EnvType = env_type or EnvType.from_env_var()
        self.data_fol: Path = data_fol or Path("data")
        self._load_params()

    def _load_params(self) -> None:
        """Orchestrate loading: common first, then stage + location."""
        self._load_common_params()
        match self.env_type.stage:
            case EnvStageType.DEV:
                self._load_dev_params()
            case EnvStageType.PROD:
                self._load_prod_params()
            case _:
                raise UnknownEnvStageError(self.env_type.stage)

    def _load_common_params(self) -> None:
        """Set attributes shared across all environments."""
        self.echo: bool = False

    def _load_dev_params(self) -> None:
        """Set DEV-stage attributes, then dispatch on location."""
        self.db_filename: str = "kit_hub_dev.db"
        match self.env_type.location:
            case EnvLocationType.LOCAL:
                self._load_dev_local_params()
            case EnvLocationType.RENDER:
                self._load_dev_render_params()
            case _:
                raise UnknownEnvLocationError(self.env_type.location)

    def _load_dev_local_params(self) -> None:
        """Set DEV + LOCAL overrides."""

    def _load_dev_render_params(self) -> None:
        """Set DEV + RENDER overrides."""

    def _load_prod_params(self) -> None:
        """Set PROD-stage attributes, then dispatch on location."""
        self.db_filename = "kit_hub.db"
        match self.env_type.location:
            case EnvLocationType.LOCAL:
                self._load_prod_local_params()
            case EnvLocationType.RENDER:
                self._load_prod_render_params()
            case _:
                raise UnknownEnvLocationError(self.env_type.location)

    def _load_prod_local_params(self) -> None:
        """Set PROD + LOCAL overrides."""

    def _load_prod_render_params(self) -> None:
        """Set PROD + RENDER overrides."""

    def to_config(self) -> DbConfig:
        """Assemble and return the typed DB config model.

        Returns:
            DbConfig: A Pydantic model carrying the database connection settings.
        """
        db_path = self.data_fol / self.db_filename
        db_url = f"sqlite+aiosqlite:///{db_path}"
        return DbConfig(db_url=db_url, echo=self.echo)

    def __str__(self) -> str:
        """Return a human-readable summary (no secrets to redact here)."""
        config = self.to_config()
        return f"DbParams: db_url={config.db_url!r} echo={config.echo}"
