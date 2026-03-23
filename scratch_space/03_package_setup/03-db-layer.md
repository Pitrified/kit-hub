# Block 2: Database layer

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md)

## Goal

Set up SQLAlchemy ORM models, Alembic migrations, and a CRUD service for recipes. SQLite as the database, upgradeable to Postgres later.

## Source material

- `recipinator`: SQLModel ORM with `Recipe`, `Author`, `Tag`, `RecipeTagLink`, `RecipeSort`
- `media-downloader`: `DownloadDBService` async pattern with `aiosqlite`, WAL mode
- `kit-hub` copilot instructions: Config/Params separation pattern

## Design decisions

- Use SQLAlchemy (not SQLModel) for the ORM - consistent with `media-downloader` patterns
- Async engine with `aiosqlite` for SQLite compatibility
- Recipe JSON (the `RecipeCore` Pydantic model) is stored as a JSON column alongside metadata columns
- UUID primary keys (not IG shortcodes) for uniformity
- `sort_index` integer column for cook-soon queue ordering
- `is_public` and `user_id` columns for access control (ready for when auth is added)

## Deliverables

### 1. DB config - `src/kit_hub/config/db_config.py`

```python
class DbConfig(BaseModelKwargs):
    db_url: str  # SQLite URL, e.g. "sqlite+aiosqlite:///data/kit_hub.db"
    echo: bool = False  # SQLAlchemy echo mode
```

### 2. DB params - `src/kit_hub/params/db_params.py`

```python
class DbParams:
    def __init__(self, env_type: EnvType | None = None): ...
    def to_config(self) -> DbConfig: ...
    # dev: sqlite+aiosqlite:///data/kit_hub_dev.db
    # prod: sqlite+aiosqlite:///data/kit_hub.db
```

### 3. ORM models - `src/kit_hub/db/models.py`

```python
class RecipeRow(Base):
    __tablename__ = "recipes"
    id: Mapped[str]           # UUID primary key
    name: Mapped[str]         # denormalized from RecipeCore for querying
    source: Mapped[str]       # RecipeSource value
    source_id: Mapped[str]    # IG shortcode, note code, or empty
    meal_course: Mapped[str | None]
    recipe_json: Mapped[str]  # full RecipeCore serialized as JSON
    user_id: Mapped[str | None]
    is_public: Mapped[bool]
    sort_index: Mapped[int]
    created_at: Mapped[datetime]
    updated_at: Mapped[datetime]
    # relationships
    tags: Mapped[list[RecipeTagRow]]

class TagRow(Base):
    __tablename__ = "tags"
    name: Mapped[str]         # primary key
    usefulness: Mapped[int]

class RecipeTagRow(Base):
    __tablename__ = "recipe_tags"
    recipe_id: Mapped[str]    # FK to recipes.id (composite PK)
    tag_name: Mapped[str]     # FK to tags.name (composite PK)
    confidence: Mapped[float]
    origin: Mapped[str]       # "ai" or "manual"

class AuthorRow(Base):
    __tablename__ = "authors"
    id: Mapped[str]           # UUID primary key
    username: Mapped[str]
    full_name: Mapped[str]
    biography: Mapped[str]
    page_link: Mapped[str | None]
    platform: Mapped[str]     # "instagram", etc.
    platform_id: Mapped[str]  # platform-specific user ID
```

Key points:
- `recipe_json` stores the full `RecipeCore` as JSON - avoids complex relational mapping of nested preparations/ingredients/steps
- Metadata columns (`name`, `source`, `meal_course`) are denormalized for efficient querying
- `RecipeCore.model_validate_json(row.recipe_json)` reconstructs the Pydantic model

### 4. DB session management - `src/kit_hub/db/session.py`

```python
class DatabaseSession:
    """Manages async SQLAlchemy engine and session factory."""
    def __init__(self, config: DbConfig): ...
    async def init_db(self) -> None: ...      # create tables, WAL mode
    def get_session(self) -> AsyncSession: ... # session factory
    async def close(self) -> None: ...         # dispose engine
```

### 5. CRUD service - `src/kit_hub/db/crud_service.py`

```python
class RecipeCRUDService:
    """Async CRUD operations for recipes."""
    def __init__(self, session: DatabaseSession): ...

    async def create_recipe(
        self, recipe: RecipeCore, source: RecipeSource,
        source_id: str = "", user_id: str | None = None,
    ) -> RecipeRow: ...

    async def get_recipe(self, recipe_id: str) -> RecipeRow | None: ...
    async def get_recipe_core(self, recipe_id: str) -> RecipeCore | None: ...
    async def list_recipes(
        self, user_id: str | None = None, limit: int = 50, offset: int = 0,
    ) -> list[RecipeRow]: ...

    async def update_recipe(self, recipe_id: str, recipe: RecipeCore) -> RecipeRow: ...
    async def delete_recipe(self, recipe_id: str) -> None: ...

    async def reorder_recipes(self, recipe_ids: list[str]) -> None: ...
        # Accepts ordered list of recipe IDs; updates sort_index accordingly

    async def add_tags(
        self, recipe_id: str, tags: list[RecipeTagAssignment],
    ) -> None: ...
```

### 6. Alembic setup

- `src/kit_hub/db/migrations/` with `env.py` and `versions/`
- Initial migration creating all tables
- Configured for async SQLite

## Tasks

- [ ] Create `src/kit_hub/config/db_config.py`
- [ ] Create `src/kit_hub/params/db_params.py`
- [ ] Wire `DbParams` into `KitHubParams`
- [ ] Create `src/kit_hub/db/` package
- [ ] Implement `models.py` with all ORM models
- [ ] Implement `session.py` with async engine management
- [ ] Implement `crud_service.py` with all CRUD operations
- [ ] Set up Alembic with initial migration
- [ ] Write tests: `tests/db/test_crud_service.py` - full CRUD lifecycle with in-memory SQLite
- [ ] Write tests: `tests/db/test_models.py` - ORM model creation, JSON round-trip
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
