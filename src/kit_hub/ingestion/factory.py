"""Factory for assembling the ingestion service.

``build_ingest_service`` wires together ``media-downloader`` components and
the kit-hub LLM transcriber into a ready-to-use ``IngestService``.

The assembled pipeline registers ``InstaDownloader``, ``WebRecipeDownloader``,
and ``GenericWebScraper`` so that any supported URL (Instagram, known recipe
sites, or arbitrary web pages) can be ingested via a single entry point.

Example::

    params = get_kit_hub_params()
    db = DatabaseSession(params.db.to_config())
    crud = RecipeCRUDService()
    service = build_ingest_service(params, crud, db)
    recipe = await service.ingest_url("https://www.instagram.com/p/...")
    recipe = await service.ingest_url("https://example-blog.com/my-recipe")
"""

from media_downloader.core.providers.generic_web import GenericWebScraper
from media_downloader.core.providers.instagram import InstaDownloader
from media_downloader.core.providers.web_recipe import WebRecipeDownloader
from media_downloader.core.router import DownloadRouter
from media_downloader.storage.media_storage import MediaStorage

from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.ingestion.ingest_service import IngestService
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.params.kit_hub_params import KitHubParams


def build_ingest_service(
    kit_hub_params: KitHubParams,
    crud: RecipeCRUDService,
    db: DatabaseSession,
) -> IngestService:
    """Assemble an ``IngestService`` from kit-hub params.

    Creates a ``MediaStorage`` rooted at ``data/media/``, builds an
    ``InstaDownloader``, wraps it in a ``DownloadRouter``, and wires it
    together with a ``RecipeCoreTranscriber`` backed by the project LLM
    config.

    Args:
        kit_hub_params: Singleton params object providing paths and LLM
            configuration.
        crud: Stateless CRUD service for persisting recipes.
        db: Async database session manager.

    Returns:
        A fully configured ``IngestService`` ready for use.
    """
    media_base_dir = kit_hub_params.paths.data_fol / "media"
    storage = MediaStorage(base_dir=media_base_dir)
    insta_dl = InstaDownloader(storage=storage)
    web_recipe_dl = WebRecipeDownloader(storage=storage)
    generic_web_dl = GenericWebScraper(storage=storage)
    dl_router = DownloadRouter(
        downloaders=[insta_dl, web_recipe_dl, generic_web_dl],
    )

    llm_config = kit_hub_params.llm.to_config()
    transcriber = RecipeCoreTranscriber(llm_config)

    return IngestService(
        dl_router=dl_router,
        transcriber=transcriber,
        crud=crud,
        db=db,
    )
