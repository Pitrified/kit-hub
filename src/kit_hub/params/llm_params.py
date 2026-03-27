"""LLM parameters - loads actual LLM chain configuration values.

Follows the Config / Params pattern: this class loads real values and
constructs an ``LlmConfig`` via ``to_config()``.  No Pydantic models here.

The model and temperature are identical across all environments for now
(``gpt-4o-mini`` at ``0.2``).  The OpenAI API key is loaded from the
``OPENAI_API_KEY`` environment variable by ``ChatOpenAIConfig`` automatically
via ``pydantic-settings``; no manual loading is needed here.

See Also:
    ``LlmConfig`` - the paired config model in ``src/kit_hub/config/``.
    ``docs/guides/params_config.md`` - full guide with rationale.
"""

from pathlib import Path

from llm_core.chat.config.openai import ChatOpenAIConfig

from kit_hub.config.llm_config import LlmConfig
from kit_hub.params.env_type import EnvLocationType
from kit_hub.params.env_type import EnvStageType
from kit_hub.params.env_type import EnvType
from kit_hub.params.env_type import UnknownEnvLocationError
from kit_hub.params.env_type import UnknownEnvStageError


class LlmParams:
    """LLM chain parameters for the given deployment environment.

    Loads the model name and temperature based on env stage, then
    constructs an ``LlmConfig`` via ``to_config()``.

    Args:
        env_type: Deployment environment (stage + location).  If ``None``,
            inferred from ``ENV_STAGE_TYPE`` and ``ENV_LOCATION_TYPE``
            environment variables (defaults: ``dev`` / ``local``).
        prompts_fol: Root folder containing versioned Jinja prompt
            subdirectories.  Typically ``KitHubPaths.prompts_fol``.
    """

    def __init__(
        self,
        env_type: EnvType | None = None,
        prompts_fol: Path | None = None,
    ) -> None:
        """Load LLM params for the given environment.

        Args:
            env_type: Deployment environment (stage + location).
                If ``None``, inferred from environment variables.
            prompts_fol: Root folder containing prompt subdirectories.
                Falls back to ``Path("prompts")`` (relative) when ``None``.
        """
        self.env_type: EnvType = env_type or EnvType.from_env_var()
        self.prompts_fol: Path = prompts_fol or Path("prompts")
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
        self.temperature: float = 0.2

    def _load_dev_params(self) -> None:
        """Set DEV-stage attributes, then dispatch on location."""
        self.model: str = "gpt-4o-mini"
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
        self.model = "gpt-4o-mini"
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

    def to_config(self) -> LlmConfig:
        """Assemble and return the typed LLM config model.

        Returns:
            LlmConfig: A Pydantic model carrying the LLM chain settings.
        """
        return LlmConfig(
            chat_config=ChatOpenAIConfig(
                model=self.model,
                temperature=self.temperature,
            ),
            prompts_fol=self.prompts_fol,
        )

    def __str__(self) -> str:
        """Return a human-readable summary."""
        return (
            f"LlmParams: model={self.model!r}"
            f" temperature={self.temperature}"
            f" prompts_fol={self.prompts_fol}"
        )

    def __repr__(self) -> str:
        """Return the string representation of the object."""
        return str(self)
