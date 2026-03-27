# Track progress - kit-hub project setup

Main plan: [00-plan.md](00-plan.md)

Track progress of each macro block in this file, and link to the companion sub plans for details.
Update this file as needed to reflect changes in the plan, and to track progress of the project setup.

---

## Architecture

**Option 3 + 6**: Monorepo, single FastAPI backend + background worker, Telegram bot as first UI.

### Phases

| Phase | Blocks | Goal |
|--|--|--|
| Phase 1 - Core | 1, 2, 3 | Data model, storage, LLM chains - all testable from code |
| Phase 2 - Pipelines | 4, 5 | IG ingestion + voice notes - full input flows working |
| Phase 3 - Bot | 6 | First usable UI via Telegram |
| Phase 4 - Web | 7, 8 | Web frontend + search |

---

## Current state

Phase 1 - complete. Blocks 1, 2, and 3 done.
Phase 2 - in progress. Block 4 (Instagram ingestion) complete.

---

## Macro blocks

### Block 1: Recipe data model + validation

Sub-plan: [02-recipe-models.md](02-recipe-models.md)
Status: **complete**
Phase: 1

Core Pydantic models: `RecipeCore`, `Preparation`, `Ingredient`, `Step`, `RecipeNote`, `Note`, enums.
No dependencies - this is the foundation.

- [x] Enums (`StepType`, `RecipeSource`, `MealCourse`)
- [x] Core models (`RecipeCore`, `Preparation`, `Ingredient`, `Step`)
- [x] Section index models (`SectionPreparation`, `SectionIngredient`, `SectionStep`)
- [x] Tag models (`Tag`, `RecipeTagAssignment`)
- [x] Voice note models (`Note`, `RecipeNote`)
- [x] Tests
- [x] Verification pass

---

### Block 2: Database layer

Sub-plan: [03-db-layer.md](03-db-layer.md)
Status: **complete**
Phase: 1
Depends on: Block 1

SQLAlchemy ORM + Alembic + async CRUD service. SQLite with JSON column for `RecipeCore`.

- [x] `DbConfig` + `DbParams`
- [x] ORM models (`RecipeRow`, `TagRow`, `RecipeTagRow`, `AuthorRow`)
- [x] `DatabaseSession` async engine management
- [x] `RecipeCRUDService` (create, read, update, delete, list, reorder, add_tags)
- [x] Alembic init + initial migration
- [x] Tests (in-memory SQLite)
- [x] Verification pass

---

### Block 3: LLM chains

Sub-plan: [04-llm-chains.md](04-llm-chains.md)
Status: **complete**
Phase: 1
Depends on: Block 1

`StructuredLLMChain`-based pipelines with versioned Jinja prompts.

- [x] `LlmConfig` + `LlmParams`
- [x] Wire `LlmParams` into `KitHubParams`
- [x] Add `prompts_fol` to `KitHubPaths`
- [x] `RecipeCoreTranscriber` (text -> RecipeCore)
- [x] `RecipeCoreEditor` (old recipe + correction -> updated RecipeCore)
- [x] `SectionIdxFinder` (NL location -> section index)
- [x] `TagExtractor` (recipe -> tags with confidence)
- [x] Versioned prompt templates (`v1.jinja` for each in `prompts/`)
- [x] Tests (mocked LLM via `FakeChatModelConfig`)
- [x] Verification pass

---

### Block 4: Instagram ingestion

Sub-plan: [05-ingestion.md](05-ingestion.md)
Status: **complete**
Phase: 2
Depends on: Blocks 1, 2, 3

Pipeline: IG URL -> `media-downloader` download -> transcribe -> LLM parse -> DB persist.

- [x] `IngestService` (orchestrator) with `ingest_ig_url` and `ingest_text`
- [x] `EmptyMediaTextError` for missing caption/transcript
- [x] `CacheManager` for IG post deduplication checks
- [x] `build_ingest_service` factory function
- [x] Tests (mocked `DownloadRouter` + `RecipeCoreTranscriber`, real in-memory DB)
- [x] Verification pass

---

### Block 5: Voice note session

Sub-plan: [06-voice-notes.md](06-voice-notes.md)
Status: **not started**
Phase: 2
Depends on: Blocks 1, 3

Live dictation: create session -> append audio -> Whisper transcribe -> freeze -> convert to recipe.

- [ ] `VoiceSessionManager` (create, append, freeze, get, list)
- [ ] `VoiceToRecipeConverter` (RecipeNote -> RecipeCore) - the missing bridge
- [ ] Tests (mocked Whisper)
- [ ] Verification pass

---

### Block 6: Telegram bot

Sub-plan: [07-telegram-bot.md](07-telegram-bot.md)
Status: **not started**
Phase: 3
Depends on: Blocks 1-5

First UI. PTB v22+ with `ApplicationBuilder`.

- [ ] `BotConfig` + `BotParams`
- [ ] `KitHubBot` builder
- [ ] Handlers: `/start`, IG ingest, voice session, `/recipes`, `/cook`, `/recipe`
- [ ] Message formatting (HTML for Telegram)
- [ ] Entry point script (`kit-hub-bot`)
- [ ] Tests (mocked bot context)
- [ ] Verification pass

---

### Block 7: FastAPI API + webapp

Sub-plan: [08-webapp-api.md](08-webapp-api.md)
Status: **not started**
Phase: 4
Depends on: Blocks 1-5

REST API + server-rendered pages. Second UI layer.

- [ ] API schemas
- [ ] Recipe API router (CRUD + ingest + edit + sort)
- [ ] Voice API router (create + upload + freeze + to-recipe)
- [ ] Page routers (Jinja2 + HTMX)
- [ ] Webapp services
- [ ] Lifespan management (DB + services init/shutdown)
- [ ] Google OAuth integration
- [ ] Background tasks for slow operations
- [ ] Tests (TestClient)
- [ ] Verification pass

---

### Block 8: Search + discovery

Sub-plan: [09-search.md](09-search.md)
Status: **not started**
Phase: 4
Depends on: Blocks 1, 2, 3

Semantic search via `llm-core` vector store + automatic AI tag extraction.

- [ ] `RecipeIndexer` (index on create/update)
- [ ] `RecipeSearcher` (NL query -> ranked results)
- [ ] `SearchConfig` + `SearchParams`
- [ ] `RecipeDocument` adapter for `Vectorable` protocol
- [ ] Auto-tagging hook in recipe create flow
- [ ] API endpoint + bot command
- [ ] Tests (mocked vector store)
- [ ] Verification pass