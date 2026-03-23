"""FastAPI application factory for kit_hub."""

from fastapi import FastAPI
from fastapi_tools import create_app

from kit_hub.params.kit_hub_params import get_kit_hub_paths
from kit_hub.params.kit_hub_params import get_webapp_params
from kit_hub.webapp.routers.pages_router import router as pages_router


def build_app() -> FastAPI:
    """Build the FastAPI application using fastapi-tools.

    Returns:
        Configured FastAPI application instance.
    """
    params = get_webapp_params()
    config = params.to_config()
    paths = get_kit_hub_paths()

    return create_app(
        config=config,
        extra_routers=[pages_router],
        static_dir=paths.static_fol,
        templates_dir=paths.templates_fol,
    )
