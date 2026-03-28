"""Tests for the recipe and cook-queue page routes."""

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
from kit_hub.llm.editor import RecipeCoreEditor
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_enums import RecipeSource
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
            secret_key="test_secret_key_page_tests",  # noqa: S106 # pragma: allowlist secret
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
        session_id="test_pages_session",
        user_id="pages_user",
        email="pages@test.com",
        name="Pages Tester",
        picture="https://example.com/pic.jpg",
        created_at=now,
        expires_at=datetime(2099, 12, 31, tzinfo=UTC),
    )


def _make_recipe_row(
    recipe_id: str = "page-recipe-001",
    name: str = "Page Test Pasta",
) -> RecipeRow:
    recipe_core = RecipeCore(
        name=name,
        preparations=[
            Preparation(
                preparation_name=None,
                ingredients=[Ingredient(name="spaghetti", quantity="200g")],
                steps=[Step(instruction="Cook spaghetti")],
            )
        ],
    )
    row = MagicMock(spec=RecipeRow)
    row.id = recipe_id
    row.name = name
    row.source = RecipeSource.MANUAL.value
    row.source_id = ""
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
    """Provide mock session data for page tests."""
    return _make_session()


@pytest.fixture
def page_app(mock_session_data: SessionData) -> FastAPI:
    """Build a FastAPI test app with mocked services for page tests."""
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

    app.state.db = mock_db
    app.state.crud = mock_crud
    app.state.transcriber = AsyncMock(spec=RecipeCoreTranscriber)
    app.state.editor = AsyncMock(spec=RecipeCoreEditor)
    app.state.ingest_service = MagicMock()
    app.state.voice_manager = MagicMock()
    app.state.voice_converter = AsyncMock()
    return app


@pytest.fixture
def page_client(
    page_app: FastAPI,
    mock_session_data: SessionData,
) -> Generator[TestClient]:
    """Yield an authenticated test client for page tests."""
    with TestClient(page_app) as client:
        session_store = page_app.state.session_store
        session_store.create_session(mock_session_data)
        client.cookies.set("session", mock_session_data.session_id)
        yield client


# ---------------------------------------------------------------------------
# /recipes page
# ---------------------------------------------------------------------------


def test_recipes_page_returns_200(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /recipes renders the recipe list page successfully."""
    row = _make_recipe_row()
    page_app.state.crud.list_recipes = AsyncMock(return_value=[row])

    resp = page_client.get("/recipes")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_recipes_page_shows_recipe_name(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /recipes renders recipe names in the response body."""
    row = _make_recipe_row(name="Carbonara")
    page_app.state.crud.list_recipes = AsyncMock(return_value=[row])

    resp = page_client.get("/recipes")
    assert resp.status_code == 200
    assert "Carbonara" in resp.text


def test_recipes_page_empty_state(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /recipes shows empty-state message when user has no recipes."""
    page_app.state.crud.list_recipes = AsyncMock(return_value=[])

    resp = page_client.get("/recipes")
    assert resp.status_code == 200
    assert "No recipes yet" in resp.text


def test_recipes_page_requires_auth(page_app: FastAPI) -> None:
    """GET /recipes redirects unauthenticated users."""
    with TestClient(page_app, follow_redirects=False) as client:
        resp = client.get("/recipes")
    assert resp.status_code in (302, 401)


# ---------------------------------------------------------------------------
# /recipes/{id} page
# ---------------------------------------------------------------------------


def test_recipe_detail_returns_200(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /recipes/{id} renders the recipe detail page."""
    row = _make_recipe_row(name="Risotto")
    page_app.state.crud.get_recipe = AsyncMock(return_value=row)

    resp = page_client.get(f"/recipes/{row.id}")
    assert resp.status_code == 200
    assert "Risotto" in resp.text


def test_recipe_detail_returns_404_when_missing(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /recipes/{id} returns 404 when the recipe does not exist."""
    page_app.state.crud.get_recipe = AsyncMock(return_value=None)

    resp = page_client.get("/recipes/nonexistent-id")
    assert resp.status_code == 404


def test_recipe_detail_shows_ingredients(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /recipes/{id} renders ingredients in the page body."""
    row = _make_recipe_row(name="Pasta Test")
    page_app.state.crud.get_recipe = AsyncMock(return_value=row)

    resp = page_client.get(f"/recipes/{row.id}")
    assert resp.status_code == 200
    assert "spaghetti" in resp.text


# ---------------------------------------------------------------------------
# /cook page
# ---------------------------------------------------------------------------


def test_cook_page_returns_200(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /cook renders the cook-soon queue page."""
    row = _make_recipe_row(name="Queue Pasta")
    page_app.state.crud.list_recipes = AsyncMock(return_value=[row])

    resp = page_client.get("/cook")
    assert resp.status_code == 200
    assert "Cook Queue" in resp.text
    assert "Queue Pasta" in resp.text


def test_cook_page_empty_state(
    page_client: TestClient,
    page_app: FastAPI,
) -> None:
    """GET /cook shows empty state when no recipes exist."""
    page_app.state.crud.list_recipes = AsyncMock(return_value=[])

    resp = page_client.get("/cook")
    assert resp.status_code == 200
    assert "No recipes" in resp.text


# ---------------------------------------------------------------------------
# /voice page
# ---------------------------------------------------------------------------


def test_voice_page_returns_200(
    page_client: TestClient,
) -> None:
    """GET /voice renders the voice note page."""
    resp = page_client.get("/voice")
    assert resp.status_code == 200
    assert "Voice Note" in resp.text


def test_voice_page_requires_auth(page_app: FastAPI) -> None:
    """GET /voice redirects unauthenticated users."""
    with TestClient(page_app, follow_redirects=False) as client:
        resp = client.get("/voice")
    assert resp.status_code in (302, 401)
