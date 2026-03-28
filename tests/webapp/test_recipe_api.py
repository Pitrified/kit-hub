"""Tests for the Recipe API endpoints."""

from collections.abc import Generator
from datetime import UTC
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

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
from kit_hub.ingestion.ingest_service import EmptyMediaTextError
from kit_hub.ingestion.ingest_service import IngestService
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
            secret_key="test_secret_key_for_testing_only",  # noqa: S106 # pragma: allowlist secret
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
        session_id="test_session_api",
        user_id="user_api_test",
        email="api@test.com",
        name="API Tester",
        picture="https://example.com/pic.jpg",
        created_at=now,
        expires_at=datetime(2099, 12, 31, tzinfo=UTC),
    )


def _make_recipe_row(
    recipe_id: str = "recipe-uuid-001",
    name: str = "Test Pasta",
) -> RecipeRow:
    """Build a minimal RecipeRow for use in mock return values."""
    recipe_core = RecipeCore(
        name=name,
        preparations=[
            Preparation(
                preparation_name=None,
                ingredients=[Ingredient(name="pasta", quantity="200g")],
                steps=[Step(instruction="Boil water")],
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
    """Provide a test SessionData instance."""
    return _make_session()


@pytest.fixture
def recipe_app(mock_session_data: SessionData) -> FastAPI:
    """Build a FastAPI test app with the API router and mocked services."""
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
    app.state.ingest_service = AsyncMock(spec=IngestService)
    app.state.voice_manager = MagicMock()
    app.state.voice_converter = AsyncMock()
    return app


@pytest.fixture
def recipe_client(
    recipe_app: FastAPI,
    mock_session_data: SessionData,
) -> Generator[TestClient]:
    """Yield an authenticated test client for recipe API tests."""
    with TestClient(recipe_app) as client:
        session_store = recipe_app.state.session_store
        session_store.create_session(mock_session_data)
        client.cookies.set("session", mock_session_data.session_id)
        yield client


# ---------------------------------------------------------------------------
# list_recipes
# ---------------------------------------------------------------------------


def test_list_recipes_returns_200(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """GET /api/v1/recipes/ returns 200 with a recipe list."""
    row = _make_recipe_row()
    recipe_app.state.crud.list_recipes = AsyncMock(return_value=[row])

    resp = recipe_client.get("/api/v1/recipes/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["recipes"][0]["id"] == row.id
    assert data["recipes"][0]["name"] == row.name


def test_list_recipes_empty(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """GET /api/v1/recipes/ returns empty list when user has no recipes."""
    recipe_app.state.crud.list_recipes = AsyncMock(return_value=[])

    resp = recipe_client.get("/api/v1/recipes/")
    assert resp.status_code == 200
    assert resp.json()["recipes"] == []


def test_list_recipes_requires_auth(recipe_app: FastAPI) -> None:
    """GET /api/v1/recipes/ returns 401 for unauthenticated requests."""
    with TestClient(recipe_app) as client:
        resp = client.get("/api/v1/recipes/")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# create_recipe
# ---------------------------------------------------------------------------


def test_create_recipe_returns_201(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """POST /api/v1/recipes/ returns 201 with recipe detail."""
    row = _make_recipe_row()
    core = RecipeCore.model_validate_json(row.recipe_json)
    recipe_app.state.transcriber.ainvoke = AsyncMock(return_value=core)
    recipe_app.state.crud.create_recipe = AsyncMock(return_value=row)

    resp = recipe_client.post(
        "/api/v1/recipes/",
        json={"text": "Make pasta with tomato sauce", "source": "manual"},
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == row.id


def test_create_recipe_requires_auth(recipe_app: FastAPI) -> None:
    """POST /api/v1/recipes/ returns 401 for unauthenticated requests."""
    with TestClient(recipe_app) as client:
        resp = client.post("/api/v1/recipes/", json={"text": "pasta"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# ingest_recipe
# ---------------------------------------------------------------------------


def test_ingest_recipe_returns_201(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """POST /api/v1/recipes/ingest returns 201 on success."""
    row = _make_recipe_row(name="Insta Pasta")
    recipe_app.state.ingest_service.ingest_ig_url = AsyncMock(return_value=None)

    # Patch _fetch_latest_row to return our mock row
    with patch(
        "kit_hub.webapp.api.v1.recipe_router._fetch_latest_row",
        new=AsyncMock(return_value=row),
    ):
        resp = recipe_client.post(
            "/api/v1/recipes/ingest",
            json={"url": "https://www.instagram.com/p/abc123/"},
        )
    assert resp.status_code == 201
    assert resp.json()["id"] == row.id


def test_ingest_recipe_empty_media_returns_422(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """POST /api/v1/recipes/ingest returns 422 when post has no text."""
    url = "https://www.instagram.com/p/empty/"
    recipe_app.state.ingest_service.ingest_ig_url = AsyncMock(
        side_effect=EmptyMediaTextError(url)
    )

    resp = recipe_client.post("/api/v1/recipes/ingest", json={"url": url})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# get_recipe
# ---------------------------------------------------------------------------


def test_get_recipe_returns_200(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """GET /api/v1/recipes/{id} returns 200 with detail."""
    row = _make_recipe_row()
    recipe_app.state.crud.get_recipe = AsyncMock(return_value=row)

    resp = recipe_client.get(f"/api/v1/recipes/{row.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == row.id


def test_get_recipe_returns_404_when_missing(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """GET /api/v1/recipes/{id} returns 404 when recipe is not found."""
    recipe_app.state.crud.get_recipe = AsyncMock(return_value=None)

    resp = recipe_client.get("/api/v1/recipes/nonexistent-id")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# delete_recipe
# ---------------------------------------------------------------------------


def test_delete_recipe_returns_204(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """DELETE /api/v1/recipes/{id} returns 204 on success."""
    recipe_app.state.crud.delete_recipe = AsyncMock(return_value=None)

    resp = recipe_client.delete("/api/v1/recipes/recipe-uuid-001")
    assert resp.status_code == 204


def test_delete_recipe_returns_404_when_missing(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """DELETE /api/v1/recipes/{id} returns 404 when recipe is not found."""
    recipe_app.state.crud.delete_recipe = AsyncMock(
        side_effect=KeyError("recipe-uuid-001")
    )

    resp = recipe_client.delete("/api/v1/recipes/recipe-uuid-001")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# sort_recipes
# ---------------------------------------------------------------------------


def test_sort_recipes_returns_200(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """POST /api/v1/recipes/sort returns 200 on success."""
    recipe_app.state.crud.reorder_recipes = AsyncMock(return_value=None)

    resp = recipe_client.post(
        "/api/v1/recipes/sort",
        json={"recipe_ids": ["id-1", "id-2", "id-3"]},
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# update_recipe
# ---------------------------------------------------------------------------


def test_update_recipe_returns_200(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """PUT /api/v1/recipes/{id} returns 200 with updated recipe."""
    row = _make_recipe_row()
    recipe_app.state.crud.update_recipe = AsyncMock(return_value=row)
    recipe_app.state.crud.get_recipe = AsyncMock(return_value=row)

    new_core = RecipeCore(
        name="Updated Pasta",
        preparations=[
            Preparation(
                preparation_name=None,
                ingredients=[Ingredient(name="pasta", quantity="300g")],
                steps=[Step(instruction="Cook on high heat")],
            )
        ],
    )
    resp = recipe_client.put(
        f"/api/v1/recipes/{row.id}",
        json=new_core.model_dump(mode="json"),
    )
    assert resp.status_code == 200


def test_update_recipe_returns_404_when_missing(
    recipe_client: TestClient,
    recipe_app: FastAPI,
) -> None:
    """PUT /api/v1/recipes/{id} returns 404 when recipe does not exist."""
    recipe_app.state.crud.update_recipe = AsyncMock(side_effect=KeyError("nonexistent"))

    new_core = RecipeCore(
        name="Ghost Pasta",
        preparations=[
            Preparation(
                preparation_name=None,
                ingredients=[],
                steps=[],
            )
        ],
    )
    resp = recipe_client.put(
        "/api/v1/recipes/nonexistent",
        json=new_core.model_dump(mode="json"),
    )
    assert resp.status_code == 404
