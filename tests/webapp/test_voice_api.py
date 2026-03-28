"""Tests for the Voice API endpoints."""

from collections.abc import Generator
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi_tools import create_app
from fastapi_tools.config.webapp_config import CORSConfig
from fastapi_tools.config.webapp_config import GoogleOAuthConfig
from fastapi_tools.config.webapp_config import RateLimitConfig
from fastapi_tools.config.webapp_config import SessionConfig
from fastapi_tools.config.webapp_config import WebappConfig
from fastapi_tools.schemas.auth import SessionData
import pytest

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.models import RecipeRow
from kit_hub.db.session import DatabaseSession
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.recipe_note import Note
from kit_hub.recipes.recipe_note import RecipeNote
from kit_hub.voice.voice_session import FrozenSessionError
from kit_hub.voice.voice_session import SessionNotFoundError
from kit_hub.voice.voice_session import VoiceSessionManager
from kit_hub.voice.voice_to_recipe import VoiceToRecipeConverter
from kit_hub.webapp.api.v1.api_router import router as api_v1_router
from kit_hub.webapp.routers.pages_router import router as pages_router

_PROJECT_ROOT = Path(__file__).parent.parent.parent
_STATIC_DIR = _PROJECT_ROOT / "static"
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"


def _make_config() -> WebappConfig:
    return WebappConfig(
        host="127.0.0.1",
        port=8000,
        debug=True,
        app_name="Test API",
        app_version="0.0.0-test",
        cors=CORSConfig(allow_origins=["http://localhost:3000"]),
        session=SessionConfig(
            secret_key="test_secret_key_voice_tests",  # noqa: S106 # pragma: allowlist secret
            max_age=3600,
        ),
        rate_limit=RateLimitConfig(requests_per_minute=1000),
        google_oauth=GoogleOAuthConfig(
            client_id="test_id",
            client_secret="test_secret",  # noqa: S106 # pragma: allowlist secret
            redirect_uri="http://localhost:8000/auth/google/callback",
        ),
    )


def _make_session() -> SessionData:
    now = datetime.now(UTC)
    return SessionData(
        session_id="test_voice_session",
        user_id="voice_user",
        email="voice@test.com",
        name="Voice Tester",
        picture="https://example.com/pic.jpg",
        created_at=now,
        expires_at=datetime(2099, 12, 31, tzinfo=UTC),
    )


def _make_recipe_row(recipe_id: str = "voice-recipe-001") -> RecipeRow:
    recipe_core = RecipeCore(
        name="Voice Recipe",
        preparations=[
            Preparation(
                preparation_name=None,
                ingredients=[Ingredient(name="eggs", quantity="2")],
                steps=[Step(instruction="Scramble eggs")],
            )
        ],
    )
    row = MagicMock(spec=RecipeRow)
    row.id = recipe_id
    row.name = "Voice Recipe"
    row.source = RecipeSource.VOICE_NOTE.value
    row.source_id = "voice-session-id"
    row.meal_course = None
    row.is_public = False
    row.sort_index = 0
    row.recipe_json = recipe_core.model_dump_json()
    row.tags = []
    row.created_at = datetime.now(UTC)
    row.updated_at = datetime.now(UTC)
    return row


@pytest.fixture
def mock_session_data() -> SessionData:
    """Provide mock session data for voice API tests."""
    return _make_session()


@pytest.fixture
def voice_app(mock_session_data: SessionData) -> FastAPI:
    """Build a FastAPI test app with mocked voice services."""
    config = _make_config()
    app = create_app(
        config=config,
        extra_routers=[pages_router, api_v1_router],
        static_dir=_STATIC_DIR,
        templates_dir=_TEMPLATES_DIR,
    )
    mock_crud = AsyncMock(spec=RecipeCRUDService)
    mock_db = MagicMock(spec=DatabaseSession)
    mock_db.get_session.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_db.get_session.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_voice_manager = MagicMock(spec=VoiceSessionManager)
    mock_voice_converter = AsyncMock(spec=VoiceToRecipeConverter)

    app.state.db = mock_db
    app.state.crud = mock_crud
    app.state.transcriber = AsyncMock(spec=RecipeCoreTranscriber)
    app.state.editor = MagicMock()
    app.state.ingest_service = MagicMock()
    app.state.voice_manager = mock_voice_manager
    app.state.voice_converter = mock_voice_converter
    return app


@pytest.fixture
def voice_client(
    voice_app: FastAPI,
    mock_session_data: SessionData,
) -> Generator[TestClient]:
    """Yield an authenticated test client for voice API tests."""
    with TestClient(voice_app) as client:
        session_store = voice_app.state.session_store
        session_store.create_session(mock_session_data)
        client.cookies.set("session", mock_session_data.session_id)
        yield client


# ---------------------------------------------------------------------------
# create_voice_session
# ---------------------------------------------------------------------------


