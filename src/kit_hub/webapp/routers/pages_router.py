"""HTML page routes.

Serves server-rendered Jinja2 templates for the browser UI.
"""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import Response
from fastapi import status
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi_tools.dependencies import get_current_user
from fastapi_tools.dependencies import get_optional_user
from fastapi_tools.schemas.auth import SessionData

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.llm.editor import RecipeCoreEditor
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_enums import MealCourse
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.webapp.api.schemas import RecipeEditRequest
from kit_hub.webapp.core.dependencies import get_crud
from kit_hub.webapp.core.dependencies import get_db
from kit_hub.webapp.core.dependencies import get_editor

# Map OAuth error codes to user-friendly messages
_ERROR_MESSAGES: dict[str, str] = {
    "access_denied": "Access was denied. Please try again.",
    "auth_failed": "Authentication failed. Please try again.",
    "invalid_state": "Session expired. Please try again.",
}

router = APIRouter(tags=["pages"])


@router.get(
    "/",
    response_model=None,
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def landing(
    request: Request,
    user: Annotated[SessionData | None, Depends(get_optional_user)],
    error: Annotated[str | None, Query()] = None,
) -> HTMLResponse | RedirectResponse:
    """Render public landing page or redirect authenticated users.

    Args:
        request: Incoming request.
        user: Current user session, if any.
        error: OAuth error code from callback redirect.

    Returns:
        Landing page HTML or redirect to dashboard.
    """
    if user is not None:
        return RedirectResponse(url="/dashboard", status_code=302)

    flash = None
    if error:
        flash = {
            "type": "danger",
            "message": _ERROR_MESSAGES.get(error, f"An error occurred: {error}"),
        }

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/landing.html",
        {"user": None, "flash": flash, "active_page": "landing"},
    )


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
) -> HTMLResponse:
    """Render authenticated dashboard.

    Args:
        request: Incoming request.
        user: Authenticated user session.

    Returns:
        Dashboard page HTML.
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/dashboard.html",
        {"user": user, "active_page": "dashboard"},
    )


@router.get(
    "/pages/partials/user-card",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def user_card_partial(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
) -> HTMLResponse:
    """Return user card HTML fragment for HTMX swap.

    Args:
        request: Incoming request.
        user: Authenticated user session.

    Returns:
        User card partial HTML (no base layout).
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/user_card.html",
        {"user": user},
    )


@router.get(
    "/pages/partials/recipe-grid",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def recipe_grid_partial(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    source: str = "",
    meal_course: str = "",
    search: str = "",
) -> HTMLResponse:
    """Return filtered recipe card grid HTML fragment for HTMX swap.

    Args:
        request: Incoming request.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        source: Filter by recipe origin channel.
        meal_course: Filter by meal course category.
        search: Case-insensitive substring match on recipe name.

    Returns:
        Recipe grid partial HTML (no base layout).
    """
    source_enum = RecipeSource(source) if source else None
    course_enum = MealCourse(meal_course) if meal_course else None
    search_val = search or None

    async with db.get_session() as dbsession:
        recipes = await crud.list_recipes(
            dbsession,
            user_id=user.user_id,
            limit=24,
            source=source_enum,
            meal_course=course_enum,
            search=search_val,
        )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/recipe_grid.html",
        {"recipes": recipes},
    )


@router.get(
    "/pages/partials/cook-table",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def cook_table_partial(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    source: str = "",
    meal_course: str = "",
    search: str = "",
) -> HTMLResponse:
    """Return filtered cook queue table body HTML fragment for HTMX swap.

    Args:
        request: Incoming request.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        source: Filter by recipe origin channel.
        meal_course: Filter by meal course category.
        search: Case-insensitive substring match on recipe name.

    Returns:
        Cook table body partial HTML (no base layout).
    """
    source_enum = RecipeSource(source) if source else None
    course_enum = MealCourse(meal_course) if meal_course else None
    search_val = search or None

    async with db.get_session() as dbsession:
        recipes = await crud.list_recipes(
            dbsession,
            user_id=user.user_id,
            limit=200,
            source=source_enum,
            meal_course=course_enum,
            search=search_val,
        )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/cook_table.html",
        {"recipes": recipes},
    )


