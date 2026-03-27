"""Tests for LlmParams."""

from pathlib import Path

import pytest

from kit_hub.config.llm_config import LlmConfig
from kit_hub.params.env_type import EnvLocationType
from kit_hub.params.env_type import EnvStageType
from kit_hub.params.env_type import EnvType
from kit_hub.params.llm_params import LlmParams


@pytest.fixture
def prompts_fol(tmp_path: Path) -> Path:
    """Return a temporary directory used as prompts_fol."""
    return tmp_path / "prompts"


@pytest.fixture
def dev_env() -> EnvType:
    """DEV + LOCAL environment."""
    return EnvType(stage=EnvStageType.DEV, location=EnvLocationType.LOCAL)


@pytest.fixture
def prod_env() -> EnvType:
    """PROD + LOCAL environment."""
    return EnvType(stage=EnvStageType.PROD, location=EnvLocationType.LOCAL)


class TestLlmParams:
    """Tests for LlmParams."""

    def test_dev_model(self, dev_env: EnvType, prompts_fol: Path) -> None:
        """DEV stage uses gpt-4o-mini."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        assert params.model == "gpt-4o-mini"

    def test_prod_model(self, prod_env: EnvType, prompts_fol: Path) -> None:
        """PROD stage uses gpt-4o-mini."""
        params = LlmParams(env_type=prod_env, prompts_fol=prompts_fol)
        assert params.model == "gpt-4o-mini"

    def test_temperature(self, dev_env: EnvType, prompts_fol: Path) -> None:
        """Temperature defaults to 0.2."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        assert params.temperature == 0.2

    def test_prompts_fol_stored(self, dev_env: EnvType, prompts_fol: Path) -> None:
        """prompts_fol is stored on the instance."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        assert params.prompts_fol == prompts_fol

    def test_to_config_returns_llm_config(
        self, dev_env: EnvType, prompts_fol: Path
    ) -> None:
        """to_config returns an LlmConfig instance."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        config = params.to_config()
        assert isinstance(config, LlmConfig)

    def test_to_config_prompts_fol(self, dev_env: EnvType, prompts_fol: Path) -> None:
        """LlmConfig carries the same prompts_fol as LlmParams."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        config = params.to_config()
        assert config.prompts_fol == prompts_fol

    def test_to_config_chat_model(self, dev_env: EnvType, prompts_fol: Path) -> None:
        """LlmConfig chat_config uses the model set by LlmParams."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        config = params.to_config()
        assert config.chat_config.model == "gpt-4o-mini"

    def test_default_prompts_fol(self, dev_env: EnvType) -> None:
        """When prompts_fol is None, falls back to Path('prompts')."""
        params = LlmParams(env_type=dev_env)
        assert params.prompts_fol == Path("prompts")

    def test_str_contains_model(self, dev_env: EnvType, prompts_fol: Path) -> None:
        """__str__ includes the model name."""
        params = LlmParams(env_type=dev_env, prompts_fol=prompts_fol)
        assert "gpt-4o-mini" in str(params)

    def test_render_env(self, prompts_fol: Path) -> None:
        """RENDER location loads without error."""
        env = EnvType(stage=EnvStageType.DEV, location=EnvLocationType.RENDER)
        params = LlmParams(env_type=env, prompts_fol=prompts_fol)
        assert params.model == "gpt-4o-mini"
