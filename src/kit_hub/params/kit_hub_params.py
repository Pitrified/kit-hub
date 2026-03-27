"""KitHub project params.

Parameters are actual value of the config.

The class is a singleton, so it can be accessed from anywhere in the code.

There is a parameter regarding the environment type (stage and location), which
is used to load different paths and other parameters based on the environment.
"""

from loguru import logger as lg

from kit_hub.metaclasses.singleton import Singleton
from kit_hub.params.db_params import DbParams
from kit_hub.params.env_type import EnvType
from kit_hub.params.kit_hub_paths import KitHubPaths
from kit_hub.params.llm_params import LlmParams
from kit_hub.params.sample_params import SampleParams
from kit_hub.params.webapp import WebappParams


class KitHubParams(metaclass=Singleton):
    """KitHub project parameters."""

    def __init__(self) -> None:
        """Load the KitHub params."""
        lg.info("Loading KitHub params")
        self.set_env_type()

    def set_env_type(self, env_type: EnvType | None = None) -> None:
        """Set the environment type.

        Args:
            env_type (EnvType | None): The environment type.
                If None, it will be set from the environment variables.
                Defaults to None.
        """
        if env_type is not None:
            self.env_type = env_type
        else:
            self.env_type = EnvType.from_env_var()
        self.load_config()

    def load_config(self) -> None:
        """Load the kit_hub configuration."""
        self.paths = KitHubPaths(env_type=self.env_type)
        self.sample = SampleParams()
        self.db = DbParams(env_type=self.env_type, data_fol=self.paths.data_fol)
        self.llm = LlmParams(env_type=self.env_type, prompts_fol=self.paths.prompts_fol)
        self.webapp = WebappParams(
            stage=self.env_type.stage,
            location=self.env_type.location,
        )

    def __str__(self) -> str:
        """Return the string representation of the object."""
        s = "KitHubParams:"
        s += f"\n{self.paths}"
        s += f"\n{self.sample}"
        s += f"\n{self.db}"
        s += f"\n{self.llm}"
        s += f"\n{self.webapp}"
        return s

    def __repr__(self) -> str:
        """Return the string representation of the object."""
        return str(self)


def get_kit_hub_params() -> KitHubParams:
    """Get the kit_hub params."""
    return KitHubParams()


def get_kit_hub_paths() -> KitHubPaths:
    """Get the kit_hub paths."""
    return get_kit_hub_params().paths


def get_webapp_params() -> WebappParams:
    """Get the webapp params."""
    return get_kit_hub_params().webapp
