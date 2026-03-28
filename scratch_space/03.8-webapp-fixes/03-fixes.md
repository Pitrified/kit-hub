# Various fixes

## e9

all recipes show `sort #0` in the recipe detail page and in the recipe list page

### Root cause

`create_recipe()` in `src/kit_hub/db/crud_service.py` hardcodes `sort_index=0` for every new recipe. The templates display that raw value:

- `templates/pages/recipe_detail.html` line 33: `Sort #{{ row.sort_index }}`
- `templates/pages/recipes.html` line 76: `#{{ recipe.sort_index }}`

So every recipe that hasn't been explicitly reordered via the cook page shows `Sort #0`.

### Fix

In `crud_service.py` `create_recipe()`, before inserting the new row, query for the current max `sort_index` and set the new recipe to `max + 1`:

```python
# in create_recipe, before building the RecipeRow
max_idx_result = await session.execute(
    select(func.coalesce(func.max(RecipeRow.sort_index), -1))
)
next_idx = max_idx_result.scalar_one() + 1
# then use sort_index=next_idx in the RecipeRow constructor
```

This places new recipes at the end of the queue instead of colliding at 0. No template changes needed - the displayed number will now be meaningful.

---

## e10

in the action for mkdocs there is a strict mode which causes the build to fail if there are warnings, which seems incredibly restrictive
disable that and hope the build will succeed, and if it doesn't then we can fix the warnings instead of just ignoring them

### Root cause

`.github/workflows/docs.yml` line 43 builds with `--strict`:

```yaml
- name: Build MkDocs site
  run: uv run mkdocs build --strict
```

`mkdocs.yml` itself does NOT set `strict: true` - it is only the CI workflow flag. Locally `uv run mkdocs serve` works fine; the build only fails in the GitHub Actions pipeline.

### Fix

Remove the `--strict` flag from `.github/workflows/docs.yml`:

```yaml
- name: Build MkDocs site
  run: uv run mkdocs build
```

Single-line change. If we later want to enforce strictness, we can re-enable it after fixing all warnings.

---

## e11

we see env loading from too many places
the dependencies should not autoload env (look at `fastapi-tools` where it was disabled for a similar reason)

```log
2026-03-28 12:54:31.983 | DEBUG    | kit_hub.params.load_env:load_env:15 - Loaded environment variables from /home/pmn/cred/kit-hub/.env
2026-03-28 12:54:32.366 | DEBUG    | llm_core.params.load_env:load_env:15 - Loaded environment variables from /home/pmn/cred/llm-core/.env
2026-03-28 12:54:36.038 | DEBUG    | media_downloader.params.load_env:load_env:17 - .env file not found at /home/pmn/cred/media-downloader/.env
```

### Root cause

Both `llm-core` and `media-downloader` auto-call `load_env()` in their package `__init__.py`:

- `llm-core/src/llm_core/__init__.py` lines 28-30: imports and calls `load_env()`
- `media-downloader/src/media_downloader/__init__.py` lines 3-5: imports and calls `load_env()`

When kit-hub imports anything from these packages, their `__init__.py` fires and side-effect loads their own `.env` file. The trigger chain is:

1. `kit_hub/__init__.py` calls `load_env()` (correct - main app)
2. `kit_hub_params.py` creates `LlmParams(...)` which imports from `llm_core` -> triggers `llm_core/__init__.py` -> `load_env()`
3. `kit_hub/ingestion/factory.py` imports from `media_downloader` -> triggers `media_downloader/__init__.py` -> `load_env()`

`fastapi-tools` does NOT have this problem because its `__init__.py` only exports public APIs without calling `load_env()`.

### Fix (in the dependency repos, not kit-hub)

**`llm-core`**: Remove the `load_env()` call from `src/llm_core/__init__.py`. Keep the function available in `params/load_env.py` for standalone use but do not auto-execute it on import.

**`media-downloader`**: Same - remove the `load_env()` call from `src/media_downloader/__init__.py`.

Libraries should never have env-loading side effects on import. Only the consuming application (kit-hub) should call `load_env()`, and it already does.
