# Block 4: Instagram ingestion

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md), [03-db-layer.md](03-db-layer.md), [04-llm-chains.md](04-llm-chains.md)

## Goal

Wire `media-downloader`'s `InstaDownloader` + `TranscriptionHook` into a kit-hub ingestion service. The pipeline: accept IG URL -> download post -> transcribe video (if present) -> combine caption + transcript -> LLM parse -> persist to DB.

## Source material

- `recipamatic`: working end-to-end IG ingestion with `instaloader`, language detection, LLM parsing
- `media-downloader`: `InstaDownloader`, `DownloadRouter`, `TranscriptionHook`, `DownloadedMedia`
- `media-downloader`: `DownloadDBService` + `run_worker` for async job processing

## Design

The ingestion service orchestrates `media-downloader` components:

```
URL -> DownloadRouter.adownload() -> DownloadedMedia
  -> combine caption + transcription
  -> RecipeCoreTranscriber.ainvoke()
  -> RecipeCRUDService.create_recipe()
```

The `DownloadRouter` is configured with an `InstaDownloader` and a `TranscriptionHook` post-processor, so download + transcription happen in one call.

For the Telegram bot flow, ingestion is called directly (not queued) since bot messages are already async. For the webapp flow, ingestion is submitted as a background job.

## Deliverables

### 1. Ingestion service - `src/kit_hub/ingestion/ingest_service.py`

```python
class IngestService:
    """Orchestrate IG download -> transcribe -> LLM parse -> DB save."""

    def __init__(
        self,
        dl_router: DownloadRouter,
        transcriber: RecipeCoreTranscriber,
        crud: RecipeCRUDService,
    ): ...

    async def ingest_ig_url(
        self, url: str, user_id: str | None = None,
    ) -> RecipeCore:
        """Full pipeline: download IG post, transcribe, parse, persist."""
        # 1. dl_router.adownload(url) -> DownloadedMedia
        # 2. Combine media.caption + media.transcript (if available)
        # 3. transcriber.ainvoke(combined_text) -> RecipeCore
        # 4. crud.create_recipe(recipe, source=INSTAGRAM, source_id=media.source_id)
        # 5. Return RecipeCore

    async def ingest_text(
        self, text: str, source: RecipeSource = RecipeSource.MANUAL,
        user_id: str | None = None,
    ) -> RecipeCore:
        """Parse free text into a recipe and persist."""
        # 1. transcriber.ainvoke(text) -> RecipeCore
        # 2. crud.create_recipe(recipe, source=source)
        # 3. Return RecipeCore
```

### 2. Ingestion factory - `src/kit_hub/ingestion/factory.py`

```python
def build_ingest_service(
    kit_hub_params: KitHubParams,
    crud: RecipeCRUDService,
) -> IngestService:
    """Wire up all components for the ingestion pipeline."""
    # 1. Build MediaStorage from kit_hub_params.paths
    # 2. Build InstaDownloader(storage)
    # 3. Build TranscriptionHook (Whisper via media-downloader)
    # 4. Build DownloadRouter([insta_dl], post_processors=[transcription_hook])
    # 5. Build RecipeCoreTranscriber from kit_hub_params.llm
    # 6. Return IngestService(dl_router, transcriber, crud)
```

### 3. Cache management - `src/kit_hub/ingestion/cache_manager.py`

```python
class CacheManager:
    """Manage cached IG post data in data/ig/."""

    def __init__(self, ig_cache_dir: Path): ...

    def has_post(self, shortcode: str) -> bool: ...
    def get_cached_media(self, shortcode: str) -> DownloadedMedia | None: ...
    def clear_old_cache(self, max_age_days: int = 30) -> int: ...
```

## Tasks

- [ ] Create `src/kit_hub/ingestion/` package
- [ ] Implement `ingest_service.py` with `ingest_ig_url` and `ingest_text`
- [ ] Implement `factory.py` to wire up components
- [ ] Implement `cache_manager.py` for IG post deduplication
- [ ] Write tests with mocked `DownloadRouter` and `RecipeCoreTranscriber`
- [ ] Write integration test: mock download -> real transcriber call flow
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
