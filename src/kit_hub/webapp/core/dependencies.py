"""Webapp dependency injection helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from kit_hub.params.kit_hub_params import get_webapp_params

if TYPE_CHECKING:
    from fastapi_tools.config.webapp_config import WebappConfig


@lru_cache
def get_settings() -> WebappConfig:
    """Get webapp configuration settings.

    Returns:
        WebappConfig instance.
    """
    return get_webapp_params().to_config()