@router.get(
    "/error/{status_code}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def error_page(
    request: Request,
    status_code: int,
    user: Annotated[SessionData | None, Depends(get_optional_user)],
) -> HTMLResponse:
    """Render a generic error page.

    Args:
        request: Incoming request.
        status_code: HTTP status code to display.
        user: Current user session, if any.

    Returns:
        Error page HTML.
    """
    messages: dict[int, str] = {
        400: "Bad request.",
        401: "You need to log in to access this page.",
        403: "You don't have permission to view this page.",
        404: "The page you're looking for doesn't exist.",
        500: "Something went wrong on our end.",
    }
    message = messages.get(status_code, "An unexpected error occurred.")

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/error.html",
        {
            "user": user,
            "status_code": status_code,
            "message": message,
        },
        status_code=status_code,
    )


# ---------------------------------------------------------------------------
# Recipe pages
# ---------------------------------------------------------------------------


@router.get("/recipes", response_class=HTMLResponse, include_in_schema=False)
async def recipes_list(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    page: int = 0,
    page_size: int = 24,
    source: str = "",
    meal_course: str = "",
    search: str = "",
) -> HTMLResponse:
    """Render the recipe browser page.

    Fetches the current user's recipes ordered by sort index and renders
    a paginated card grid. Supports filtering by source, meal course, and
    text search on recipe name.

    Args:
        request: Incoming request.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        page: Zero-based page number (default 0).
        page_size: Recipes per page (default 24).
        source: Filter by recipe origin channel.
        meal_course: Filter by meal course category.
        search: Case-insensitive substring match on recipe name.

    Returns:
        Recipe list page HTML.
    """
    source_enum = RecipeSource(source) if source else None
    course_enum = MealCourse(meal_course) if meal_course else None
    search_val = search or None

    async with db.get_session() as dbsession:
        rows = await crud.list_recipes(
            dbsession,
            user_id=user.user_id,
            limit=page_size + 1,
            offset=page * page_size,
            source=source_enum,
            meal_course=course_enum,
            search=search_val,
        )
    has_next = len(rows) > page_size
    recipes = rows[:page_size]

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/recipes.html",
        {
            "user": user,
            "active_page": "recipes",
            "recipes": recipes,
            "page": page,
            "page_size": page_size,
            "has_next": has_next,
            "has_prev": page > 0,
            "source": source,
            "meal_course": meal_course,
            "search": search,
            "sources": [s.value for s in RecipeSource],
            "meal_courses": [m.value for m in MealCourse],
        },
    )


@router.get(
    "/recipes/{recipe_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def recipe_detail(
    request: Request,
    recipe_id: str,
    user: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> HTMLResponse:
    """Render the recipe detail page.

    Args:
        request: Incoming request.
        recipe_id: UUID string of the recipe to display.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.

    Returns:
        Recipe detail page HTML.

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
    recipe_core = RecipeCore.model_validate_json(row.recipe_json)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/recipe_detail.html",
        {
            "user": user,
            "active_page": "recipes",
            "row": row,
            "recipe": recipe_core,
            "original_url": row.original_url,
            "raw_input_text": row.raw_input_text,
        },
    )


# ---------------------------------------------------------------------------
# Cook-soon queue page
# ---------------------------------------------------------------------------


@router.get("/cook", response_class=HTMLResponse, include_in_schema=False)
async def cook_queue(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    source: str = "",
    meal_course: str = "",
    search: str = "",
) -> HTMLResponse:
    """Render the cook-soon queue page.

    Fetches all of the current user's recipes ordered by sort index for
    drag-and-drop priority management. Supports filtering by source,
    meal course, and text search.

    Args:
        request: Incoming request.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        source: Filter by recipe origin channel.
        meal_course: Filter by meal course category.
        search: Case-insensitive substring match on recipe name.

    Returns:
        Cook-soon queue page HTML.
    """
    source_enum = RecipeSource(source) if source else None
    course_enum = MealCourse(meal_course) if meal_course else None
    search_val = search or None

    async with db.get_session() as dbsession:
        recipes = await crud.list_recipes(
            dbsession,
            user_id=user.user_id,
            limit=200,
            source=source_enum,
            meal_course=course_enum,
            search=search_val,
        )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/cook.html",
        {
            "user": user,
            "active_page": "cook",
            "recipes": recipes,
            "source": source,
            "meal_course": meal_course,
            "search": search,
            "sources": [s.value for s in RecipeSource],
            "meal_courses": [m.value for m in MealCourse],
        },
    )


# ---------------------------------------------------------------------------
# Voice note page
# ---------------------------------------------------------------------------


@router.get("/voice", response_class=HTMLResponse, include_in_schema=False)
async def voice_notes(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
) -> HTMLResponse:
    """Render the voice note recording page.

    Args:
        request: Incoming request.
        user: Authenticated user session.

    Returns:
        Voice note page HTML.
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/voice.html",
        {
            "user": user,
            "active_page": "voice",
        },
    )


