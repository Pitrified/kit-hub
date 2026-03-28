# Various notes and fix plans

---

## e3 - Leaked semaphore objects on shutdown

### Symptom

```log
^CINFO:     Shutting down
INFO:     Waiting for application shutdown.
2026-03-28 11:14:42.437 | INFO     | kit_hub.db.session:close:114 - Closing database engine
2026-03-28 11:14:42.444 | INFO     | kit_hub.webapp.main:_lifespan:92 - Database connection closed
INFO:     Application shutdown complete.
INFO:     Finished server process [109586]
INFO:     Stopping reloader process [109581]
/home/pmn/snap/code/230/.local/share/uv/python/cpython-3.14.2-linux-x86_64-gnu/lib/python3.14/multiprocessing/resource_tracker.py:396: UserWarning: resource_tracker: There appear to be 1 leaked semaphore objects to clean up at shutdown: {'/mp-nwmp2qe0'}
  warnings.warn(
```

```log
/home/pmn/snap/code/230/.local/share/uv/python/cpython-3.14.2-linux-x86_64-gnu/lib/python3.14/multiprocessing/resource_tracker.py:396: UserWarning: resource_tracker: There appear to be 6 leaked semaphore objects to clean up at shutdown: {'/mp-j5lrabfg', '/mp-jrk768hp', '/mp-x5lul3o9', '/mp-oo49v__b', '/mp-3nwiq1sb', '/mp-fo1badcg'}
  warnings.warn(
```

### Analysis

This is a known CPython 3.14 issue with the `multiprocessing.resource_tracker`. The semaphore leak warning fires when uvicorn's reloader spawns child processes and the resource tracker detects POSIX named semaphores that were not explicitly unlinked before the process tree exits. Kit-hub's own code does not create any semaphores - the `DatabaseSession` uses async SQLAlchemy with `aiosqlite`, which does not use multiprocessing semaphores.

The likely sources are:
- **Uvicorn's `--reload` mode** uses `multiprocessing.Process` or `spawn` to fork a reloader; the semaphore is the cross-process signal.
- **SQLAlchemy's async engine dispose** may not fully clean up if the event loop shuts down before the pool drains.
- **Python 3.14 regression/strictness** - the resource tracker was made more aggressive about detecting leaks.

### Severity

Low. This is a cosmetic warning during development (`--reload`). Does not occur in production (single-process uvicorn without reloader).

### Resolution

Confirmed: running `uvicorn kit_hub.webapp.app:app` without `--reload` produces no warnings. This is a uvicorn reloader artifact - the reloader spawns a child process using `multiprocessing.spawn` and the resource tracker in CPython 3.14 reports the inter-process semaphore as leaked when the parent tears down. Kit-hub's own code is clean.

### Plan

No code changes required. Accept the warning as a known development artifact.

Optional low-priority improvement: add a `warnings.filterwarnings` call in `src/kit_hub/webapp/app.py` (guarded to dev mode only) to suppress the noise when stopping the reloader, but this is purely cosmetic and not urgent.

### Files to touch

- None required. Optionally `src/kit_hub/webapp/app.py` for a warnings filter (low priority).

---

## e4 - Raw JSON displayed after adding a recipe

### Symptom

When adding a recipe from `http://localhost:8000/recipes`, the API returns raw JSON into the `#add-recipe-body` div instead of a formatted HTML response.

```
Add a Recipe

{"id":"6f714df9-757c-4d5a-a834-6bd4b2530bef","recipe":{"name":"Ciccioli Croccanti","preparations":[{"preparation_name":"Rendering e Preparazione Base","ingredients ... all the json here ... "}]}}
```

### Analysis

The HTMX form in `templates/partials/add_recipe_form.html` does:

```html
<form hx-post="/api/v1/recipes/"
      hx-ext="json-enc"
      hx-target="#add-recipe-body"
      hx-swap="innerHTML"
      ...>
```

The API endpoint `POST /api/v1/recipes/` in `recipe_router.py` returns a `RecipeDetailResponse` Pydantic model - which FastAPI serializes as JSON. HTMX then swaps this raw JSON text into `#add-recipe-body` as `innerHTML`.

