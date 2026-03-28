"""Async CRUD service for recipes.

``RecipeCRUDService`` provides high-level async operations over the recipe
tables.  All methods accept an ``AsyncSession`` returned by
``DatabaseSession.get_session()`` so callers control transaction boundaries.

Usage example::

    async with db.get_session() as session:
        row = await crud.create_recipe(
            session,
            recipe=my_recipe_core,
            source=RecipeSource.MANUAL,
        )
"""

from datetime import UTC
from datetime import datetime
import uuid

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from kit_hub.db.models import RecipeRow
from kit_hub.db.models import RecipeTagRow
from kit_hub.db.models import TagRow
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.tag import RecipeTagAssignment


class RecipeCRUDService:
    """Async CRUD operations for recipes.

    All public methods take an ``AsyncSession`` as their first argument.
    This design keeps the service stateless - it holds no session state
    of its own and is therefore safe to share across concurrent requests.
    """

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_recipe(
        self,
        session: AsyncSession,
        recipe: RecipeCore,
        source: RecipeSource,
        source_id: str = "",
        user_id: str | None = None,
    ) -> RecipeRow:
        """Persist a new recipe and return the resulting row.

        The ``sort_index`` is set to ``max_existing + 1`` so new recipes
        are appended at the end of the queue.

        Args:
            session: Active database session.
            recipe: Structured recipe model to persist.
            source: Origin channel (IG, voice note, or manual).
            source_id: Platform-specific identifier (IG shortcode, etc.).
                Empty string for manual entries.
            user_id: Owner identifier.  ``None`` for anonymous recipes.

        Returns:
            RecipeRow: The newly created ORM row with all columns populated.
        """
        max_idx_result = await session.execute(
            select(func.coalesce(func.max(RecipeRow.sort_index), -1))
        )
        next_idx = max_idx_result.scalar_one() + 1
        row = RecipeRow(
            id=str(uuid.uuid4()),
            name=recipe.name,
            source=source.value,
            source_id=source_id,
            meal_course=recipe.meal_course.value if recipe.meal_course else None,
            recipe_json=recipe.model_dump_json(),
            user_id=user_id,
            is_public=False,
            sort_index=next_idx,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        session.add(row)
        await session.flush()
        await session.refresh(row)
        return row

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def get_recipe(
        self,
        session: AsyncSession,
        recipe_id: str,
    ) -> RecipeRow | None:
        """Fetch a recipe row by its UUID.

        Tags are eagerly loaded via a JOIN to avoid N+1 queries.

        Args:
            session: Active database session.
            recipe_id: UUID of the recipe to fetch.

        Returns:
            RecipeRow if found, ``None`` otherwise.
        """
        stmt = (
            select(RecipeRow)
            .where(RecipeRow.id == recipe_id)
            .options(selectinload(RecipeRow.tags))
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_recipe_core(
        self,
        session: AsyncSession,
        recipe_id: str,
    ) -> RecipeCore | None:
        """Fetch a recipe and deserialise its JSON into a ``RecipeCore``.

        Args:
            session: Active database session.
            recipe_id: UUID of the recipe to fetch.

        Returns:
            Deserialised ``RecipeCore`` if found, ``None`` otherwise.
        """
        row = await self.get_recipe(session, recipe_id)
        if row is None:
            return None
        return RecipeCore.model_validate_json(row.recipe_json)

    async def list_recipes(
        self,
        session: AsyncSession,
        user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RecipeRow]:
        """Return a paginated list of recipes ordered by ``sort_index``.

        Args:
            session: Active database session.
            user_id: When provided, filter to recipes owned by this user.
                When ``None``, return all recipes.
            limit: Maximum number of rows to return.
            offset: Number of rows to skip (for pagination).

        Returns:
            List of ``RecipeRow`` instances ordered by ``sort_index`` ascending.
        """
        stmt = (
            select(RecipeRow)
            .options(selectinload(RecipeRow.tags))
            .order_by(RecipeRow.sort_index)
            .limit(limit)
            .offset(offset)
        )
        if user_id is not None:
            stmt = stmt.where(RecipeRow.user_id == user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Update
    # ------------------------------------------------------------------

    async def update_recipe(
        self,
        session: AsyncSession,
        recipe_id: str,
        recipe: RecipeCore,
    ) -> RecipeRow:
        """Replace the stored ``RecipeCore`` JSON and sync metadata columns.

        Args:
            session: Active database session.
            recipe_id: UUID of the recipe to update.
            recipe: Updated recipe model.

        Returns:
            Updated ``RecipeRow``.

        Raises:
            KeyError: If no recipe with this ``recipe_id`` exists.
        """
        row = await self.get_recipe(session, recipe_id)
        if row is None:
            msg = f"Recipe not found: {recipe_id}"
            raise KeyError(msg)
        row.name = recipe.name
        row.meal_course = recipe.meal_course.value if recipe.meal_course else None
        row.recipe_json = recipe.model_dump_json()
        row.updated_at = datetime.now(UTC)
        await session.flush()
        await session.refresh(row)
        return row

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    async def delete_recipe(
        self,
        session: AsyncSession,
        recipe_id: str,
    ) -> None:
        """Delete a recipe and all its tag assignments.

        Uses cascade delete defined on the ORM relationship.

        Args:
            session: Active database session.
            recipe_id: UUID of the recipe to delete.

        Raises:
            KeyError: If no recipe with this ``recipe_id`` exists.
        """
        row = await self.get_recipe(session, recipe_id)
        if row is None:
            msg = f"Recipe not found: {recipe_id}"
            raise KeyError(msg)
        await session.delete(row)
        await session.flush()

    # ------------------------------------------------------------------
    # Reorder
    # ------------------------------------------------------------------

    async def reorder_recipes(
        self,
        session: AsyncSession,
        recipe_ids: list[str],
    ) -> None:
        """Set ``sort_index`` values from the given ordered list of IDs.

        The first ID in the list gets ``sort_index=0``, the second gets
        ``sort_index=1``, and so on.  IDs not present in the list are
        unchanged.

        Args:
            session: Active database session.
            recipe_ids: Ordered list of recipe UUIDs representing the
                desired cook-soon priority.
        """
        for idx, recipe_id in enumerate(recipe_ids):
            stmt = (
                update(RecipeRow)
                .where(RecipeRow.id == recipe_id)
                .values(sort_index=idx)
            )
            await session.execute(stmt)
        await session.flush()

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    async def add_tags(
        self,
        session: AsyncSession,
        recipe_id: str,
        tags: list[RecipeTagAssignment],
    ) -> None:
        """Attach tags to a recipe, upserting the global tag registry.

        For each ``RecipeTagAssignment``:
        1. Insert the ``TagRow`` if it does not already exist.
        2. Insert the ``RecipeTagRow`` link (skipped if already present).

        Args:
            session: Active database session.
            recipe_id: UUID of the recipe to tag.
            tags: List of tag assignments to apply.
        """
        for assignment in tags:
            # Upsert the tag into the global registry.
            existing_tag = await session.get(TagRow, assignment.tag_name)
            if existing_tag is None:
                session.add(TagRow(name=assignment.tag_name, usefulness=0))
                await session.flush()

            # Skip the link if it already exists.
            stmt = select(RecipeTagRow).where(
                RecipeTagRow.recipe_id == recipe_id,
                RecipeTagRow.tag_name == assignment.tag_name,
            )
            result = await session.execute(stmt)
            if result.scalar_one_or_none() is None:
                session.add(
                    RecipeTagRow(
                        recipe_id=recipe_id,
                        tag_name=assignment.tag_name,
                        confidence=assignment.confidence,
                        origin=assignment.origin,
                    )
                )
        await session.flush()