# ---------------------------------------------------------------------------
# HTMX partials
# ---------------------------------------------------------------------------


@router.get(
    "/pages/partials/add-recipe-form",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def add_recipe_form_partial(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
) -> HTMLResponse:
    """Return the paste-text recipe form HTML fragment for HTMX swap.

    Args:
        request: Incoming request.
        user: Authenticated user session.

    Returns:
        Add-recipe form partial HTML (no base layout).
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/add_recipe_form.html",
        {"user": user},
    )


@router.get(
    "/pages/partials/ingest-recipe-form",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def ingest_recipe_form_partial(
    request: Request,
    user: Annotated[SessionData, Depends(get_current_user)],
) -> HTMLResponse:
    """Return the Instagram ingest form HTML fragment for HTMX swap.

    Args:
        request: Incoming request.
        user: Authenticated user session.

    Returns:
        Ingest-recipe form partial HTML (no base layout).
    """
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/ingest_recipe_form.html",
        {"user": user},
    )


@router.get(
    "/pages/partials/edit-recipe-form/{recipe_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
async def edit_recipe_form_partial(
    request: Request,
    recipe_id: str,
    user: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
) -> HTMLResponse:
    """Return the edit-step form HTML fragment for HTMX swap.

    Args:
        request: Incoming request.
        recipe_id: UUID string of the recipe to edit.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.

    Returns:
        Edit-recipe form partial HTML (no base layout).

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
    recipe_core = RecipeCore.model_validate_json(row.recipe_json)

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "partials/edit_recipe_form.html",
        {"user": user, "row": row, "recipe": recipe_core},
    )


@router.post(
    "/pages/recipes/{recipe_id}/edit",
    response_model=None,
    include_in_schema=False,
)
async def edit_recipe_page(
    recipe_id: str,
    body: RecipeEditRequest,
    _session: Annotated[SessionData, Depends(get_current_user)],
    db: Annotated[DatabaseSession, Depends(get_db)],
    crud: Annotated[RecipeCRUDService, Depends(get_crud)],
    editor: Annotated[RecipeCoreEditor, Depends(get_editor)],
) -> Response:
    """Apply an LLM-powered step correction and redirect to the detail page.

    Args:
        recipe_id: UUID string of the recipe to edit.
        body: Old step text and natural-language correction instructions.
        _session: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        editor: LLM editor chain.

    Returns:
        HX-Redirect response to the refreshed recipe detail page.

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
    updated = await editor.ainvoke(
        old_recipe=old_recipe,
        old_step=body.old_step,
        new_step=body.new_step,
    )
    try:
        async with db.get_session() as dbsession:
            await crud.update_recipe(
                dbsession,
                recipe_id=recipe_id,
                recipe=updated,
            )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found.",
        ) from exc

    return Response(
        status_code=200,
        headers={"HX-Redirect": f"/recipes/{recipe_id}"},
    )