The same issue applies to `templates/partials/ingest_recipe_form.html` which targets the same div via `POST /api/v1/recipes/ingest`.

**Root cause**: HTMX expects HTML from the server. The API returns JSON. There is no HTML partial template for a "recipe created successfully" confirmation.

### Plan

Use `HX-Redirect` to send the browser to the full recipe detail page after creation. The user lands on `/recipes/{new_id}` immediately and can edit or start cooking.

1. In `recipe_router.py`, detect the `HX-Request` header on the `POST /api/v1/recipes/` and `POST /api/v1/recipes/ingest` endpoints.
2. When the request comes from HTMX, return a `Response` with status `204` (or `200`) and the `HX-Redirect: /recipes/{new_id}` header instead of the JSON body.
3. When the request is a plain API call (no `HX-Request` header), continue returning the full `RecipeDetailResponse` JSON as before.
4. No new templates or page-router endpoints needed.

### Files to touch

- `src/kit_hub/webapp/api/v1/recipe_router.py` (add HX-Redirect branch on create + ingest)
- `templates/partials/add_recipe_form.html` (no change needed - existing hx-post targets are fine)
- `templates/partials/ingest_recipe_form.html` (no change needed)

---

## e5 + e5.1 - CSP blocks inline scripts on /voice and /cook

### Symptom

Navigating to `http://localhost:8000/voice` shows in the console:

```
voice:182
Executing inline script violates the following Content Security Policy directive 'script-src 'self''.
```

Clicking `start recording session` is a no-op.

Similarly, `http://localhost:8000/cook` - move arrow buttons are blocked:

```log
cook:219
Executing inline script violates the following Content Security Policy directive 'script-src 'self''.
cook:183
Executing inline event handler violates the following Content Security Policy directive 'script-src 'self''.
```

### Analysis

The `SecurityHeadersMiddleware` in `fastapi-tools/src/fastapi_tools/middleware.py` sets:

```
script-src 'self'
```

This blocks ALL inline `<script>` tags and ALL inline event handlers (`onclick="..."`).

Affected templates:
- **`voice.html`**: has a large inline `<script>` block (IIFE wrapping session management, media recording, transcription upload, etc.) inside `{% block scripts_extra %}`.
- **`cook.html`**: has an inline `<script>` block (IIFE defining `moveRow`, `refreshRowNumbers`, `saveOrder`) inside `{% block scripts_extra %}`, PLUS inline `onclick="moveRow(...)"` attributes on the up/down buttons.
- **`navbar.html`**: has an inline `onclick="..."` on the burger menu toggle button (minor but also blocked on mobile).

### Plan

The correct approach is to move inline scripts to external `.js` files, preserving the strict CSP. This is the right security posture - do NOT weaken CSP with `'unsafe-inline'`.

**Step 1 - Extract JS to external files**:
1. Create `static/js/voice.js` - move the entire `voice.html` IIFE contents there.
2. Create `static/js/cook.js` - move the `cook.html` IIFE contents there.
3. Create `static/js/navbar.js` - move the burger toggle logic there (bind via `addEventListener` on `DOMContentLoaded`).

**Step 2 - Update templates to load external scripts**:
1. In `voice.html` `{% block scripts_extra %}`, replace inline `<script>` with `<script src="/static/js/voice.js"></script>`.
2. In `cook.html` `{% block scripts_extra %}`, replace inline `<script>` with `<script src="/static/js/cook.js"></script>`.
3. In `cook.html`, replace `onclick="moveRow(...)"` attributes with `data-recipe-id="{{ recipe.id }}"` and `data-direction="-1"` / `data-direction="1"` attributes. The external JS uses event delegation on the table to handle clicks.
4. In `navbar.html`, replace `onclick="..."` with a class or `data-*` attribute, and move the toggle logic to `navbar.js`.

**Step 3 - Include navbar.js in base.html**:
Since navbar is on every page, add `<script src="/static/js/navbar.js"></script>` to `base.html` after htmx.

