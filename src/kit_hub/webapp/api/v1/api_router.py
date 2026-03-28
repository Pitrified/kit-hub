"""API v1 main router aggregating all v1 routes."""

from typing import Annotated

from fastapi import APIRouter
from fastapi import Depends
from fastapi_tools.dependencies import get_current_user
from fastapi_tools.schemas.auth import SessionData
from fastapi_tools.schemas.common import MessageResponse

from kit_hub.webapp.api.v1.recipe_router import router as recipe_router
from kit_hub.webapp.api.v1.voice_router import router as voice_router

router = APIRouter(prefix="/api/v1", tags=["api-v1"])
router.include_router(recipe_router)
router.include_router(voice_router)


@router.get(
    "/",
    summary="API v1 root",
    description="Returns API version information.",
)
async def api_root() -> MessageResponse:
    """Return API v1 root information.

    Returns:
        MessageResponse with API info.
    """
    return MessageResponse(message="Kit Hub API v1")


@router.get(
    "/protected",
    summary="Protected endpoint example",
    description="Example of an endpoint that requires authentication.",
)
async def protected_endpoint(
    session: Annotated[SessionData, Depends(get_current_user)],
) -> MessageResponse:
    """Return a protected endpoint greeting.

    Args:
        session: Current user session (requires authentication).

    Returns:
        MessageResponse with personalized greeting.
    """
    return MessageResponse(message=f"Hello, {session.name}! You are authenticated.")


# To add more API routers as the application grows, import and include them here.
