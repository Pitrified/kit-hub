"""Tests for ORM models.

Covers row construction and the RecipeCore JSON round-trip.
Uses an in-memory SQLite database via DatabaseSession.
"""

from datetime import UTC
from datetime import datetime
import uuid

import pytest
from sqlalchemy import select

from kit_hub.config.db_config import DbConfig
from kit_hub.db.models import AuthorRow
from kit_hub.db.models import RecipeRow
from kit_hub.db.models import TagRow
from kit_hub.db.session import DatabaseSession
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_enums import RecipeSource

_IN_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db() -> DatabaseSession:
    """Provide an initialised in-memory DatabaseSession."""
    config = DbConfig(db_url=_IN_MEMORY_URL)
    session = DatabaseSession(config)
    await session.init_db()
    return session


def _make_recipe_core(name: str = "Test Recipe") -> RecipeCore:
    return RecipeCore(
        name=name,
        preparations=[
            Preparation(
                ingredients=[Ingredient(name="flour", quantity="500g")],
                steps=[Step(instruction="Mix flour with water.")],
            )
        ],
        source=RecipeSource.MANUAL,
    )


class TestRecipeRow:
    """Tests for RecipeRow ORM model."""

    async def test_insert_and_fetch(self, db: DatabaseSession) -> None:
        """A RecipeRow can be inserted and fetched by primary key."""
        recipe = _make_recipe_core()
        row = RecipeRow(
            id=str(uuid.uuid4()),
            name=recipe.name,
            source=RecipeSource.MANUAL.value,
            source_id="",
            recipe_json=recipe.model_dump_json(),
            is_public=False,
            sort_index=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        async with db.get_session() as session:
            session.add(row)

        async with db.get_session() as session:
            fetched = await session.get(RecipeRow, row.id)
            assert fetched is not None
            assert fetched.name == "Test Recipe"
            assert fetched.source == "manual"

    async def test_recipe_json_roundtrip(self, db: DatabaseSession) -> None:
        """RecipeCore survives a serialise -> DB -> deserialise round-trip."""
        original = _make_recipe_core("Pasta")
        row = RecipeRow(
            id=str(uuid.uuid4()),
            name=original.name,
            source=RecipeSource.MANUAL.value,
            source_id="",
            recipe_json=original.model_dump_json(),
            is_public=False,
            sort_index=0,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        async with db.get_session() as session:
            session.add(row)

        async with db.get_session() as session:
            fetched = await session.get(RecipeRow, row.id)
            assert fetched is not None
            restored = RecipeCore.model_validate_json(fetched.recipe_json)

        assert restored.name == original.name
        assert len(restored.preparations) == len(original.preparations)
        ing_orig = original.preparations[0].ingredients[0]
        ing_rest = restored.preparations[0].ingredients[0]
        assert ing_rest.name == ing_orig.name
        assert ing_rest.quantity == ing_orig.quantity


class TestTagRow:
    """Tests for TagRow ORM model."""

    async def test_insert_and_fetch(self, db: DatabaseSession) -> None:
        """A TagRow can be inserted and fetched by name."""
        async with db.get_session() as session:
            session.add(TagRow(name="vegetarian", usefulness=5))

        async with db.get_session() as session:
            fetched = await session.get(TagRow, "vegetarian")
            assert fetched is not None
            assert fetched.usefulness == 5

    async def test_default_usefulness(self, db: DatabaseSession) -> None:
        """Usefulness defaults to 0."""
        async with db.get_session() as session:
            session.add(TagRow(name="quick"))

        async with db.get_session() as session:
            fetched = await session.get(TagRow, "quick")
            assert fetched is not None
            assert fetched.usefulness == 0


class TestAuthorRow:
    """Tests for AuthorRow ORM model."""

    async def test_insert_and_fetch(self, db: DatabaseSession) -> None:
        """An AuthorRow can be inserted and fetched."""
        async with db.get_session() as session:
            session.add(
                AuthorRow(
                    id=str(uuid.uuid4()),
                    username="chef_mario",
                    full_name="Mario Rossi",
                    biography="Italian chef.",
                    platform="instagram",
                    platform_id="12345",
                )
            )

        async with db.get_session() as session:
            result = await session.execute(
                select(AuthorRow).where(AuthorRow.username == "chef_mario")
            )
            author = result.scalar_one_or_none()
            assert author is not None
            assert author.full_name == "Mario Rossi"
            assert author.platform == "instagram"
