"""Webapp dependency injection helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import Request  # noqa: TC002 - FastAPI needs runtime access

from kit_hub.params.kit_hub_params import get_webapp_params

if TYPE_CHECKING:
    from fastapi_tools.config.webapp_config import WebappConfig

    from kit_hub.db.crud_service import RecipeCRUDService
    from kit_hub.db.session import DatabaseSession
    from kit_hub.ingestion.ingest_service import IngestService
    from kit_hub.llm.editor import RecipeCoreEditor
    from kit_hub.llm.transcriber import RecipeCoreTranscriber
    from kit_hub.voice.voice_session import VoiceSessionManager
    from kit_hub.voice.voice_to_recipe import VoiceToRecipeConverter


@lru_cache
def get_settings() -> WebappConfig:
    """Get webapp configuration settings.

    Returns:
        WebappConfig instance.
    """
    return get_webapp_params().to_config()


def get_db(request: Request) -> DatabaseSession:
    """Provide the ``DatabaseSession`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        DatabaseSession stored at ``app.state.db``.
    """
    return request.app.state.db  # type: ignore[no-any-return]


def get_crud(request: Request) -> RecipeCRUDService:
    """Provide the ``RecipeCRUDService`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        RecipeCRUDService stored at ``app.state.crud``.
    """
    return request.app.state.crud  # type: ignore[no-any-return]


def get_transcriber(request: Request) -> RecipeCoreTranscriber:
    """Provide the ``RecipeCoreTranscriber`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        RecipeCoreTranscriber stored at ``app.state.transcriber``.
    """
    return request.app.state.transcriber  # type: ignore[no-any-return]


def get_editor(request: Request) -> RecipeCoreEditor:
    """Provide the ``RecipeCoreEditor`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        RecipeCoreEditor stored at ``app.state.editor``.
    """
    return request.app.state.editor  # type: ignore[no-any-return]


def get_ingest_service(request: Request) -> IngestService:
    """Provide the ``IngestService`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        IngestService stored at ``app.state.ingest_service``.
    """
    return request.app.state.ingest_service  # type: ignore[no-any-return]


def get_voice_manager(request: Request) -> VoiceSessionManager:
    """Provide the ``VoiceSessionManager`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        VoiceSessionManager stored at ``app.state.voice_manager``.
    """
    return request.app.state.voice_manager  # type: ignore[no-any-return]


def get_voice_converter(request: Request) -> VoiceToRecipeConverter:
    """Provide the ``VoiceToRecipeConverter`` from app state.

    Args:
        request: Incoming HTTP request.

    Returns:
        VoiceToRecipeConverter stored at ``app.state.voice_converter``.
    """
    return request.app.state.voice_converter  # type: ignore[no-any-return]
