"""Application instance for uvicorn.

Entry point: uvicorn kit_hub.webapp.app:app
"""

from kit_hub.webapp.main import build_app

# Create application instance
app = build_app()

if __name__ == "__main__":
    import uvicorn

    from kit_hub.params.kit_hub_params import get_webapp_params

    params = get_webapp_params()
    uvicorn.run(
        "kit_hub.webapp.app:app",
        host=params.host,
        port=params.port,
        reload=params.debug,
    )
