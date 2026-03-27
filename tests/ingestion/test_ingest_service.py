"""Tests for IngestService.

Uses an in-memory SQLite database for the CRUD layer and mocks for the
download router and LLM transcriber, so no external services are called.
"""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from media_downloader.core.models import DownloadedMedia
from media_downloader.core.models import SourceType
import pytest

from kit_hub.config.db_config import DbConfig
from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.ingestion.ingest_service import EmptyMediaTextError
from kit_hub.ingestion.ingest_service import IngestService
from kit_hub.llm.transcriber import RecipeCoreTranscriber
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


@pytest.fixture
def crud() -> RecipeCRUDService:
    """Provide a RecipeCRUDService instance."""
    return RecipeCRUDService()


@pytest.fixture
def fake_recipe() -> RecipeCore:
    """Return a minimal valid RecipeCore."""
    return RecipeCore(
        name="Pasta al Pomodoro",
        preparations=[
            Preparation(
                ingredients=[Ingredient(name="pasta", quantity="200g")],
                steps=[Step(instruction="Boil pasta for 10 minutes.")],
            )
        ],
    )


@pytest.fixture
def fake_media() -> DownloadedMedia:
    """Return a DownloadedMedia stub with a caption and no transcription."""
    return DownloadedMedia(
        source=SourceType.INSTAGRAM,
        source_id="CaB3d4eF",
        original_url="https://www.instagram.com/p/CaB3d4eF/",
        caption="Great pasta recipe! Use 200g pasta.",
    )


def _make_service(
    db: DatabaseSession,
    crud: RecipeCRUDService,
    fake_recipe: RecipeCore,
    media: DownloadedMedia | None = None,
) -> IngestService:
    """Build an IngestService with mocked download router and transcriber."""
    dl_router = MagicMock()
    dl_router.adownload = AsyncMock(return_value=media)

    transcriber = MagicMock(spec=RecipeCoreTranscriber)
    transcriber.ainvoke = AsyncMock(return_value=fake_recipe)

    return IngestService(
        dl_router=dl_router,
        transcriber=transcriber,
        crud=crud,
        db=db,
    )


class TestIngestIgUrl:
    """Tests for IngestService.ingest_ig_url."""

    async def test_returns_recipe_core(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
        fake_media: DownloadedMedia,
    ) -> None:
        """ingest_ig_url returns the parsed RecipeCore."""
        service = _make_service(db, crud, fake_recipe, fake_media)
        result = await service.ingest_ig_url(fake_media.original_url)
        assert isinstance(result, RecipeCore)
        assert result.name == "Pasta al Pomodoro"

    async def test_persists_recipe_to_db(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
        fake_media: DownloadedMedia,
    ) -> None:
        """ingest_ig_url persists with INSTAGRAM source and the correct source_id."""
        service = _make_service(db, crud, fake_recipe, fake_media)
        await service.ingest_ig_url(fake_media.original_url)

        async with db.get_session() as session:
            rows = await crud.list_recipes(session)

        assert len(rows) == 1
        assert rows[0].source == "instagram"
        assert rows[0].source_id == "CaB3d4eF"

    async def test_persists_with_user_id(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
        fake_media: DownloadedMedia,
    ) -> None:
        """ingest_ig_url stores the user_id on the created row."""
        service = _make_service(db, crud, fake_recipe, fake_media)
        await service.ingest_ig_url(fake_media.original_url, user_id="user-42")

        async with db.get_session() as session:
            rows = await crud.list_recipes(session)

        assert rows[0].user_id == "user-42"

    async def test_raises_on_empty_media(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
    ) -> None:
        """ingest_ig_url raises EmptyMediaTextError when there is no text."""
        empty_media = DownloadedMedia(
            source=SourceType.INSTAGRAM,
            source_id="empty123",
            original_url="https://www.instagram.com/p/empty123/",
            caption="",
        )
        service = _make_service(db, crud, fake_recipe, empty_media)

        with pytest.raises(EmptyMediaTextError):
            await service.ingest_ig_url(empty_media.original_url)

    async def test_calls_download_router(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
        fake_media: DownloadedMedia,
    ) -> None:
        """ingest_ig_url delegates to the download router."""
        dl_router = MagicMock()
        dl_router.adownload = AsyncMock(return_value=fake_media)
        transcriber = MagicMock(spec=RecipeCoreTranscriber)
        transcriber.ainvoke = AsyncMock(return_value=fake_recipe)
        service = IngestService(
            dl_router=dl_router, transcriber=transcriber, crud=crud, db=db
        )
        await service.ingest_ig_url(fake_media.original_url)
        dl_router.adownload.assert_called_once_with(fake_media.original_url)