**Consideration - CSRF token passing**:
`voice.js` currently reads a CSRF meta tag via `document.querySelector('meta[name="csrf-token"]')`. Since the meta tag is in the HTML (not inline JS), this works fine from an external file.

### Notes on e6 overlap

The three new JS files (`voice.js`, `cook.js`, `navbar.js`) go into `static/js/` alongside the existing `htmx-ext-json-enc.min.js`. This is the right location - no conflict with e6. The stale files being deleted in e6 (`bulma.min.css`, `htmx.min.js`, the swagger directory) are in different subdirectories and are not touched by this fix.

### Files to touch

- `static/js/voice.js` (new)
- `static/js/cook.js` (new)
- `static/js/navbar.js` (new)
- `templates/pages/voice.html` (replace inline script with external)
- `templates/pages/cook.html` (replace inline script + onclick with external + data attributes)
- `templates/partials/navbar.html` (replace onclick with data attribute)
- `templates/base.html` (add navbar.js script tag)

---

## e6 - Duplicate/stale static assets between fastapi-tools and kit-hub

### Symptom

Kit-hub's `static/` directory contains duplicate copies of vendor assets that are already served by `fastapi-tools` at `/vendor/`:

| File | kit-hub `static/` | fastapi-tools `_static/` (served at `/vendor/`) |
|------|--------------------|--------------------------------------------------|
| `bulma.min.css` | 678 KB (stale) | 207 KB (current) |
| `htmx.min.js` | 51 KB (stale) | 43 KB (current) |
| `swagger-ui-bundle.js` | 1.5 MB (same) | 1.5 MB (same) |
| `swagger-ui.css` | 177 KB (close) | 179 KB (close) |
| `redoc.standalone.js` | 940 KB (same) | 940 KB (same) |

### Analysis

`base.html` loads from `/vendor/css/bulma.min.css` and `/vendor/js/htmx.min.js` - these are the fastapi-tools bundled versions. The kit-hub `static/` copies at `/static/css/bulma.min.css` and `/static/js/htmx.min.js` are stale leftovers from before the vendor split and are NOT referenced by any template.

The `static/swagger/` directory is similarly unused - Swagger/ReDoc are mounted by fastapi-tools internally.

Only these kit-hub-specific assets in `static/` are used:
- `static/css/app.css` (loaded in `base.html`)
- `static/js/htmx-ext-json-enc.min.js` (loaded in `base.html`)
- `static/img/logo.svg` (referenced in navbar)

### Confirmed: the `/vendor/` mount is fully self-contained

Investigation of the fastapi-tools repo confirms:

- The vendor assets live at `src/fastapi_tools/_static/` inside the package source.
- Hatchling automatically includes all non-Python files within the `packages = ["src/fastapi_tools"]` directory when building the wheel - no `MANIFEST.in` or extra config needed.
- `factory.py` resolves the path at import time: `_VENDOR_STATIC = Path(__file__).parent / "_static"` and mounts it at `/vendor/`.
- kit-hub pulls fastapi-tools as a git dependency (`git+https://github.com/Pitrified/fastapi-tools@v0.1.0`); the `_static/` directory is present in the installed package and `/vendor/` just works.

It is therefore safe to delete the stale duplicates from kit-hub's `static/` directory.

### Plan

1. Delete stale files from `kit-hub/static/`:
   - `static/css/bulma.min.css` (replaced by `/vendor/css/bulma.min.css`)
   - `static/js/htmx.min.js` (replaced by `/vendor/js/htmx.min.js`)
   - `static/swagger/redoc.standalone.js`
   - `static/swagger/swagger-ui-bundle.js`
   - `static/swagger/swagger-ui.css`
   - `static/swagger/` directory
2. Verify no template references `/static/css/bulma.min.css`, `/static/js/htmx.min.js`, or `/static/swagger/*` - they should all use `/vendor/` paths.
3. Update `scripts/webapp/cdn_load.sh` to clarify that vendor assets come from fastapi-tools and no download is needed.
4. Check `.gitignore` - if the stale files were tracked in git, they need to be untracked.

