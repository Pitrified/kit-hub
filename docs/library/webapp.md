# Webapp Layer

The `webapp` package is a FastAPI application that exposes recipe management,
voice note recording, and cook-queue reordering through a REST API and
server-rendered Jinja2 pages. It builds on `fastapi-tools` for Google OAuth,
session middleware, CORS, and rate limiting.

## Overview

| Path | Role |
|------|------|
| `src/kit_hub/webapp/main.py` | App factory (`build_app`) with lifespan wiring |
| `src/kit_hub/webapp/app.py` | Uvicorn entry point (`kit_hub.webapp.app:app`) |
| `src/kit_hub/webapp/core/dependencies.py` | Dependency injectors for services |
| `src/kit_hub/webapp/api/schemas.py` | Pydantic request/response models |
| `src/kit_hub/webapp/api/v1/api_router.py` | Top-level `/api/v1` router |
| `src/kit_hub/webapp/api/v1/recipe_router.py` | Recipe CRUD + ingest + edit + sort endpoints |
| `src/kit_hub/webapp/api/v1/voice_router.py` | Voice session lifecycle endpoints |
| `src/kit_hub/webapp/routers/pages_router.py` | Server-rendered HTML page routes |
| `src/kit_hub/webapp/services/user_service.py` | User profile helper |

## Design decisions

**Lifespan-based service wiring.** All heavy services (`DatabaseSession`,
`RecipeCRUDService`, LLM chains, `VoiceSessionManager`) are created inside
`_startup()` and stored on `app.state`. Dependencies read from `app.state` at
request time. This avoids import-time side effects and gives tests full
control over mocks.

**Dependency injection via FastAPI Depends.** Each service has a thin function
in `dependencies.py` that reads from `request.app.state`. Endpoint functions
declare these with `Annotated[ServiceType, Depends(get_service)]`. Tests
replace `app.state` attributes with mocks before creating a `TestClient`.

**Two router families.** API routes live under `/api/v1/` and return JSON.
Page routes live at `/recipes`, `/cook`, `/voice` and return HTML. Both
families require authentication through `get_current_user`.

**Stub audio transcriber.** When Whisper models are not available (e.g. in CI),
a `_StubAudioTranscriber` is used that returns a placeholder string. This
keeps the voice pipeline functional without GPU dependencies.

## API endpoints

### Recipe router (`/api/v1/recipes`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Paginated recipe list for authenticated user |
| `POST` | `/` | Create recipe from free text via LLM transcriber |
| `POST` | `/ingest` | Ingest recipe from Instagram URL |
| `GET` | `/{id}` | Full recipe detail with tags |
| `PUT` | `/{id}` | Replace recipe content |
| `DELETE` | `/{id}` | Delete recipe |
| `POST` | `/{id}/edit` | LLM-powered step correction |
| `POST` | `/sort` | Reorder cook-soon queue |

### Voice router (`/api/v1/voice`)

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/create` | Start a new voice recording session |
| `POST` | `/{id}/upload` | Upload an audio clip for transcription |
| `POST` | `/{id}/freeze` | Freeze session and get the final `RecipeNote` |
| `POST` | `/{id}/to-recipe` | Convert voice session to a persisted `RecipeCore` |
| `GET` | `/{id}` | Retrieve session transcript |

## Page routes

| Path | Template | Purpose |
|------|----------|---------|
| `/recipes` | `recipes.html` | Card grid with pagination and add-recipe panel |
| `/recipes/{id}` | `recipe_detail.html` | Full recipe with preparations, ingredients, and steps |
| `/cook` | `cook.html` | Sortable cook-soon queue with reorder buttons |
| `/voice` | `voice.html` | Voice recording UI with MediaRecorder API |

## Schemas

Request and response models live in
[`schemas`](../../reference/kit_hub/webapp/api/schemas/).

Key models:

- `RecipeCreateRequest` - text + source for LLM parsing
- `RecipeIngestRequest` - Instagram URL
- `RecipeEditRequest` - old step + new step for corrections
- `RecipeSortRequest` - ordered list of recipe IDs
- `RecipeListResponse` - paginated recipe summaries
- `RecipeDetailResponse` - full recipe with `RecipeCore` and tags
- `VoiceSessionCreateResponse` / `VoiceNoteResponse` - voice session payloads

## Templates

All templates extend `base.html` (Bulma CSS + HTMX). The `recipes.html` page
uses HTMX for recipe creation and deletion without full page reloads. The
`cook.html` page uses vanilla JavaScript to post reordered recipe IDs to the
sort endpoint. The `voice.html` page uses the browser `MediaRecorder` API to
capture audio clips and posts them as `audio/webm` blobs.

## Testing approach

Tests create a real `create_app()` instance with mocked `app.state` services.
Authentication is injected by writing a `SessionData` entry to the in-memory
session store and setting the session cookie on the test client. No actual
database, LLM, or Whisper calls are made.

```python
with TestClient(app) as client:
    session_store = app.state.session_store
    session_store.create_session(mock_session_data)
    client.cookies.set("session", mock_session_data.session_id)
    resp = client.get("/api/v1/recipes/")
```
