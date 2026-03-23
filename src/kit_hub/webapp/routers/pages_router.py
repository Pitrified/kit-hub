"""HTML page routes.

Serves server-rendered Jinja2 templates for the browser UI.
"""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi_tools.dependencies import get_current_user
from fastapi_tools.dependencies import get_optional_user
from fastapi_tools.schemas.auth import SessionData

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