class TestIngestText:
    """Tests for IngestService.ingest_text."""

    async def test_returns_recipe_core(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
    ) -> None:
        """ingest_text returns the parsed RecipeCore."""
        service = _make_service(db, crud, fake_recipe)
        result = await service.ingest_text("Mix flour and water.")
        assert isinstance(result, RecipeCore)
        assert result.name == "Pasta al Pomodoro"

    async def test_persists_with_manual_source(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
    ) -> None:
        """ingest_text defaults to MANUAL source."""
        service = _make_service(db, crud, fake_recipe)
        await service.ingest_text("Mix flour and water.")

        async with db.get_session() as session:
            rows = await crud.list_recipes(session)

        assert rows[0].source == "manual"
        assert rows[0].source_id == ""

    async def test_persists_with_custom_source(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
    ) -> None:
        """ingest_text stores the provided source enum value."""
        service = _make_service(db, crud, fake_recipe)
        await service.ingest_text("some note", source=RecipeSource.VOICE_NOTE)

        async with db.get_session() as session:
            rows = await crud.list_recipes(session)

        assert rows[0].source == "voice_note"

    async def test_calls_transcriber(
        self,
        db: DatabaseSession,
        crud: RecipeCRUDService,
        fake_recipe: RecipeCore,
    ) -> None:
        """ingest_text delegates to the transcriber with the provided text."""
        dl_router = MagicMock()
        transcriber = MagicMock(spec=RecipeCoreTranscriber)
        transcriber.ainvoke = AsyncMock(return_value=fake_recipe)
        service = IngestService(
            dl_router=dl_router, transcriber=transcriber, crud=crud, db=db
        )
        await service.ingest_text("boil pasta")
        transcriber.ainvoke.assert_called_once_with("boil pasta")


class TestBuildText:
    """Tests for IngestService._build_text."""

    def test_caption_only(self) -> None:
        """Returns caption when no transcription is present."""
        media = DownloadedMedia(
            source=SourceType.INSTAGRAM,
            source_id="x",
            original_url="https://example.com",
            caption="Caption text.",
        )
        result = IngestService._build_text(media)  # noqa: SLF001
        assert result == "Caption text."

    def test_transcript_only(self) -> None:
        """Returns transcript when caption is empty."""
        transcription = MagicMock()
        transcription.text = "Transcript text."
        transcription.language = "it"

        media = DownloadedMedia(
            source=SourceType.INSTAGRAM,
            source_id="x",
            original_url="https://example.com",
            caption="",
            transcription=transcription,
        )
        result = IngestService._build_text(media)  # noqa: SLF001
        assert result == "Transcript text."

    def test_caption_and_transcript_combined(self) -> None:
        """Returns caption and transcript joined by a blank line."""
        transcription = MagicMock()
        transcription.text = "Transcript text."
        transcription.language = "it"

        media = DownloadedMedia(
            source=SourceType.INSTAGRAM,
            source_id="x",
            original_url="https://example.com",
            caption="Caption text.",
            transcription=transcription,
        )
        result = IngestService._build_text(media)  # noqa: SLF001
        assert result == "Caption text.\n\nTranscript text."

    def test_empty_when_no_content(self) -> None:
        """Returns empty string when both caption and transcript are empty."""
        media = DownloadedMedia(
            source=SourceType.INSTAGRAM,
            source_id="x",
            original_url="https://example.com",
            caption="",
        )
        result = IngestService._build_text(media)  # noqa: SLF001
        assert result == ""
