"""Voice note session API router."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import UploadFile
from fastapi import status
from fastapi_tools.dependencies import get_current_user
from fastapi_tools.schemas.auth import SessionData
from loguru import logger as lg

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.recipe_note import RecipeNote
from kit_hub.voice.voice_session import FrozenSessionError
from kit_hub.voice.voice_session import SessionNotFoundError
from kit_hub.voice.voice_session import VoiceSessionManager
from kit_hub.voice.voice_to_recipe import VoiceToRecipeConverter
from kit_hub.webapp.api.schemas import RecipeDetailResponse
from kit_hub.webapp.api.schemas import VoiceNoteResponse
from kit_hub.webapp.api.schemas import VoiceSessionCreateResponse
from kit_hub.webapp.core.dependencies import get_crud
from kit_hub.webapp.core.dependencies import get_db
from kit_hub.webapp.core.dependencies import get_voice_converter
from kit_hub.webapp.core.dependencies import get_voice_manager

router = APIRouter(prefix="/voice", tags=["voice"])


def _note_to_detail(recipe_note: RecipeNote) -> dict:  # type: ignore[type-arg]
    """Serialise a ``RecipeNote`` to a plain dict for JSON responses.

    Args:
        recipe_note: Voice session log to serialise.

    Returns:
        Dictionary ready for JSON serialisation.
    """
    return recipe_note.model_dump(mode="json")


@router.post(
    "/create",
    summary="Create a new voice recording session",
    status_code=status.HTTP_201_CREATED,
)
async def create_voice_session(
    session: Annotated[SessionData, Depends(get_current_user)],
    voice_manager: Annotated[VoiceSessionManager, Depends(get_voice_manager)],
) -> VoiceSessionCreateResponse:
    """Create a new voice recording session for the current user.

    Args:
        session: Authenticated user session.
        voice_manager: Voice session lifecycle manager.

    Returns:
        New session ID to use for subsequent audio uploads.
    """
    session_id = await voice_manager.create_session(user_id=session.user_id)
    lg.info(f"Created voice session {session_id!r} for user {session.user_id!r}")
    return VoiceSessionCreateResponse(session_id=session_id)


@router.post("/{session_id}/upload", summary="Upload an audio clip to a session")
async def upload_audio(
    session_id: str,
    audio: UploadFile,
    _session: Annotated[SessionData, Depends(get_current_user)],
    voice_manager: Annotated[VoiceSessionManager, Depends(get_voice_manager)],
) -> VoiceNoteResponse:
    """Upload an audio clip, transcribe it, and append the result to the session.

    Args:
        session_id: Target voice session identifier.
        audio: Uploaded audio file (``audio/webm``, ``audio/ogg``, etc.).
        session: Authenticated user session.
        voice_manager: Voice session lifecycle manager.

    Returns:
        Transcribed text and timestamp of the appended note.

    Raises:
        HTTPException: 404 when ``session_id`` does not exist.
        HTTPException: 409 when the session is already frozen.
    """
    audio_data = await audio.read()
    content_type = audio.content_type or "audio/webm"
    try:
        note = await voice_manager.append_audio(
            session_id=session_id,
            audio_data=audio_data,
            content_type=content_type,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice session not found: {session_id}",
        ) from exc
    except FrozenSessionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    lg.debug(f"Appended note to session {session_id!r}: {note.text[:60]!r}")
    return VoiceNoteResponse(
        text=note.text,
        timestamp=note.timestamp.isoformat(),
    )


@router.post("/{session_id}/freeze", summary="Freeze a voice session")
async def freeze_voice_session(
    session_id: str,
    _session: Annotated[SessionData, Depends(get_current_user)],
    voice_manager: Annotated[VoiceSessionManager, Depends(get_voice_manager)],
) -> dict:  # type: ignore[type-arg]
    """Freeze a voice session; no more audio clips can be appended after this.

    Args:
        session_id: Target voice session identifier.
        session: Authenticated user session.
        voice_manager: Voice session lifecycle manager.

    Returns:
        The frozen ``RecipeNote`` as a JSON dict.

    Raises:
        HTTPException: 404 when ``session_id`` does not exist.
    """
    try:
        recipe_note = await voice_manager.freeze_session(session_id=session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice session not found: {session_id}",
        ) from exc
    lg.info(f"Frozen voice session {session_id!r}")
    return _note_to_detail(recipe_note)


@router.post(
    "/{session_id}/to-recipe",
    summary="Convert a voice session to a structured recipe",
    status_code=status.HTTP_201_CREATED,
)
async def voice_to_recipe(
    session_id: str,
    _session: Annotated[SessionData, Depends(get_current_user)],
    voice_manager: Annotated[VoiceSessionManager, Depends(get_voice_manager)],
    voice_converter: Annotated[VoiceToRecipeConverter, Depends(get_voice_converter)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> RecipeDetailResponse:
    """Convert a voice session transcript into a structured recipe and persist it.

    The session must have at least one note. If not yet frozen, the
    in-memory transcript is used as-is.

    Args:
        session_id: Target voice session identifier.
        _session: Authenticated user session.
        voice_manager: Voice session lifecycle manager.
        voice_converter: LLM bridge for ``RecipeNote -> RecipeCore``.
        db: Database session manager.
        crud: Recipe CRUD service.

    Returns:
        Full detail for the newly created recipe.

    Raises:
        HTTPException: 404 when ``session_id`` does not exist.
        HTTPException: 422 when the session has no notes.
    """
    recipe_note = voice_manager.get_session(session_id=session_id)
    if recipe_note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice session not found: {session_id}",
        )
    if not recipe_note.notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Voice session has no notes to convert.",
        )
    lg.info(f"Converting voice session {session_id!r} to recipe")
    recipe_core = await voice_converter.convert(recipe_note=recipe_note)
    async with db.get_session() as dbsession:
        row = await crud.create_recipe(
            dbsession,
            recipe=recipe_core,
            source=RecipeSource.VOICE_NOTE,
            source_id=session_id,
            user_id=_session.user_id,
        )
    lg.info(f"Created recipe '{recipe_core.name}' from voice session {session_id!r}")
    from kit_hub.webapp.api.v1.recipe_router import _row_to_detail  # noqa: PLC0415

    return _row_to_detail(row, tags=[])


@router.get("/{session_id}", summary="Get voice session transcript")
async def get_voice_session(
    session_id: str,
    _session: Annotated[SessionData, Depends(get_current_user)],
    voice_manager: Annotated[VoiceSessionManager, Depends(get_voice_manager)],
) -> dict:  # type: ignore[type-arg]
    """Return the current transcript of a voice session.

    Args:
        session_id: Target voice session identifier.
        session: Authenticated user session.
        voice_manager: Voice session lifecycle manager.

    Returns:
        The ``RecipeNote`` as a JSON dict.

    Raises:
        HTTPException: 404 when ``session_id`` does not exist.
    """
    recipe_note = voice_manager.get_session(session_id=session_id)
    if recipe_note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Voice session not found: {session_id}",
        )
    return _note_to_detail(recipe_note)
