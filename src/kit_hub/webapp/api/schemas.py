"""API request and response schemas for the kit-hub webapp."""

from datetime import datetime

from pydantic import BaseModel

from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.tag import RecipeTagAssignment


class RecipeCreateRequest(BaseModel):
    """Request body for creating a recipe from free text.

    Attributes:
        text: Raw recipe text to parse (Instagram caption, pasted text, etc.).
        source: Origin channel; defaults to ``MANUAL``.
    """

    text: str
    source: RecipeSource = RecipeSource.MANUAL


class RecipeIngestRequest(BaseModel):
    """Request body for ingesting a recipe from a URL.

    Supports Instagram posts, known recipe websites, and arbitrary
    web pages. The download pipeline auto-detects the source type.

    Attributes:
        url: Public URL to ingest (Instagram, recipe site, or web page).
    """

    url: str


class RecipeEditRequest(BaseModel):
    """Request body for applying an LLM-powered step correction.

    Attributes:
        old_step: Exact text of the step to correct.
        new_step: Natural-language description of the desired correction.
    """

    old_step: str
    new_step: str


class RecipeSortRequest(BaseModel):
    """Ordered list of recipe IDs defining the new cook-soon queue.

    Attributes:
        recipe_ids: Recipe UUIDs in the desired display order.
    """

    recipe_ids: list[str]


class RecipeListItem(BaseModel):
    """Compact recipe summary used in list and queue views.

    Attributes:
        id: Recipe UUID string.
        name: Recipe name.
        source: Origin channel (``instagram``, ``manual``, etc.).
        meal_course: Italian meal-course classification or ``None``.
        sort_index: Cook-soon queue position (lower = higher priority).
        created_at: UTC creation timestamp.
    """

    id: str
    name: str
    source: str
    meal_course: str | None
    sort_index: int
    created_at: datetime


class RecipeListResponse(BaseModel):
    """Paginated list of recipe summaries.

    Attributes:
        recipes: Recipe summaries for the requested page.
        total: Number of recipes returned in this page.
        page: Zero-based page index.
        page_size: Maximum number of recipes per page.
    """

    recipes: list[RecipeListItem]
    total: int
    page: int
    page_size: int


class RecipeDetailResponse(BaseModel):
    """Full recipe detail including structured content and tags.

    Attributes:
        id: Recipe UUID string.
        recipe: Structured ``RecipeCore`` Pydantic model.
        source: Origin channel string.
        source_id: Platform-specific identifier (IG shortcode or empty string).
        is_public: Whether the recipe is visible to all users.
        sort_index: Cook-soon queue position.
        created_at: UTC creation timestamp.
        updated_at: UTC last-update timestamp.
        tags: AI-assigned tags with confidence scores.
    """

    id: str
    recipe: RecipeCore
    source: str
    source_id: str
    is_public: bool
    sort_index: int
    created_at: datetime
    updated_at: datetime
    tags: list[RecipeTagAssignment]


class VoiceSessionCreateResponse(BaseModel):
    """Response body when a new voice recording session is created.

    Attributes:
        session_id: Unique session identifier for subsequent uploads.
    """

    session_id: str


class VoiceNoteResponse(BaseModel):
    """Response body after uploading a single audio clip.

    Attributes:
        text: Whisper-transcribed content of the clip.
        timestamp: ISO-8601 datetime string of when the note was recorded.
    """

    text: str
    timestamp: str
