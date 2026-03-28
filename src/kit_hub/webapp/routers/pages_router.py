"""HTML page routes.

Serves server-rendered Jinja2 templates for the browser UI.
"""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi import status
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi_tools.dependencies import get_current_user
from fastapi_tools.dependencies import get_optional_user
from fastapi_tools.schemas.auth import SessionData

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.webapp.core.dependencies import get_crud
from kit_hub.webapp.core.dependencies import get_db

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
) -> HTMLResponse:
    """Render the recipe browser page.

    Fetches the current user's recipes ordered by sort index and renders
    a paginated card grid.

    Args:
        request: Incoming request.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.
        page: Zero-based page number (default 0).
        page_size: Recipes per page (default 24).

    Returns:
        Recipe list page HTML.
    """
    async with db.get_session() as dbsession:
        rows = await crud.list_recipes(
            dbsession,
            user_id=user.user_id,
            limit=page_size + 1,
            offset=page * page_size,
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
) -> HTMLResponse:
    """Render the cook-soon queue page.

    Fetches all of the current user's recipes ordered by sort index for
    drag-and-drop priority management.

    Args:
        request: Incoming request.
        user: Authenticated user session.
        db: Database session manager.
        crud: Recipe CRUD service.

    Returns:
        Cook-soon queue page HTML.
    """
    async with db.get_session() as dbsession:
        recipes = await crud.list_recipes(
            dbsession,
            user_id=user.user_id,
            limit=200,
        )

    templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "pages/cook.html",
        {
            "user": user,
            "active_page": "cook",
            "recipes": recipes,
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
