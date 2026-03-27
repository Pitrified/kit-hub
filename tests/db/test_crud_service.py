"""Tests for RecipeCRUDService.

Covers the full CRUD lifecycle using an in-memory SQLite database.
All operations run through DatabaseSession so the session commit/rollback
logic is also exercised.
"""

import pytest

from kit_hub.config.db_config import DbConfig
from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_enums import MealCourse
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.tag import RecipeTagAssignment

_IN_MEMORY_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db() -> DatabaseSession:
    """Provide an initialised in-memory DatabaseSession."""
    config = DbConfig(db_url=_IN_MEMORY_URL)
    session = DatabaseSession(config)
    await session.init_db()
    return session


@pytest.fixture
def crud() -> RecipeCRUDService:
    """Provide a RecipeCRUDService instance."""
    return RecipeCRUDService()


def _make_recipe(name: str = "Pasta", course: MealCourse | None = None) -> RecipeCore:
    return RecipeCore(
        name=name,
        preparations=[
            Preparation(
                ingredients=[Ingredient(name="pasta", quantity="200g")],
                steps=[Step(instruction="Boil water.")],
            )
        ],
        source=RecipeSource.MANUAL,
        meal_course=course,
    )


class TestCreateRecipe:
    """Tests for RecipeCRUDService.create_recipe."""

    async def test_create_returns_row(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """create_recipe returns a RecipeRow with a populated id."""
        recipe = _make_recipe()
        async with db.get_session() as session:
            row = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
        assert row.id is not None
        assert row.name == "Pasta"
        assert row.source == "manual"

    async def test_create_with_source_id(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """source_id is stored correctly."""
        recipe = _make_recipe()
        async with db.get_session() as session:
            row = await crud.create_recipe(
                session, recipe, RecipeSource.INSTAGRAM, source_id="abc123"
            )
        assert row.source_id == "abc123"

    async def test_create_with_meal_course(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """meal_course is denormalised into the row."""
        recipe = _make_recipe(course=MealCourse.PRIMI)
        async with db.get_session() as session:
            row = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
        assert row.meal_course == "primi"

    async def test_create_with_user_id(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """user_id is stored when provided."""
        recipe = _make_recipe()
        async with db.get_session() as session:
            row = await crud.create_recipe(
                session, recipe, RecipeSource.MANUAL, user_id="user-abc"
            )
        assert row.user_id == "user-abc"


class TestGetRecipe:
    """Tests for RecipeCRUDService.get_recipe and get_recipe_core."""

    async def test_get_recipe_found(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """get_recipe returns the row for an existing id."""
        recipe = _make_recipe("Pizza")
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
        async with db.get_session() as session:
            fetched = await crud.get_recipe(session, created.id)
        assert fetched is not None
        assert fetched.name == "Pizza"

    async def test_get_recipe_not_found(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """get_recipe returns None for an unknown id."""
        async with db.get_session() as session:
            result = await crud.get_recipe(session, "nonexistent-id")
        assert result is None

    async def test_get_recipe_core_roundtrip(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """get_recipe_core deserialises RecipeCore faithfully."""
        recipe = _make_recipe("Risotto")
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
        async with db.get_session() as session:
            core = await crud.get_recipe_core(session, created.id)
        assert core is not None
        assert core.name == "Risotto"
        assert core.preparations[0].ingredients[0].name == "pasta"

    async def test_get_recipe_core_not_found(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """get_recipe_core returns None for an unknown id."""
        async with db.get_session() as session:
            result = await crud.get_recipe_core(session, "no-such-id")
        assert result is None


class TestListRecipes:
    """Tests for RecipeCRUDService.list_recipes."""

    async def test_list_all(self, db: DatabaseSession, crud: RecipeCRUDService) -> None:
        """list_recipes returns all recipes when user_id is None."""
        async with db.get_session() as session:
            await crud.create_recipe(session, _make_recipe("A"), RecipeSource.MANUAL)
            await crud.create_recipe(session, _make_recipe("B"), RecipeSource.MANUAL)
        async with db.get_session() as session:
            rows = await crud.list_recipes(session)
        assert len(rows) == 2

    async def test_list_filtered_by_user(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """list_recipes filters by user_id when provided."""
        async with db.get_session() as session:
            await crud.create_recipe(
                session, _make_recipe("Mine"), RecipeSource.MANUAL, user_id="u1"
            )
            await crud.create_recipe(
                session, _make_recipe("Theirs"), RecipeSource.MANUAL, user_id="u2"
            )
        async with db.get_session() as session:
            rows = await crud.list_recipes(session, user_id="u1")
        assert len(rows) == 1
        assert rows[0].name == "Mine"

    async def test_list_limit(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """Limit parameter caps the number of rows returned."""
        async with db.get_session() as session:
            for i in range(5):
                await crud.create_recipe(
                    session, _make_recipe(f"R{i}"), RecipeSource.MANUAL
                )
        async with db.get_session() as session:
            rows = await crud.list_recipes(session, limit=3)
        assert len(rows) == 3

    async def test_list_ordered_by_sort_index(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """list_recipes returns rows ordered by sort_index ascending."""
        async with db.get_session() as session:
            r1 = await crud.create_recipe(
                session, _make_recipe("First"), RecipeSource.MANUAL
            )
            r2 = await crud.create_recipe(
                session, _make_recipe("Second"), RecipeSource.MANUAL
            )
            await crud.reorder_recipes(session, [r2.id, r1.id])
        async with db.get_session() as session:
            rows = await crud.list_recipes(session)
        assert rows[0].name == "Second"
        assert rows[1].name == "First"


class TestUpdateRecipe:
    """Tests for RecipeCRUDService.update_recipe."""

    async def test_update_name(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """update_recipe overwrites the name and JSON."""
        recipe = _make_recipe("Old Name")
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)

        updated_recipe = _make_recipe("New Name")
        async with db.get_session() as session:
            updated = await crud.update_recipe(session, created.id, updated_recipe)
        assert updated.name == "New Name"

    async def test_update_not_found_raises(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """update_recipe raises KeyError for an unknown id."""
        async with db.get_session() as session:
            with pytest.raises(KeyError):
                await crud.update_recipe(session, "no-such-id", _make_recipe())

    async def test_update_json_persisted(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """Updated JSON is readable back via get_recipe_core."""
        recipe = _make_recipe("Old")
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)

        new_recipe = RecipeCore(
            name="New",
            preparations=[
                Preparation(
                    ingredients=[Ingredient(name="tomato", quantity="3")],
                    steps=[Step(instruction="Slice tomatoes.")],
                )
            ],
        )
        async with db.get_session() as session:
            await crud.update_recipe(session, created.id, new_recipe)

        async with db.get_session() as session:
            core = await crud.get_recipe_core(session, created.id)
        assert core is not None
        assert core.name == "New"
        assert core.preparations[0].ingredients[0].name == "tomato"


class TestDeleteRecipe:
    """Tests for RecipeCRUDService.delete_recipe."""

    async def test_delete_removes_row(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """delete_recipe removes the row from the database."""
        recipe = _make_recipe()
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)

        async with db.get_session() as session:
            await crud.delete_recipe(session, created.id)

        async with db.get_session() as session:
            result = await crud.get_recipe(session, created.id)
        assert result is None

    async def test_delete_not_found_raises(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """delete_recipe raises KeyError for an unknown id."""
        async with db.get_session() as session:
            with pytest.raises(KeyError):
                await crud.delete_recipe(session, "no-such-id")


class TestReorderRecipes:
    """Tests for RecipeCRUDService.reorder_recipes."""

    async def test_reorder_sets_sort_index(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """reorder_recipes assigns sort_index matching the list position."""
        async with db.get_session() as session:
            r1 = await crud.create_recipe(
                session, _make_recipe("Alpha"), RecipeSource.MANUAL
            )
            r2 = await crud.create_recipe(
                session, _make_recipe("Beta"), RecipeSource.MANUAL
            )
            r3 = await crud.create_recipe(
                session, _make_recipe("Gamma"), RecipeSource.MANUAL
            )
            await crud.reorder_recipes(session, [r3.id, r1.id, r2.id])

        async with db.get_session() as session:
            rows = await crud.list_recipes(session)

        names = [r.name for r in rows]
        assert names == ["Gamma", "Alpha", "Beta"]


class TestAddTags:
    """Tests for RecipeCRUDService.add_tags."""

    async def test_add_tags_creates_links(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """Add_tags creates TagRow and RecipeTagRow records."""
        recipe = _make_recipe()
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
            assignments = [
                RecipeTagAssignment(tag_name="quick", confidence=0.9, origin="ai"),
                RecipeTagAssignment(
                    tag_name="vegetarian", confidence=1.0, origin="manual"
                ),
            ]
            await crud.add_tags(session, created.id, assignments)

        async with db.get_session() as session:
            row = await crud.get_recipe(session, created.id)
        assert row is not None
        tag_names = {t.tag_name for t in row.tags}
        assert "quick" in tag_names
        assert "vegetarian" in tag_names

    async def test_add_tags_idempotent(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """Calling add_tags twice with the same tag does not duplicate."""
        recipe = _make_recipe()
        tag = [RecipeTagAssignment(tag_name="italian", confidence=1.0, origin="manual")]
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
            await crud.add_tags(session, created.id, tag)
            await crud.add_tags(session, created.id, tag)

        async with db.get_session() as session:
            row = await crud.get_recipe(session, created.id)
        assert row is not None
        italian_tags = [t for t in row.tags if t.tag_name == "italian"]
        assert len(italian_tags) == 1

    async def test_add_tags_confidence_origin(
        self, db: DatabaseSession, crud: RecipeCRUDService
    ) -> None:
        """Confidence and origin are stored correctly."""
        recipe = _make_recipe()
        async with db.get_session() as session:
            created = await crud.create_recipe(session, recipe, RecipeSource.MANUAL)
            await crud.add_tags(
                session,
                created.id,
                [RecipeTagAssignment(tag_name="spicy", confidence=0.75, origin="ai")],
            )

        async with db.get_session() as session:
            row = await crud.get_recipe(session, created.id)
        assert row is not None
        spicy = next(t for t in row.tags if t.tag_name == "spicy")
        assert abs(spicy.confidence - 0.75) < 1e-6
        assert spicy.origin == "ai"
