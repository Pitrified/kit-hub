"""FastAPI application factory for kit_hub."""

from pathlib import Path

from fastapi import FastAPI
from fastapi_tools import create_app
from loguru import logger as lg

from kit_hub.params.kit_hub_params import get_kit_hub_params
from kit_hub.params.kit_hub_params import get_kit_hub_paths
from kit_hub.params.kit_hub_params import get_webapp_params
from kit_hub.webapp.api.v1.api_router import router as api_v1_router
from kit_hub.webapp.routers.pages_router import router as pages_router


class _StubAudioTranscriber:
    """No-op audio transcriber used when Whisper is not configured.

    Returns a placeholder message instead of a real transcript. Replace
    this with a ``media-downloader`` Whisper transcriber in production.
    """

    async def atranscribe(self, audio_fp: Path) -> str:  # noqa: ARG002
        """Return a fixed placeholder transcript.

        Args:
            audio_fp: Path to the audio file (ignored).

        Returns:
            Placeholder transcription string.
        """
        return "[Transcription service not configured]"


def build_app() -> FastAPI:
    """Build the FastAPI application with services wired via lifespan.

    Registers startup and shutdown callbacks that initialise the database,
    build all service objects, and attach them to ``app.state``.

    Returns:
        Configured FastAPI application instance.
    """
    params = get_webapp_params()
    config = params.to_config()
    paths = get_kit_hub_paths()

    app = create_app(
        config=config,
        extra_routers=[pages_router, api_v1_router],
        static_dir=paths.static_fol,
        templates_dir=paths.templates_fol,
    )

    async def _startup() -> None:
        from kit_hub.db.crud_service import RecipeCRUDService  # noqa: PLC0415
        from kit_hub.db.session import DatabaseSession  # noqa: PLC0415
        from kit_hub.ingestion.factory import build_ingest_service  # noqa: PLC0415
        from kit_hub.llm.editor import RecipeCoreEditor  # noqa: PLC0415
        from kit_hub.llm.transcriber import RecipeCoreTranscriber  # noqa: PLC0415
        from kit_hub.voice.voice_session import VoiceSessionManager  # noqa: PLC0415
        from kit_hub.voice.voice_to_recipe import (  # noqa: PLC0415
            VoiceToRecipeConverter,
        )

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
        voice_manager = VoiceSessionManager(
            notes_dir=kit_hub.paths.notes_fol,
            transcriber=_StubAudioTranscriber(),
        )

        app.state.db = db
        app.state.crud = crud
        app.state.transcriber = transcriber
        app.state.editor = editor
        app.state.ingest_service = ingest_service
        app.state.voice_manager = voice_manager
        app.state.voice_converter = voice_converter
        lg.info("All services initialised and attached to app.state")

    async def _shutdown() -> None:
        if hasattr(app.state, "db"):
            await app.state.db.close()
            lg.info("Database connection closed")

    app.router.on_startup.append(_startup)
    app.router.on_shutdown.append(_shutdown)

    return app
