# Database Layer

The database layer provides persistent storage for recipes, tags, and author
profiles using SQLAlchemy (async) with SQLite as the backend.

## Overview

Five files form the layer:

| File | Role |
|------|------|
| `src/kit_hub/config/db_config.py` | `DbConfig` - shape of connection settings |
| `src/kit_hub/params/db_params.py` | `DbParams` - loads actual values per environment |
| `src/kit_hub/db/models.py` | SQLAlchemy ORM models for all tables |
| `src/kit_hub/db/session.py` | `DatabaseSession` - engine + session factory |
| `src/kit_hub/db/crud_service.py` | `RecipeCRUDService` - high-level async CRUD |

An Alembic migration lives in `src/kit_hub/db/migrations/` with the initial
schema in `versions/`.

## Design decisions

**JSON blob for recipe content.** The full `RecipeCore` Pydantic model is
stored as a JSON string in `recipe_json`. Metadata columns (`name`, `source`,
`meal_course`) are denormalised for queries. This avoids complex relational
mapping of nested preparations and ingredients while keeping the rich model
intact.

**UUID primary keys.** All recipes use UUID strings as primary keys rather
than IG shortcodes, so the key scheme is uniform across all ingestion sources.

**Async throughout.** All database operations use `sqlalchemy.ext.asyncio`
with `aiosqlite`. WAL journal mode is enabled on init for better read
concurrency and crash safety.

**Service is stateless.** `RecipeCRUDService` holds no session state - callers
pass a session from `DatabaseSession.get_session()`. This keeps it safe to
share a single instance across concurrent requests.

## Tables

```
recipes       - one row per recipe; metadata + RecipeCore JSON blob
tags          - global tag registry; keyed by tag name
recipe_tags   - many-to-many link between recipes and tags
authors       - Instagram / platform author profiles
```

## Usage

```python
from kit_hub.config.db_config import DbConfig
from kit_hub.db.crud_service import RecipeCRUDService
from kit_hub.db.session import DatabaseSession
from kit_hub.recipes.recipe_enums import RecipeSource

# Initialise (normally done once at app startup via KitHubParams)
config = DbConfig(db_url="sqlite+aiosqlite:///data/kit_hub_dev.db")
db = DatabaseSession(config)
await db.init_db()

crud = RecipeCRUDService()

# Create a recipe
async with db.get_session() as session:
    row = await crud.create_recipe(session, my_recipe_core, RecipeSource.MANUAL)

# Fetch it back as a RecipeCore
async with db.get_session() as session:
    core = await crud.get_recipe_core(session, row.id)

# Close when done
await db.close()
```

## Config / Params

`KitHubParams` wires everything together:

```python
params = get_kit_hub_params()
db_config = params.db.to_config()  # DbConfig
```

- DEV stage - SQLite file: `data/kit_hub_dev.db`
- PROD stage - SQLite file: `data/kit_hub.db`

## Alembic migrations

```bash
# Generate a new migration after a model change
uv run alembic revision --autogenerate -m "describe_change"

# Apply all pending migrations
uv run alembic upgrade head

# Show current migration status
uv run alembic current
```

The `env.py` reads the database URL from `DbParams` so migrations always
target the correct file for the active environment (`ENV_STAGE_TYPE` /
`ENV_LOCATION_TYPE`).
