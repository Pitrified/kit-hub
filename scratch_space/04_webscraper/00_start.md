# Scrape any page for recipes

## Overview

current downloader 
`media-downloader`
only gets pages in a registered set of urls,
leveraging a dedicated recipe scraper library.

we want to add a more general scraper that can be used on any page,
to use it as a fallback when the domain is unknown.

in media downloader, the general scraper is a separate entity, completely decoupled from the recipe scrapers

it is a concern for `kit-hub` using the right scraper at the right time,
and doing the fallback pattern where needed

## Analysis of current state

### media-downloader architecture

The download pipeline lives in `media_downloader.core`:

- `UrlDetector` classifies URLs into `SourceType` (INSTAGRAM, YOUTUBE, TIKTOK, WEB_RECIPE, UNKNOWN).
  - WEB_RECIPE is matched by a hardcoded `_RECIPE_HOSTS` frozenset (allrecipes.com, bbcgoodfood.com, etc.).
  - Unknown URLs (not matching any pattern) get `SourceType.UNKNOWN` - no downloader is registered for this, so `DownloadRouter.download()` raises `NoDownloaderForSourceError`.
- `DownloadRouter` maps `SourceType -> BaseDownloader` and runs post-processors (e.g. transcription).
- `WebRecipeDownloader` handles `SourceType.WEB_RECIPE`:
  - First tries `recipe-scrapers` (structured extraction: title, ingredients, instructions).
  - Falls back to `trafilatura` (raw text extraction) if recipe-scrapers fails.
  - Returns `DownloadedMedia` with recipe text as `caption` and a `WebRecipeMetadata` dataclass.
- Provider enablement is config-driven via `ProvidersConfig.web_recipe_enabled` (bool, default True).
- Dependencies: `recipe-scrapers>=14.0` and `trafilatura>=1.8` are in the `[recipe]` optional group.

### kit-hub integration

- Kit-hub depends on `media-downloader[instagram]` only (pyproject.toml) - no recipe scraping deps installed.
- `IngestService` is the entry point: `ingest_ig_url()` calls `DownloadRouter.adownload()` then passes caption+transcript to `RecipeCoreTranscriber` (LLM chain) and persists via `RecipeCRUDService`.
- `build_ingest_service()` factory in `kit_hub/ingestion/factory.py` only registers `InstaDownloader`.
- The webapp exposes `POST /api/v1/recipes/ingest` which accepts a URL (typed as `RecipeIngestRequest(url: str)`), assumed to be an Instagram URL, calls `ingest.ingest_ig_url()`.
- `RecipeSource` enum has: INSTAGRAM, VOICE_NOTE, MANUAL. No WEB source yet.
- There is no fallback logic for non-Instagram URLs.

### Gap summary

1. **No general page scraper** - unknown URLs (not IG, not in `_RECIPE_HOSTS`) cannot be downloaded at all.
2. **No web recipe path in kit-hub** - even known recipe sites would fail because kit-hub only has `InstaDownloader` registered.
3. **No fallback pattern** - if a URL is not Instagram, the user gets an error rather than a degraded but usable result.

---

## Plan for general scraper

### Where it lives: media-downloader

A new provider `GenericWebScraper` in `media_downloader/core/providers/generic_web.py`:

1. **Responsibility**: fetch any web page and extract its main textual content.
2. **Strategy**: use `trafilatura` (already a dep in the `[recipe]` group) for content extraction. No structured recipe parsing - that is the LLM's job in kit-hub.
3. **SourceType**: add a new `SourceType.GENERIC_WEB` value.
4. **Detector change**: `UrlDetector.detect()` should return `GENERIC_WEB` instead of `UNKNOWN` for unrecognised HTTP URLs (keep UNKNOWN for truly invalid or non-HTTP inputs).
5. **Output**: `DownloadedMedia` with `caption` = extracted text, `metadata` = new `GenericWebMetadata(host, page_title, char_count)`.
6. **Config**: new `ProvidersConfig.generic_web_enabled: bool = True`.
7. **Dependency group**: rename existing `recipe` extra to `web` (covers both `recipe-scrapers` and `trafilatura` for all web scraping).

### New files in media-downloader

| File | Contents |
|------|----------|
| `core/providers/generic_web.py` | `GenericWebScraper` class |
| (edit) `core/models.py` | add `GENERIC_WEB` to `SourceType` |
| (edit) `core/metadata.py` | add `GenericWebMetadata`, update union |
| (edit) `core/detector.py` | return `GENERIC_WEB` for valid HTTP URLs instead of `UNKNOWN` |
| (edit) `config/downloader_config.py` | add `generic_web_enabled` flag |
| (edit) `webapp/router_builder.py` | register `GenericWebScraper` when enabled |
| (edit) `pyproject.toml` | rename `recipe` extra to `web` |

---

## Plan for kit-hub integration

### 1. Add WEB_RECIPE and WEB_GENERIC to RecipeSource

In `kit_hub/recipes/recipe_enums.py`:
```python
WEB_RECIPE = "web_recipe"
WEB_GENERIC = "web_generic"
```

### 2. Extend the ingestion factory

In `kit_hub/ingestion/factory.py`, register both `InstaDownloader` and `WebRecipeDownloader` (and optionally `GenericWebScraper`).

Update pyproject.toml dependency: `media-downloader[instagram,web]`.

