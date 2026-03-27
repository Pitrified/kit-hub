"""Tests for DbConfig and DbParams."""

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from kit_hub.config.db_config import DbConfig
from kit_hub.params.db_params import DbParams
from kit_hub.params.env_type import EnvLocationType
from kit_hub.params.env_type import EnvStageType
from kit_hub.params.env_type import EnvType
from kit_hub.params.env_type import UnknownEnvStageError

_DEV_LOCAL = EnvType(stage=EnvStageType.DEV, location=EnvLocationType.LOCAL)
_DEV_RENDER = EnvType(stage=EnvStageType.DEV, location=EnvLocationType.RENDER)
_PROD_LOCAL = EnvType(stage=EnvStageType.PROD, location=EnvLocationType.LOCAL)
_PROD_RENDER = EnvType(stage=EnvStageType.PROD, location=EnvLocationType.RENDER)


@pytest.fixture
def tmp_data_fol() -> Path:
    """Return a temporary directory path for test data."""
    with TemporaryDirectory() as tmp:
        return Path(tmp)


class TestDbConfig:
    """Tests for DbConfig."""

    def test_init(self) -> None:
        """Basic construction sets db_url and echo."""
        config = DbConfig(db_url="sqlite+aiosqlite:///data/test.db")
        assert config.db_url == "sqlite+aiosqlite:///data/test.db"
        assert config.echo is False

    def test_echo_true(self) -> None:
        """Echo can be set to True."""
        config = DbConfig(db_url="sqlite+aiosqlite:///data/test.db", echo=True)
        assert config.echo is True

    def test_to_kw(self) -> None:
        """To_kw returns a flat dict."""
        config = DbConfig(db_url="sqlite+aiosqlite:///data/test.db")
        kw = config.to_kw()
        assert kw["db_url"] == "sqlite+aiosqlite:///data/test.db"
        assert kw["echo"] is False


class TestDbParams:
    """Tests for DbParams."""

    def test_dev_local_filename(self, tmp_data_fol: Path) -> None:
        """DEV stage uses kit_hub_dev.db."""
        params = DbParams(env_type=_DEV_LOCAL, data_fol=tmp_data_fol)
        assert params.db_filename == "kit_hub_dev.db"

    def test_dev_render_filename(self, tmp_data_fol: Path) -> None:
        """DEV stage on Render also uses kit_hub_dev.db."""
        params = DbParams(env_type=_DEV_RENDER, data_fol=tmp_data_fol)
        assert params.db_filename == "kit_hub_dev.db"

    def test_prod_local_filename(self, tmp_data_fol: Path) -> None:
        """PROD stage uses kit_hub.db."""
        params = DbParams(env_type=_PROD_LOCAL, data_fol=tmp_data_fol)
        assert params.db_filename == "kit_hub.db"

    def test_prod_render_filename(self, tmp_data_fol: Path) -> None:
        """PROD stage on Render uses kit_hub.db."""
        params = DbParams(env_type=_PROD_RENDER, data_fol=tmp_data_fol)
        assert params.db_filename == "kit_hub.db"

    def test_to_config_dev_url(self, tmp_data_fol: Path) -> None:
        """To_config produces a correct sqlite+aiosqlite URL for DEV."""
        params = DbParams(env_type=_DEV_LOCAL, data_fol=tmp_data_fol)
        config = params.to_config()
        assert isinstance(config, DbConfig)
        assert "sqlite+aiosqlite:///" in config.db_url
        assert "kit_hub_dev.db" in config.db_url

    def test_to_config_prod_url(self, tmp_data_fol: Path) -> None:
        """To_config produces a correct sqlite+aiosqlite URL for PROD."""
        params = DbParams(env_type=_PROD_LOCAL, data_fol=tmp_data_fol)
        config = params.to_config()
        assert "kit_hub.db" in config.db_url
        assert "kit_hub_dev.db" not in config.db_url

    def test_echo_default_false(self, tmp_data_fol: Path) -> None:
        """Echo is False by default."""
        params = DbParams(env_type=_DEV_LOCAL, data_fol=tmp_data_fol)
        config = params.to_config()
        assert config.echo is False

    def test_str_contains_url(self, tmp_data_fol: Path) -> None:
        """Str representation contains the database URL."""
        params = DbParams(env_type=_DEV_LOCAL, data_fol=tmp_data_fol)
        result = str(params)
        assert "sqlite+aiosqlite" in result

    def test_invalid_stage_raises(self, tmp_data_fol: Path) -> None:
        """An invalid stage raises UnknownEnvStageError."""
        params = DbParams.__new__(DbParams)
        params.env_type = EnvType(stage="bad_stage", location=EnvLocationType.LOCAL)  # type: ignore[arg-type]
        params.data_fol = tmp_data_fol
        with pytest.raises(UnknownEnvStageError):
            params._load_params()  # noqa: SLF001