### Files to touch

- Delete `static/css/bulma.min.css`
- Delete `static/js/htmx.min.js`
- Delete `static/swagger/` (entire directory)
- `scripts/webapp/cdn_load.sh` (update comment/docs)
- Possibly `.gitignore` (untrack deleted files if they are currently tracked)

---

## e7 - Chrome DevTools `.well-known` 404

### Symptom

```log
INFO:     127.0.0.1:52568 - "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 Not Found
```

### Analysis

This is Chrome (v128+) automatically requesting `/.well-known/appspecific/com.chrome.devtools.json` from every site when DevTools is open. It is a browser-initiated request, not a bug in kit-hub. The 404 is expected and harmless.

### Severity

None. This is purely cosmetic log noise during development.

### Plan

No action. This is a Chrome feature probe; the 404 is correct and expected behaviour. Zero user impact.

### Files to touch

None.

---

## e8 - Edit step button returns 404

### Symptom

On `http://localhost:8000/recipes/{id}`, clicking `Edit step` triggers:

```log
htmx.min.js:1  GET http://localhost:8000/pages/partials/edit-recipe-form/6f714df9-757c-4d5a-a834-6bd4b2530bef 404 (Not Found)
```

### Analysis

The `recipe_detail.html` template contains:

```html
<button class="button is-warning is-light is-small"
        hx-get="/pages/partials/edit-recipe-form/{{ row.id }}"
        hx-target="#edit-panel"
        hx-swap="innerHTML">
  Edit step
</button>
```

This expects a `GET /pages/partials/edit-recipe-form/{recipe_id}` endpoint to return an HTML form partial. Examination of `pages_router.py` shows this endpoint does **not exist**. The existing partials are:
- `GET /pages/partials/user-card`
- `GET /pages/partials/add-recipe-form`
- `GET /pages/partials/ingest-recipe-form`

There is no `edit-recipe-form` partial endpoint and no corresponding template.

### Plan

1. **Create the partial template** `templates/partials/edit_recipe_form.html`:
   - Renders a form with a textarea pre-filled with the current step text.
   - Includes a field for the natural-language correction instruction.
   - Uses `hx-post="/api/v1/recipes/{recipe_id}/edit"` (which already exists in `recipe_router.py`) with `hx-ext="json-enc"`.
   - The form should include fields for `step_reference` (which step to edit) and `correction` (the instruction).
   - On success, swap the updated recipe detail into the page (or redirect to the refreshed detail page via `HX-Redirect`).

2. **Create the pages router endpoint** in `pages_router.py`:
   - `GET /pages/partials/edit-recipe-form/{recipe_id}`
   - Fetches the recipe from DB via `RecipeCRUDService`
   - Renders `partials/edit_recipe_form.html` with the recipe data

3. **Edit scope UX**: keep the main recipe page clean with a single "Edit recipe" button (already in the header). When clicked, the edit form loads into `#edit-panel` and presents:
   - A grouped dropdown (or `<optgroup>` select) listing all preparations and their steps, so the user can pick exactly which step to edit even when there are multiple preparations.
   - A free-text textarea for the natural-language correction instruction.
   This avoids cluttering each step row with an inline edit button and makes the partial reusable for any step across any preparation.

4. **Edit response**: the HTMX form should `POST` to a new pages-layer endpoint (e.g. `POST /pages/recipes/{recipe_id}/edit`) rather than directly to the API. That endpoint calls `RecipeCRUDService` / the LLM editor, then returns a `Response` with `HX-Redirect: /recipes/{recipe_id}` so the browser navigates to the refreshed recipe detail page. The underlying API endpoint (`POST /api/v1/recipes/{recipe_id}/edit`) stays as-is for programmatic clients.

### Files to touch

- `templates/partials/edit_recipe_form.html` (new - step selector + correction textarea)
- `src/kit_hub/webapp/routers/pages_router.py` (new GET endpoint for the partial + new POST endpoint that calls the editor and returns HX-Redirect)
- `templates/pages/recipe_detail.html` (verify edit button placement; no structural changes expected)
