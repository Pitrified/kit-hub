# Ingestion layer

The ingestion layer converts external recipe sources - Instagram posts and plain
text - into structured `RecipeCore` objects and persists them to the database.

## Pipeline

For Instagram URLs the flow is:

```
URL
  -> DownloadRouter.adownload()   # fetch post via InstaDownloader
  -> DownloadedMedia              # caption + optional transcription
  -> IngestService._build_text()  # combine caption and transcript
  -> RecipeCoreTranscriber.ainvoke()
  -> RecipeCore
  -> RecipeCRUDService.create_recipe()  # persist with source=INSTAGRAM
```

For plain text (manual paste or voice transcript):

```
text
  -> RecipeCoreTranscriber.ainvoke()
  -> RecipeCore
  -> RecipeCRUDService.create_recipe()  # persist with given source
```

## Components

### `IngestService`

Central orchestrator in `src/kit_hub/ingestion/ingest_service.py`. Accepts a
pre-built `DownloadRouter`, a `RecipeCoreTranscriber`, a `RecipeCRUDService`,
and a `DatabaseSession`. All public methods are async.

Key methods:

- `ingest_ig_url(url, user_id=None)` - full IG pipeline; raises
  `EmptyMediaTextError` when the post has neither a caption nor a transcript.
- `ingest_text(text, source=MANUAL, user_id=None)` - parse and persist free text.

### `CacheManager`

Utility in `src/kit_hub/ingestion/cache_manager.py` for checking whether a given
Instagram shortcode has already been downloaded. Files are organised as
`{ig_cache_dir}/{shortcode}/`, mirroring the layout that `MediaStorage` produces
for `SourceType.INSTAGRAM`.

Key methods:

- `has_post(shortcode)` - True when a non-empty directory exists for the shortcode.
- `get_cached_media(shortcode)` - currently always returns `None`; the full
  `DownloadedMedia` cannot be reconstructed from files alone without the original
  caption metadata.
- `clear_old_cache(max_age_days=30)` - removes directories older than the cutoff
  and returns the count of deleted entries.

### `build_ingest_service` factory

Convenience factory in `src/kit_hub/ingestion/factory.py` that wires all
components from a `KitHubParams` object:

```python
from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.ingestion.factory import build_ingest_service
from kit_hub.params.kit_hub_params import get_kit_hub_params

params = get_kit_hub_params()
db = DatabaseSession(params.db.to_config())
await db.init_db()
crud = RecipeCRUDService()

service = build_ingest_service(params, crud, db)
recipe = await service.ingest_ig_url("https://www.instagram.com/p/...")
```

The factory creates a `MediaStorage` rooted at `data/media/`, builds an
`InstaDownloader`, and wraps it in a bare `DownloadRouter` (no transcription hook
by default). Transcription support can be added later when a `BaseTranscriber` is
available from llm-core.

## Design notes

Transcription is optional in the default factory. `IngestService._build_text`
combines whatever text is present - caption only, transcript only, or both joined
by a blank line. If neither is available, `EmptyMediaTextError` is raised before
the LLM chain is called.

The `RecipeCRUDService` is stateless and shared. The `IngestService` calls
`db.get_session()` internally for each recipe persisted, so callers do not need
to manage sessions.