def test_create_session_returns_201(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/create returns 201 with a session_id."""
    voice_app.state.voice_manager.create_session = AsyncMock(
        return_value="20260327_120000_abcd1234"
    )

    resp = voice_client.post("/api/v1/voice/create")
    assert resp.status_code == 201
    assert resp.json()["session_id"] == "20260327_120000_abcd1234"


def test_create_session_requires_auth(voice_app: FastAPI) -> None:
    """POST /api/v1/voice/create returns 401 for unauthenticated requests."""
    with TestClient(voice_app) as client:
        resp = client.post("/api/v1/voice/create")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# upload_audio
# ---------------------------------------------------------------------------


def test_upload_audio_returns_200(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/upload returns 200 with transcribed note."""
    fake_note = Note(text="Add a pinch of salt", timestamp=datetime.now(UTC))
    voice_app.state.voice_manager.append_audio = AsyncMock(return_value=fake_note)

    resp = voice_client.post(
        "/api/v1/voice/test-session/upload",
        files={"audio": ("clip.webm", b"fake-audio-bytes", "audio/webm")},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["text"] == "Add a pinch of salt"
    assert "timestamp" in data


def test_upload_audio_returns_404_for_unknown_session(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/upload returns 404 for unknown session."""
    voice_app.state.voice_manager.append_audio = AsyncMock(
        side_effect=SessionNotFoundError("ghost-session")
    )

    resp = voice_client.post(
        "/api/v1/voice/ghost-session/upload",
        files={"audio": ("clip.webm", b"bytes", "audio/webm")},
    )
    assert resp.status_code == 404


def test_upload_audio_returns_409_for_frozen_session(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/upload returns 409 for a frozen session."""
    voice_app.state.voice_manager.append_audio = AsyncMock(
        side_effect=FrozenSessionError("frozen-session")
    )

    resp = voice_client.post(
        "/api/v1/voice/frozen-session/upload",
        files={"audio": ("clip.webm", b"bytes", "audio/webm")},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# freeze_session
# ---------------------------------------------------------------------------


def test_freeze_session_returns_200(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/freeze returns 200 with RecipeNote JSON."""
    note = Note(text="Stir well", timestamp=datetime.now(UTC))
    recipe_note = RecipeNote(notes=[note])
    voice_app.state.voice_manager.freeze_session = AsyncMock(return_value=recipe_note)

    resp = voice_client.post("/api/v1/voice/active-session/freeze")
    assert resp.status_code == 200
    data = resp.json()
    assert "notes" in data
    assert data["notes"][0]["text"] == "Stir well"


def test_freeze_session_returns_404_for_unknown_session(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/freeze returns 404 for unknown session."""
    voice_app.state.voice_manager.freeze_session = AsyncMock(
        side_effect=SessionNotFoundError("ghost")
    )

    resp = voice_client.post("/api/v1/voice/ghost/freeze")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# get_voice_session
# ---------------------------------------------------------------------------


def test_get_session_returns_200(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """GET /api/v1/voice/{id} returns 200 with session transcript."""
    note = Note(text="Boil the pasta", timestamp=datetime.now(UTC))
    recipe_note = RecipeNote(notes=[note])
    voice_app.state.voice_manager.get_session = MagicMock(return_value=recipe_note)

    resp = voice_client.get("/api/v1/voice/some-session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["notes"][0]["text"] == "Boil the pasta"


def test_get_session_returns_404_when_missing(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """GET /api/v1/voice/{id} returns 404 when session is not found."""
    voice_app.state.voice_manager.get_session = MagicMock(return_value=None)

    resp = voice_client.get("/api/v1/voice/missing-session")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# voice_to_recipe
# ---------------------------------------------------------------------------


def test_voice_to_recipe_returns_201(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/to-recipe returns 201 with recipe detail."""
    note = Note(text="Scramble eggs gently", timestamp=datetime.now(UTC))
    recipe_note = RecipeNote(notes=[note])
    voice_app.state.voice_manager.get_session = MagicMock(return_value=recipe_note)

    recipe_core = RecipeCore(
        name="Scrambled Eggs",
        preparations=[
            Preparation(
                preparation_name=None,
                ingredients=[Ingredient(name="eggs", quantity="2")],
                steps=[Step(instruction="Scramble eggs gently")],
            )
        ],
    )
    voice_app.state.voice_converter.convert = AsyncMock(return_value=recipe_core)

    row = _make_recipe_row()
    voice_app.state.crud.create_recipe = AsyncMock(return_value=row)

    resp = voice_client.post("/api/v1/voice/active-session/to-recipe")
    assert resp.status_code == 201
    assert resp.json()["id"] == row.id


def test_voice_to_recipe_returns_404_when_session_missing(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/to-recipe returns 404 when session is not found."""
    voice_app.state.voice_manager.get_session = MagicMock(return_value=None)

    resp = voice_client.post("/api/v1/voice/missing-session/to-recipe")
    assert resp.status_code == 404


def test_voice_to_recipe_returns_422_when_no_notes(
    voice_client: TestClient,
    voice_app: FastAPI,
) -> None:
    """POST /api/v1/voice/{id}/to-recipe returns 422 when no notes recorded."""
    empty_note = RecipeNote(notes=[])
    voice_app.state.voice_manager.get_session = MagicMock(return_value=empty_note)

    resp = voice_client.post("/api/v1/voice/empty-session/to-recipe")
    assert resp.status_code == 422
