"""Ingestion service - orchestrates download, parsing, and storage.

``IngestService`` is the main entry point for adding recipes from external
sources. It wires together the download router, LLM transcriber, and CRUD
service into a single async pipeline.

Pipeline for Instagram URLs::

    URL -> DownloadRouter.adownload() -> DownloadedMedia
        -> combine caption + transcript
        -> RecipeCoreTranscriber.ainvoke()
        -> RecipeCRUDService.create_recipe()
        -> RecipeCore

Pipeline for plain text::

    text -> RecipeCoreTranscriber.ainvoke()
         -> RecipeCRUDService.create_recipe()
         -> RecipeCore
"""

from loguru import logger as lg
from media_downloader.core.models import DownloadedMedia
from media_downloader.core.router import DownloadRouter

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_enums import RecipeSource


class EmptyMediaTextError(ValueError):
    """Raised when a downloaded media item has no caption or transcript."""

    def __init__(self, url: str) -> None:
        """Initialise with the offending URL.

        Args:
            url: The source URL that produced no usable text.
        """
        self.url = url
        msg = f"No caption or transcript found for URL: {url}"
        super().__init__(msg)


class IngestService:
    """Orchestrate IG download -> transcribe -> LLM parse -> DB persist.

    All public methods are async and should be called from an async context
    (e.g. a Telegram handler or a FastAPI background task).

    Attributes:
        _dl_router:
            Pre-configured ``DownloadRouter`` for fetching media.
        _transcriber:
            ``RecipeCoreTranscriber`` that converts text to a structured recipe.
        _crud:
            Stateless CRUD service for persisting recipes.
        _db:
            ``DatabaseSession`` used to open async sessions.
    """

    def __init__(
        self,
        dl_router: DownloadRouter,
        transcriber: RecipeCoreTranscriber,
        crud: RecipeCRUDService,
        db: DatabaseSession,
    ) -> None:
        """Initialise the ingestion service.

        Args:
            dl_router: Configured download router with Instagram (and
                optionally other) providers.
            transcriber: LLM chain that converts free text to a
                structured ``RecipeCore``.
            crud: Async CRUD service for recipe persistence.
            db: Database session manager.
        """
        self._dl_router = dl_router
        self._transcriber = transcriber
        self._crud = crud
        self._db = db

    async def ingest_ig_url(
        self,
        url: str,
        user_id: str | None = None,
    ) -> RecipeCore:
        """Download an Instagram post, parse it, and persist the recipe.

        Args:
            url: Public Instagram post URL.
            user_id: Optional owner identifier for the resulting recipe.

        Returns:
            The parsed and persisted ``RecipeCore``.

        Raises:
            EmptyMediaTextError: If the downloaded post has neither a
                caption nor a transcription to parse.
        """
        lg.info(f"Ingesting IG URL: {url}")
        media = await self._dl_router.adownload(url)
        text = self._build_text(media)
        if not text:
            raise EmptyMediaTextError(url)
        recipe = await self._transcriber.ainvoke(text)
        async with self._db.get_session() as session:
            await self._crud.create_recipe(
                session,
                recipe,
                source=RecipeSource.INSTAGRAM,
                source_id=media.source_id,
                user_id=user_id,
            )
        lg.info(f"Ingested recipe '{recipe.name}' from {url}")
        return recipe

    async def ingest_text(
        self,
        text: str,
        source: RecipeSource = RecipeSource.MANUAL,
        user_id: str | None = None,
    ) -> RecipeCore:
        """Parse free text into a recipe and persist it.

        Args:
            text: Raw recipe text (Instagram caption, voice transcript,
                or manually pasted text).
            source: Origin channel for the recipe.
            user_id: Optional owner identifier.

        Returns:
            The parsed and persisted ``RecipeCore``.
        """
        lg.info(f"Ingesting text ({source.value}), {len(text)} chars")
        recipe = await self._transcriber.ainvoke(text)
        async with self._db.get_session() as session:
            await self._crud.create_recipe(
                session,
                recipe,
                source=source,
                user_id=user_id,
            )
        lg.info(f"Ingested recipe '{recipe.name}' from {source.value}")
        return recipe

    @staticmethod
    def _build_text(media: DownloadedMedia) -> str:
        """Combine caption and transcript from a downloaded media item.

        Args:
            media: The downloaded media to extract text from.

        Returns:
            Combined text string, or an empty string if neither
            caption nor transcript is available.
        """
        parts: list[str] = []
        if media.caption:
            parts.append(media.caption)
        if media.transcript:
            parts.append(media.transcript)
        return "\n\n".join(parts)
