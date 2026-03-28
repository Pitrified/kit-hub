"""FastAPI application factory for kit_hub."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi_tools import create_app
from fastapi_tools.auth.google import GoogleAuthService
from fastapi_tools.auth.google import SessionStore
from loguru import logger as lg

from kit_hub.params.kit_hub_params import get_kit_hub_params
from kit_hub.params.kit_hub_params import get_kit_hub_paths
from kit_hub.params.kit_hub_params import get_webapp_params
from kit_hub.webapp.api.v1.api_router import router as api_v1_router
from kit_hub.webapp.routers.pages_router import router as pages_router


def build_app() -> FastAPI:
    """Build the FastAPI application with services wired via lifespan.

    All services (database, LLM chains, voice session manager, ingest service)
    are created inside the lifespan context manager and attached to
    ``app.state`` before the first request is handled.

    Returns:
        Configured FastAPI application instance.
    """
    params = get_webapp_params()
    config = params.to_config()
    paths = get_kit_hub_paths()

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
        # --- fastapi-tools default lifespan (SessionStore + GoogleAuthService) ---
        session_store = SessionStore()
        app.state.session_store = session_store
        auth_service = GoogleAuthService(
            oauth_config=config.google_oauth,
            session_config=config.session,
            session_store=session_store,
        )
        app.state.auth_service = auth_service

        # --- kit-hub services ---
        from kit_hub.db.crud_service import RecipeCRUDService  # noqa: I001, PLC0415
        from kit_hub.db.session import DatabaseSession  # noqa: PLC0415
        from kit_hub.ingestion.factory import build_ingest_service  # noqa: PLC0415
        from kit_hub.llm.editor import RecipeCoreEditor  # noqa: PLC0415
        from kit_hub.llm.transcriber import RecipeCoreTranscriber  # noqa: PLC0415
        from kit_hub.voice.voice_session import VoiceSessionManager  # noqa: PLC0415
        from kit_hub.voice.voice_to_recipe import (  # noqa: PLC0415
            VoiceToRecipeConverter,
        )
        from kit_hub.voice.whisper_adapter import WhisperAudioTranscriber  # noqa: PLC0415

        lg.info("Kit Hub webapp starting up")
        kit_hub = get_kit_hub_params()

        db_config = kit_hub.db.to_config()
        db = DatabaseSession(db_config)
        await db.init_db()
        lg.info("Database initialised")

        crud = RecipeCRUDService()
        llm_config = kit_hub.llm.to_config()
        transcriber = RecipeCoreTranscriber(llm_config)
        editor = RecipeCoreEditor(llm_config)
        ingest_service = build_ingest_service(kit_hub, crud, db)
        voice_converter = VoiceToRecipeConverter(
            transcriber=RecipeCoreTranscriber(llm_config),
        )
        audio_transcriber = WhisperAudioTranscriber.from_default()
        voice_manager = VoiceSessionManager(
            notes_dir=kit_hub.paths.notes_fol,
            transcriber=audio_transcriber,
        )

        app.state.db = db
        app.state.crud = crud
        app.state.transcriber = transcriber
        app.state.editor = editor
        app.state.ingest_service = ingest_service
        app.state.voice_manager = voice_manager
        app.state.voice_converter = voice_converter
        lg.info("All services initialised and attached to app.state")

        yield

        # --- shutdown ---
        await db.close()
        lg.info("Database connection closed")

    app = create_app(
        config=config,
        extra_routers=[pages_router, api_v1_router],
        static_dir=paths.static_fol,
        templates_dir=paths.templates_fol,
        lifespan=_lifespan,
    )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Log validation error details and return 422."""
        lg.warning(
            "Request validation error"
            f" | {request.method} {request.url.path}"
            f" | content-type: {request.headers.get('content-type', '<not set>')}"
            f" | errors: {exc.errors()}"
        )
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    return app
