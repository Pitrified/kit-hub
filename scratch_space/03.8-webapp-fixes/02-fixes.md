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

### Plan

1. **Verify it doesn't happen in production mode**: run `uvicorn kit_hub.webapp.app:app` (no `--reload`) and confirm no leak warnings.
2. **If it persists in production**, ensure `await db.close()` calls `await engine.dispose()` explicitly before the lifespan yields back, and add a brief `await asyncio.sleep(0.1)` to let pending pool tasks settle.
3. **If it's reload-only**, suppress with a `warnings.filterwarnings("ignore", message="resource_tracker")` in the uvicorn dev entry point only, or simply document as expected.
4. **Track upstream**: check if CPython 3.14.3+ or uvicorn has a fix for this; it's a known issue in the ecosystem.

### Files to touch

- Possibly `src/kit_hub/webapp/app.py` (warnings filter for dev only)
- Possibly `src/kit_hub/db/session.py` (explicit dispose + sleep)

RESULT: with no `--reload`, the warning does not appear. This is a uvicorn dev mode artifact. Document and ignore for now.
Maybe add a filter so that we don't see the warning every time we stop the server during development, but it's not a high priority fix.

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

Two options (choose one):

**Option A - Create a success partial (recommended)**:
1. Create a new Jinja2 partial template `templates/partials/recipe_created.html` that renders a success card with the recipe name and a "View recipe" link.
2. Create new page-router endpoints (e.g. `POST /pages/recipes/add-text` and `POST /pages/recipes/ingest`) that call the service layer directly, then render the partial.
3. Update `add_recipe_form.html` to `hx-post="/pages/recipes/add-text"` and `ingest_recipe_form.html` to `hx-post="/pages/recipes/ingest"`.
4. The API endpoints stay as-is (JSON) for programmatic clients.

**Option B - Redirect after creation**:
1. Add `HX-Redirect` header in the API response when the request comes from HTMX (check `HX-Request` header).
2. Redirect to `/recipes/{new_id}` so the user sees the full detail page.
3. Simpler but less smooth UX (full page navigation instead of partial swap).

### Files to touch

- `templates/partials/recipe_created.html` (new - success partial)
- `src/kit_hub/webapp/routers/pages_router.py` (new POST endpoints for HTMX)
- `templates/partials/add_recipe_form.html` (update hx-post target)
- `templates/partials/ingest_recipe_form.html` (update hx-post target)

DECISION: option B, user will probably want to see the full recipe detail after adding, to edit it if something went wrong or cook it immediately

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

### Plan

1. **Delete stale files** from `kit-hub/static/`:
   - `static/css/bulma.min.css`
   - `static/js/htmx.min.js`
   - `static/swagger/redoc.standalone.js`
   - `static/swagger/swagger-ui-bundle.js`
   - `static/swagger/swagger-ui.css`
   - `static/swagger/` directory itself
2. **Verify no templates reference** `/static/css/bulma.min.css`, `/static/js/htmx.min.js`, or `/static/swagger/*`. They should all use `/vendor/` paths.
3. **Update `scripts/webapp/cdn_load.sh`** to document clearly that vendor assets come from fastapi-tools.
4. **Update `.gitignore`** if needed - the stale files might be tracked.

### Files to touch

- Delete `static/css/bulma.min.css`
- Delete `static/js/htmx.min.js`
- Delete `static/swagger/` (entire directory)
- Possibly update `scripts/webapp/cdn_load.sh`
- Possibly update `.gitignore`

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

Two options:

**Option A - Ignore (recommended)**:
Do nothing. This is a Chrome feature probe and the 404 is correct behavior. It has zero user impact.

**Option B - Suppress log noise**:
If the 404s are annoying in the dev logs, add a lightweight handler in fastapi-tools or kit-hub that returns an empty 204 or JSON `{}` for `/.well-known/appspecific/com.chrome.devtools.json`. This is purely cosmetic.

### Files to touch

None (Option A). Or a small route in `pages_router.py` (Option B).

DECISION: Option A, ignore

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

3. **Decide on edit scope**: The button currently sits at the recipe level (one button in the header area). Consider whether it should be per-step (next to each step) or per-recipe (one form for the whole recipe). The existing API endpoint `POST /api/v1/recipes/{recipe_id}/edit` accepts a `step_reference` + `correction`, so a per-recipe form with a step selector makes sense.
   - Analyze UX implications, what happens when there are multiple preparations and steps?
   A single `edit recipe` button that then allows selecting which preparation+step to edit, so we keep the main recipe page clean, and the edit form can be reused for any step.

4. **Handle the edit response**: The API's `POST /api/v1/recipes/{recipe_id}/edit` returns JSON (`RecipeDetailResponse`). Similar to e4, the HTMX form should either:
   - Target a pages endpoint that returns HTML, or
   - Use `HX-Redirect` to refresh the recipe detail page after edit. -> this, redirect to the recipe detail page to see the updated content.

### Files to touch

- `templates/partials/edit_recipe_form.html` (new)
- `src/kit_hub/webapp/routers/pages_router.py` (new GET endpoint)
- Possibly `src/kit_hub/webapp/routers/pages_router.py` (new POST endpoint for HTMX edit, similar to e4 plan)
- `templates/pages/recipe_detail.html` (may need adjustments to edit button placement)
