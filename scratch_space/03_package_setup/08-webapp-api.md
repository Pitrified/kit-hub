# Block 7: FastAPI API + webapp

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md), [03-db-layer.md](03-db-layer.md), [04-llm-chains.md](04-llm-chains.md), [05-ingestion.md](05-ingestion.md), [06-voice-notes.md](06-voice-notes.md)

## Goal

Extend the existing FastAPI scaffold with recipe-specific API endpoints and server-rendered pages. This is the second UI layer, added after the Telegram bot proves the core pipeline. Uses `fastapi-tools` for the web infrastructure.

## Source material

- `kit-hub` existing scaffold: `webapp/main.py`, `webapp/routers/`, `webapp/services/`
- `fastapi-tools`: `create_app()`, Google OAuth, session management, CORS, rate limiting
- `recipamatic`: recipe CRUD API, voice note API, IG ingestion API
- `media-downloader`: background worker pattern (`run_worker` + job DB)

## Design

The webapp serves two roles:
1. **REST API** (`/api/...`) - JSON endpoints for recipe CRUD, ingestion, voice notes
2. **Server-rendered pages** (`/...`) - Jinja2 + HTMX pages for browsing, editing, voice notes

Background work (IG scraping, Whisper, LLM calls) is handled by an in-process `arq` worker that shares the same codebase. The API enqueues jobs; the worker processes them; the frontend polls or uses SSE for progress.

### Background worker strategy

For the initial implementation, use `FastAPI.BackgroundTasks` for simplicity:
- Ingestion and voice transcription run as background tasks
- No persistence of job state (acceptable since the server rarely restarts)
- If a task fails, the user is informed on the next poll

Upgrade path: switch to `arq` with Redis when job persistence or retry logic is needed.

## Deliverables

### 1. API schemas - `src/kit_hub/webapp/api/schemas.py`

```python
class RecipeCreateRequest(BaseModel):
    text: str  # free text to parse
    source: RecipeSource = RecipeSource.MANUAL

class RecipeIngestRequest(BaseModel):
    url: str  # Instagram URL

class RecipeListResponse(BaseModel):
    recipes: list[RecipeListItem]
    total: int
    page: int
    page_size: int

class RecipeListItem(BaseModel):
    id: str
    name: str
    source: str
    meal_course: str | None
    created_at: datetime

class RecipeDetailResponse(BaseModel):
    id: str
    recipe: RecipeCore
    source: str
    source_id: str
    is_public: bool
    sort_index: int
    created_at: datetime
    updated_at: datetime
    tags: list[RecipeTagAssignment]

class RecipeEditRequest(BaseModel):
    old_step: str
    new_step: str

class RecipeSortRequest(BaseModel):
    recipe_ids: list[str]  # ordered list

class VoiceSessionCreateResponse(BaseModel):
    session_id: str

class VoiceNoteResponse(BaseModel):
    text: str
    timestamp: str  # ISO format
```

### 2. Recipe API router - `src/kit_hub/webapp/api/recipe_router.py`

```
GET    /api/recipes/              -> RecipeListResponse
POST   /api/recipes/              -> RecipeDetailResponse (create from text)
GET    /api/recipes/{id}          -> RecipeDetailResponse
PUT    /api/recipes/{id}          -> RecipeDetailResponse (update full recipe)
DELETE /api/recipes/{id}          -> 204
POST   /api/recipes/{id}/edit     -> RecipeDetailResponse (LLM-powered step edit)
POST   /api/recipes/sort          -> 200 (reorder cook-soon queue)
POST   /api/recipes/ingest        -> RecipeDetailResponse (IG URL ingestion)
```

### 3. Voice API router - `src/kit_hub/webapp/api/voice_router.py`

```
POST   /api/voice/create          -> VoiceSessionCreateResponse
POST   /api/voice/{id}/upload     -> VoiceNoteResponse (audio upload)
POST   /api/voice/{id}/freeze     -> RecipeNote JSON
POST   /api/voice/{id}/to-recipe  -> RecipeDetailResponse
GET    /api/voice/{id}            -> RecipeNote JSON
```

### 4. Page routers - `src/kit_hub/webapp/routers/`

Server-rendered pages using Jinja2 + HTMX:

```
GET  /                    -> landing page
GET  /recipes             -> recipe list (card grid)
GET  /recipes/{id}        -> recipe detail page
GET  /recipes/{id}/edit   -> recipe edit form (HTMX)
GET  /voice               -> voice note session page (audio recorder)
GET  /cook                -> cook-soon queue page (sortable list)
GET  /login               -> Google OAuth login
GET  /profile             -> user profile
```

### 5. Webapp services - `src/kit_hub/webapp/services/`

Thin service layer that wraps core services for the webapp context:

```python
class WebappRecipeService:
    """Wraps RecipeCRUDService + IngestService for webapp use."""
    # Adds user context, pagination, error handling

class WebappVoiceService:
    """Wraps VoiceSessionManager for webapp use."""
    # Adds user context, file upload handling
```

### 6. Lifespan management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: init DB, build services, store in app.state
    # shutdown: close DB, cleanup
    ...
```

### 7. Auth integration

- Google OAuth via `fastapi-tools` (same pattern as `python-project-template`)
- Session-based auth for page routes
- JWT or session token for API routes
- `user_id` from session passed to all service calls

## Tasks

- [ ] Define API schemas in `src/kit_hub/webapp/api/schemas.py`
- [ ] Implement `recipe_router.py` with all recipe endpoints
- [ ] Implement `voice_router.py` with voice session endpoints
- [ ] Update page routers for recipe list, detail, edit, voice, cook-soon
- [ ] Implement webapp service wrappers
- [ ] Set up lifespan with DB + service initialization
- [ ] Wire Google OAuth from `fastapi-tools`
- [ ] Add background task support for slow operations
- [ ] Create Jinja2 templates for all pages
- [ ] Write tests for API endpoints (TestClient)
- [ ] Write tests for page routes (TestClient)
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
