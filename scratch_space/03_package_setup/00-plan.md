# kit-hub setup

## Overview

we have as libraries ready to use:

- `llm-core` - LLM tooling: `StructuredLLMChain`, chat/embeddings configs, vector store, versioned Jinja prompts
- `fastapi-tools` - FastAPI web layer: Google OAuth, session management, CORS, rate limiting, Jinja2 templates, HTMX
- `media-downloader` - Instagram download, yt-dlp, web scraping, Whisper transcription, background worker queue

we have existing recipe-related projects:

- `recipamatic` - SvelteKit + FastAPI; working recipe model, IG ingestion, LLM parsing, voice notes, auth
- `recipinator` - React + FastAPI; working recipe model, IG ingestion, sort queue, tag model, SQLite storage
- `cookbook` - Personal static recipe site in Italian. Jekyll + GitHub Pages. Live at `pitrified.github.io/cookbook`.

note: the actual tech stack for the three existing projects is not relevant. we want to update to the new libraries.

## Chosen architecture: Option 3 + 6

**Option 3**: Monorepo, single FastAPI backend + background worker process
**Option 6**: Telegram bot as primary UI (no web frontend initially)

See [07-recipe-plan.md](../../linux-box-cloudflare/scratch_space/vibes/07-recipe-plan.md) for the full brainstorm.

### Key decisions

| Decision | Choice | Rationale |
|--|--|--|
| Background worker | `arq` in-process | asyncio-native, no Redis for now; switch to Redis later if needed |
| Database | SQLite + SQLAlchemy + Alembic | avoid flat-JSON trap; upgradeable to Postgres |
| Recipe primary key | UUID for all recipes; IG shortcode stored as a separate field | uniform key strategy |
| First UI | Telegram bot via `tg-central-hub-bot` patterns | zero frontend overhead; voice input native on mobile |
| Second UI | FastAPI + Jinja2/HTMX templates (server-rendered) | evaluate before committing to a full SPA |
| Frontend timing | defer until core pipeline works end-to-end | bot covers ingestion + voice flows first |

### Dependency graph

```
kit-hub
  depends on:
    llm-core          -> StructuredLLMChain, ChatConfig, PromptLoader
    media-downloader  -> InstaDownloader, TranscriptionHook, DownloadRouter
    fastapi-tools     -> create_app, OAuth, session, CORS, rate limiting
  uses patterns from:
    tg-central-hub-bot -> BotParams, ApplicationBuilder, command handlers
    python-project-template -> Singleton, EnvType, Config/Params separation
```

### Repo structure target

```
kit-hub/
  prompts/                 # versioned Jinja2 prompt templates, use paths.prompt_fol to access them
    transcriber/v1.jinja
    editor/v1.jinja
    section_finder/v1.jinja
    tag_extractor/v1.jinja
  src/kit_hub/
    config/                # Pydantic config models (shape only)
      sample_config.py     # (existing)
      db_config.py         # DB connection config
      bot_config.py        # Telegram bot config
      llm_config.py        # LLM chain configs (transcriber, editor, etc.)
      webapp/              # (existing from fastapi-tools scaffold)
    params/                # Plain classes that load values
      kit_hub_params.py    # (existing) - add bot, db, llm params
      kit_hub_paths.py     # (existing)
      bot_params.py        # Telegram bot token loading
      db_params.py         # DB path/URL loading
      llm_params.py        # LLM provider + model selection
      webapp/              # (existing)
    recipes/               # A. Recipe data model + validation
      recipe_core.py       # RecipeCore, Preparation, Ingredient, Step
      recipe_note.py       # RecipeNote, Note (voice session)
      recipe_enums.py      # StepType, RecipeSource, MealCourse
    db/                    # B. Persistent storage
      models.py            # SQLAlchemy ORM models
      crud_service.py      # RecipeCRUDService
      migrations/          # Alembic
    ingestion/             # C. Instagram ingestion
      ingest_service.py    # orchestrate IG download -> LLM parse -> DB save
      cache_manager.py     # manage cached IG post data
    llm/                   # E + F. LLM parsing + editing + tags
      transcriber.py       # RecipeCoreTranscriber (StructuredLLMChain)
      editor.py            # RecipeCoreEditor
      section_finder.py    # SectionIdxFinder
      tag_extractor.py     # AI tag extraction (new)
    voice/                 # G + D. Voice note session
      voice_session.py     # session lifecycle: create, append, freeze
      transcription.py     # Whisper integration via media-downloader
    search/                # I. Semantic search (later phase)
      recipe_indexer.py    # index recipes into vector store
      recipe_searcher.py   # search recipes
    bot/                   # Telegram bot handlers
      bot_app.py           # ApplicationBuilder setup + handler registration
      handlers/
        start.py           # /start command
        ingest.py          # paste IG URL -> parse recipe
        voice.py           # voice message -> transcribe -> recipe note
        browse.py          # browse/list recipes
        sort.py            # cook-soon queue management
    webapp/                # K. HTTP API (existing scaffold)
      api/                 # REST API routers
      routers/             # page routers (Jinja2 templates)
      services/            # business logic services
    data_models/           # (existing)
    metaclasses/           # (existing)
  tests/                   # mirrors src/ structure
  data/                    # leverage MediaStorage if possible, otherwise add
    recipes/               # recipe JSON cache (if needed alongside DB)
    ig/                    # Instagram post cache
    notes/                 # voice note audio files
```

## Plan - macro blocks

Each macro block is a self-contained unit of work. They are ordered by dependency (earlier blocks are prerequisites for later ones). Each has a companion sub-plan file with detailed steps.

