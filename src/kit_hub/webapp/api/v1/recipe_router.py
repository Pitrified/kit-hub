"""Recipe CRUD and ingestion API router."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi_tools.dependencies import get_current_user
from fastapi_tools.schemas.auth import SessionData
from loguru import logger as lg
from sqlalchemy import desc
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.models import RecipeRow
from kit_hub.db.session import DatabaseSession
from kit_hub.ingestion.ingest_service import EmptyMediaTextError
from kit_hub.ingestion.ingest_service import IngestService
from kit_hub.llm.editor import RecipeCoreEditor
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.tag import RecipeTagAssignment
from kit_hub.webapp.api.schemas import RecipeCreateRequest
from kit_hub.webapp.api.schemas import RecipeDetailResponse
from kit_hub.webapp.api.schemas import RecipeEditRequest
from kit_hub.webapp.api.schemas import RecipeIngestRequest
from kit_hub.webapp.api.schemas import RecipeListItem
from kit_hub.webapp.api.schemas import RecipeListResponse
from kit_hub.webapp.api.schemas import RecipeSortRequest
from kit_hub.webapp.core.dependencies import get_crud
from kit_hub.webapp.core.dependencies import get_db
from kit_hub.webapp.core.dependencies import get_editor
from kit_hub.webapp.core.dependencies import get_ingest_service
from kit_hub.webapp.core.dependencies import get_transcriber

router = APIRouter(prefix="/recipes", tags=["recipes"])


def _row_to_detail(
    row: RecipeRow,
    tags: list[RecipeTagAssignment] | None = None,
) -> RecipeDetailResponse:
    """Build a ``RecipeDetailResponse`` from an ORM row.

    Args:
        row: Persisted recipe row. When ``tags`` is ``None``, ``row.tags``
            must already be eagerly loaded.
        tags: Pre-built tag list. Pass an empty list for newly created
            recipes that have no tags yet.

    Returns:
        Populated ``RecipeDetailResponse``.
    """
    resolved_tags: list[RecipeTagAssignment] = (
        tags
        if tags is not None
        else [
            RecipeTagAssignment(
                tag_name=t.tag_name,
                confidence=t.confidence,
                origin=t.origin,
            )
            for t in (row.tags or [])
        ]
    )
    return RecipeDetailResponse(
        id=row.id,
        recipe=RecipeCore.model_validate_json(row.recipe_json),
        source=row.source,
        source_id=row.source_id,
        is_public=row.is_public,
        sort_index=row.sort_index,
        created_at=row.created_at,
        updated_at=row.updated_at,
        tags=resolved_tags,
    )


async def _fetch_latest_row(db: DatabaseSession, user_id: str) -> RecipeRow | None:
    """Return the most recently created recipe row for a user.

    Includes eagerly loaded tags. Used after ingestion operations to
    retrieve the persisted row that the ingestion service created
    internally.

    Args:
        db: Active ``DatabaseSession``.
        user_id: Owner to filter by.

    Returns:
        Most recent ``RecipeRow`` for the user, or ``None`` if the user
        has no recipes.
    """
    async with db.get_session() as dbsession:
        stmt = (
            select(RecipeRow)
            .where(RecipeRow.user_id == user_id)
            .order_by(desc(RecipeRow.created_at))
            .limit(1)
            .options(selectinload(RecipeRow.tags))
        )
        result = await dbsession.execute(stmt)
        return result.scalars().first()


@router.get("/", summary="List recipes for the current user")
async def list_recipes(
    session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    page: int = 0,
    page_size: int = 20,
) -> RecipeListResponse:
    """Return a paginated list of recipe summaries ordered by sort index.

    Args:
        session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        page: Zero-based page number (default 0).
        page_size: Recipes per page (default 20).

    Returns:
        Paginated list of recipe summaries.
    """
    async with db.get_session() as dbsession:
        rows = await crud.list_recipes(
            dbsession,
            user_id=session.user_id,
            limit=page_size,
            offset=page * page_size,
        )
    items = [
        RecipeListItem(
            id=r.id,
            name=r.name,
            source=r.source,
            meal_course=r.meal_course,
            sort_index=r.sort_index,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return RecipeListResponse(
        recipes=items,
        total=len(items),
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    summary="Create recipe from free text",
    status_code=status.HTTP_201_CREATED,
)
async def create_recipe(
    body: RecipeCreateRequest,
    session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    transcriber: Annotated[RecipeCoreTranscriber, Depends(get_transcriber)],
) -> RecipeDetailResponse:
    """Parse free text into a structured recipe and persist it.

    Args:
        body: Text content and optional source type.
        session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        transcriber: LLM chain for text-to-recipe parsing.

    Returns:
        Full detail for the newly created recipe.
    """
    lg.info(f"Creating recipe from text ({body.source.value}), {len(body.text)} chars")
    recipe_core = await transcriber.ainvoke(body.text)
    async with db.get_session() as dbsession:
        row = await crud.create_recipe(
            dbsession,
            recipe=recipe_core,
            source=body.source,
            user_id=session.user_id,
        )
    lg.info(f"Created recipe '{recipe_core.name}' (id={row.id})")
    return _row_to_detail(row, tags=[])


@router.post(
    "/ingest",
    summary="Ingest recipe from Instagram URL",
    status_code=status.HTTP_201_CREATED,
)
async def ingest_recipe(
    body: RecipeIngestRequest,
    session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    ingest: Annotated[IngestService, Depends(get_ingest_service)],
) -> RecipeDetailResponse:
    """Download an Instagram post, parse it with the LLM, and persist the recipe.

    Args:
        body: Instagram post URL.
        session: Authenticated user session.
        db: Database session manager.
        ingest: Instagram ingestion pipeline.

    Returns:
        Full detail for the ingested recipe.

    Raises:
        HTTPException: 422 when the post has no usable text (no caption or
            transcript).
        HTTPException: 500 when the row cannot be retrieved after ingestion.
    """
    lg.info(f"Ingesting IG URL: {body.url}")
    try:
        await ingest.ingest_ig_url(url=body.url, user_id=session.user_id)
    except EmptyMediaTextError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    row = await _fetch_latest_row(db, session.user_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Recipe was ingested but could not be retrieved.",
        )
    lg.info(f"Ingested recipe '{row.name}' from {body.url}")
    return _row_to_detail(row)


@router.post("/sort", summary="Reorder the cook-soon queue")
async def sort_recipes(
    body: RecipeSortRequest,
    _session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> None:
    """Set a new sort order for the cook-soon queue.

    Args:
        body: Ordered list of recipe UUIDs defining the new priority.
        session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
    """
    lg.info(f"Reordering {len(body.recipe_ids)} recipes")
    async with db.get_session() as dbsession:
        await crud.reorder_recipes(dbsession, recipe_ids=body.recipe_ids)


@router.get("/{recipe_id}", summary="Get full recipe detail")
async def get_recipe(
    recipe_id: str,
    _session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> RecipeDetailResponse:
    """Return full detail for a single recipe, including tags.

    Args:
        recipe_id: UUID string identifying the recipe.
        _session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.

    Returns:
        Full recipe detail with eagerly loaded tags.

    Raises:
        HTTPException: 404 when the recipe does not exist.
    """
    async with db.get_session() as dbsession:
        row = await crud.get_recipe(dbsession, recipe_id=recipe_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )
    return _row_to_detail(row)


@router.put("/{recipe_id}", summary="Replace recipe content")
async def update_recipe(
    recipe_id: str,
    recipe: RecipeCore,
    _session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> RecipeDetailResponse:
    """Replace the full content of an existing recipe.

    Args:
        recipe_id: UUID string identifying the recipe.
        recipe: New ``RecipeCore`` content to persist.
        _session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.

    Returns:
        Updated recipe detail with eagerly loaded tags.

    Raises:
        HTTPException: 404 when the recipe does not exist.
    """
    try:
        async with db.get_session() as dbsession:
            await crud.update_recipe(dbsession, recipe_id=recipe_id, recipe=recipe)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        ) from exc
    async with db.get_session() as dbsession:
        row = await crud.get_recipe(dbsession, recipe_id=recipe_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )
    return _row_to_detail(row)


@router.delete(
    "/{recipe_id}",
    summary="Delete a recipe",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_recipe(
    recipe_id: str,
    _session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> None:
    """Permanently delete a recipe.

    Args:
        recipe_id: UUID string identifying the recipe.
        session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.

    Raises:
        HTTPException: 404 when the recipe does not exist.
    """
    try:
        async with db.get_session() as dbsession:
            await crud.delete_recipe(dbsession, recipe_id=recipe_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        ) from exc
    lg.info(f"Deleted recipe {recipe_id}")


@router.post("/{recipe_id}/edit", summary="Apply LLM-powered step correction")
async def edit_recipe(
    recipe_id: str,
    body: RecipeEditRequest,
    _session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    editor: Annotated[RecipeCoreEditor, Depends(get_editor)],
) -> RecipeDetailResponse:
    """Apply a natural-language correction to a step via the LLM editor.

    Args:
        recipe_id: UUID string identifying the recipe.
        body: Old step text and natural-language correction instructions.
        _session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        editor: LLM editor chain.

    Returns:
        Updated recipe detail after applying the correction.

    Raises:
        HTTPException: 404 when the recipe does not exist.
    """
    async with db.get_session() as dbsession:
        row = await crud.get_recipe(dbsession, recipe_id=recipe_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )
    old_recipe = RecipeCore.model_validate_json(row.recipe_json)
    lg.info(f"Editing step in recipe '{old_recipe.name}' ({recipe_id})")
    updated = await editor.ainvoke(
        old_recipe=old_recipe,
        old_step=body.old_step,
        new_step=body.new_step,
    )
    try:
        async with db.get_session() as dbsession:
            await crud.update_recipe(dbsession, recipe_id=recipe_id, recipe=updated)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        ) from exc
    async with db.get_session() as dbsession:
        row = await crud.get_recipe(dbsession, recipe_id=recipe_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        )
    return _row_to_detail(row)