### 3. Add a unified ingest URL method

In `IngestService`:
```python
async def ingest_url(self, url: str, user_id: str | None = None) -> RecipeCore:
    """Download any supported URL, parse with LLM, persist."""
    media = await self._dl_router.adownload(url)
    text = self._build_text(media)
    if not text:
        raise EmptyMediaTextError(url)
    source = self._map_source(media.source)
    recipe = await self._transcriber.ainvoke(text)
    # persist...
```
This replaces `ingest_ig_url` as the main entry point (or `ingest_ig_url` becomes a thin wrapper).

### 4. Fallback strategy (kit-hub's responsibility)

The DownloadRouter in media-downloader now handles the dispatch:
- Instagram URL -> InstaDownloader
- Known recipe host -> WebRecipeDownloader (structured extraction)
- Any other HTTP URL -> GenericWebScraper (trafilatura raw extraction)

In all cases, kit-hub's `RecipeCoreTranscriber` (LLM chain) gets the extracted text and produces a structured `RecipeCore`. The LLM handles the ambiguity of unstructured text.

The fallback ordering is therefore handled by the detector classification, not by kit-hub retrying. Kit-hub just calls `ingest_url()` with any URL and trusts the pipeline.

### 5. Webapp changes

- Rename/generalize `POST /api/v1/recipes/ingest` to accept any URL (not just Instagram).
- Update `RecipeIngestRequest` docstring.
- Remove the IG-specific error handling or generalize it.

### 6. Sequence

1. Implement `GenericWebScraper` in media-downloader, tag a new release.
2. Update kit-hub's dep, extend `IngestService`, update factory.
3. Generalize the webapp endpoint.
4. Add tests for each layer.

---

## Implementation progress

### Step 1: media-downloader GenericWebScraper - DONE

All changes verified (pytest 89 passed, ruff clean, pyright 0 errors).

**Files changed:**

| File | Change |
|------|--------|
| `core/models.py` | Added `GENERIC_WEB = "generic_web"` to `SourceType` enum |
| `core/metadata.py` | Added `GenericWebMetadata(host, page_title, char_count)` dataclass; updated `SourceMetadata` union |
| `core/detector.py` | URLs starting with `http://`/`https://` that don't match any specific pattern now return `GENERIC_WEB` instead of `UNKNOWN` |
| `core/providers/generic_web.py` | **New file** - `GenericWebScraper` provider using `trafilatura`; custom exceptions `GenericWebFetchError`, `GenericWebExtractError` |
| `config/downloader_config.py` | Added `generic_web_enabled: bool = True` to `ProvidersConfig` |
| `webapp/router_builder.py` | Registers `GenericWebScraper` when `generic_web_enabled` is True |
| `pyproject.toml` | Renamed `recipe` extra to `web` (covers both `recipe-scrapers` and `trafilatura`); updated `box` and `all` extras |
| `tests/core/test_detector.py` | Added `TestGenericWebDetection` class; updated `TestUnknownDetection` to test non-HTTP URLs |
| `tests/core/test_models.py` | Added `GENERIC_WEB` assertion to `test_source_type_values` |

**Design decisions:**
- `UNKNOWN` is now reserved for truly non-HTTP inputs (bare strings, ftp://, etc.)
- `GenericWebScraper` raises custom exceptions (`GenericWebFetchError`, `GenericWebExtractError`) rather than generic `RuntimeError`
- Title extraction uses a simple regex on `<title>` tag rather than adding an HTML parsing dep
- The `web` extra name keeps things simple: one extra for all web scraping (structured + generic)

### Step 2: kit-hub integration - DONE

All changes verified (pytest 300 passed, ruff clean, pyright errors unchanged from baseline at 141 - all pre-existing StrEnum/union-syntax issues).

**Files changed:**

| File | Change |
|------|--------|
| `pyproject.toml` | Changed dep from `media-downloader[instagram]` to `media-downloader[instagram,web]` |
| `recipes/recipe_enums.py` | Added `WEB_RECIPE = "web_recipe"` and `WEB_GENERIC = "web_generic"` to `RecipeSource` |
| `ingestion/factory.py` | Factory now registers all 3 providers: `InstaDownloader`, `WebRecipeDownloader`, `GenericWebScraper` |
| `ingestion/ingest_service.py` | Added `ingest_url()` unified method; `ingest_ig_url()` now wraps it; added `_map_source()` with `_SOURCE_MAP` dict; added `UnmappedSourceTypeError` |
| `webapp/api/schemas.py` | Updated `RecipeIngestRequest` docstring from "Instagram URL" to "any URL" |
| `webapp/api/v1/recipe_router.py` | Endpoint now calls `ingest_url()` instead of `ingest_ig_url()`; updated summary and docstring |
| `tests/webapp/test_recipe_api.py` | Updated 2 mocks from `ingest_ig_url` to `ingest_url` |

**Design decisions:**
- `ingest_ig_url()` kept as thin wrapper for backward compatibility
- `_SOURCE_MAP` dict at module level maps `SourceType` to `RecipeSource` for clean dispatch
- `UnmappedSourceTypeError` raised for any `SourceType` not in the map (defensive, should not happen in practice)
- No fallback/retry logic needed - `DownloadRouter` handles dispatch via `UrlDetector` classification