### Block 1: Recipe data model + validation

**Sub-plan**: [02-recipe-models.md](02-recipe-models.md)

Port the canonical recipe schema from `recipamatic` to clean Pydantic models in `src/kit_hub/recipes/`. This is the foundation - everything else depends on it.

Deliverables:
- `RecipeCore`, `Preparation`, `Ingredient`, `Step` models
- `RecipeNote`, `Note` models for voice sessions
- Enums: `StepType`, `RecipeSource`, `MealCourse`
- Full test coverage
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 2: Database layer

**Sub-plan**: [03-db-layer.md](03-db-layer.md)

Set up SQLAlchemy ORM models, Alembic migrations, and a CRUD service. Recipes, tags, authors, and sort state all live in SQLite.

Deliverables:
- SQLAlchemy ORM models mirroring the Pydantic recipe models
- `RecipeCRUDService` with create, read, update, delete, list, reorder
- Alembic init + initial migration
- `DbParams` + `DbConfig` for connection management
- Full test coverage with in-memory SQLite
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 3: LLM chains

**Sub-plan**: [04-llm-chains.md](04-llm-chains.md)

Reimplement the LLM pipelines using `llm-core` `StructuredLLMChain`. Each chain gets a versioned Jinja prompt.

Deliverables:
- `RecipeCoreTranscriber`: free text -> structured `RecipeCore`
- `RecipeCoreEditor`: old recipe + correction -> updated `RecipeCore`
- `SectionIdxFinder`: NL location query -> `(prep_idx, step_idx)`
- `TagExtractor`: recipe -> `list[Tag]` with confidence scores (new)
- Versioned prompt templates in `src/kit_hub/llm/prompts/`
- `LlmParams` + `LlmConfig` for model selection
- Tests with mocked LLM responses
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 4: Instagram ingestion

**Sub-plan**: [05-ingestion.md](05-ingestion.md)

Wire `media-downloader`'s `InstaDownloader` + `TranscriptionHook` into a kit-hub ingestion service that downloads IG posts, transcribes video if present, and produces a structured recipe via the LLM chain.

Deliverables:
- `IngestService`: URL -> download -> transcribe -> LLM parse -> `RecipeCore`
- Cache management for IG post data
- Integration with `RecipeCRUDService` to persist results
- Tests with mocked downloader + LLM
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 5: Voice note session

**Sub-plan**: [06-voice-notes.md](06-voice-notes.md)

Reimplement the live cooking dictation flow: create a session, append audio clips (transcribed via Whisper), freeze the session, and optionally convert to a clean recipe.

Deliverables:
- `VoiceSession`: create, append audio, freeze, get transcript
- Whisper integration via `media-downloader` transcription
- Bridge: `RecipeNote.to_string()` -> `RecipeCoreTranscriber` -> `RecipeCore`
- Storage of audio files in `data/notes/`
- Tests with mocked transcription
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 6: Telegram bot

**Sub-plan**: [07-telegram-bot.md](07-telegram-bot.md)

Build the Telegram bot as the first UI. Uses `python-telegram-bot` (PTB v22+) with `ApplicationBuilder`. The bot is the primary way to interact with kit-hub initially.

Deliverables:
- `BotParams` + `BotConfig` (following `tg-central-hub-bot` pattern)
- `/start` command - welcome + help
- IG ingest command: paste URL -> bot replies with parsed recipe card
- Voice message handler: audio -> Whisper -> recipe note session
- `/recipes` - list recent recipes (inline keyboard pagination)
- `/cook` - manage cook-soon queue (inline keyboard)
- Bot entry point script
- Tests for handler logic (mocked bot context)
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 7: FastAPI API + webapp

**Sub-plan**: [08-webapp-api.md](08-webapp-api.md)

Extend the existing FastAPI scaffold with recipe-specific API endpoints and server-rendered pages. This is the second UI layer, added after the bot proves the pipeline.

Deliverables:
- REST API: `/api/recipes/` CRUD, `/api/recipes/sort`, `/api/ingest/ig`
- Voice note API: `/api/voice/create`, `/api/voice/{id}/upload`, `/api/voice/{id}/freeze`
- Server-rendered recipe list + detail pages (Jinja2 + HTMX)
- Google OAuth integration (via `fastapi-tools`)
- Background worker for slow jobs (ingestion, transcription)
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

### Block 8: Search + discovery

**Sub-plan**: [09-search.md](09-search.md)

Implement semantic search using `llm-core` vector store. Index recipes on save; query by natural language.

Deliverables:
- `RecipeIndexer`: index recipe text + ingredients into vector store on create/update
- `RecipeSearcher`: NL query -> ranked recipe list
- API endpoint: `/api/recipes/search?q=...`
- Bot command: `/search <query>`
- AI tag extraction on recipe create (wired to `TagExtractor` from Block 3)
- Verification: `uv run pytest && uv run ruff check . && uv run pyright`

## Phasing

### Phase 1 - Core (Blocks 1-3)

Foundation: data model, storage, LLM chains. No UI yet, but all core logic is testable and usable from code.

### Phase 2 - Pipelines (Blocks 4-5)

Ingestion and voice note session. These are the two main input flows for recipes. Still no UI, but the full pipeline works end-to-end.

### Phase 3 - Telegram bot (Block 6)

First usable UI. Can ingest recipes from IG, transcribe voice notes, browse and sort recipes - all from Telegram.

### Phase 4 - Web (Blocks 7-8)

Web frontend + search. Full-featured recipe management app with server-rendered pages and semantic search.
