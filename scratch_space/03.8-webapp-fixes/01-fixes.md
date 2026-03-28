# Webapp errors

## e1 - 404 on ingest form partial

status: solved

```log
2026-03-28 02:41:27.088 | INFO | GET /pages/partials/ingest-recipe-form from 127.0.0.1
2026-03-28 02:41:27.089 | INFO | GET /pages/partials/ingest-recipe-form -> 404 (1.11ms)
```

### Root cause

The route `/pages/partials/ingest-recipe-form` did not exist in `pages_router.py`.
Similarly, `/pages/partials/add-recipe-form` was missing. Both were referenced in the
recipe page template via `hx-get` but were never registered.

### Fix

1. Added two routes to `src/kit_hub/webapp/routers/pages_router.py`:
   - `GET /pages/partials/add-recipe-form` → renders `partials/add_recipe_form.html`
   - `GET /pages/partials/ingest-recipe-form` → renders `partials/ingest_recipe_form.html`
2. Created the two partial templates:
   - `templates/partials/add_recipe_form.html` - textarea form posting JSON to `POST /api/v1/recipes/`
   - `templates/partials/ingest_recipe_form.html` - URL input form posting JSON to `POST /api/v1/recipes/ingest`
3. Both forms use `hx-ext="json-enc"` (see e2 below - the extension must be loaded separately).

---

## e2 - 422 on POST /api/v1/recipes/ingest

status: solved

```log
2026-03-28 03:14:53.802 | INFO | POST /api/v1/recipes/ingest from 127.0.0.1
2026-03-28 03:14:53.806 | INFO | POST /api/v1/recipes/ingest -> 422 (4.08ms)
```

Pasted: `https://www.instagram.com/reel/DV7QKUGgduS`

### Root cause

The ingest form uses the HTMX `json-enc` extension (`hx-ext="json-enc"`) to send the URL
as a JSON body: `{"url": "https://..."}`. The FastAPI endpoint expects exactly this format
via its `RecipeIngestRequest(BaseModel)` Pydantic body.

However, the `json-enc` extension JavaScript file was never loaded. Without it, HTMX
silently falls back to sending `application/x-www-form-urlencoded` (`url=https%3A%2F%2F...`),
which FastAPI cannot validate against a JSON body model - hence 422.

The 4ms response time confirmed it was a body validation failure (not a pipeline error -
actual Instagram ingestion takes several seconds).

The `json-enc` extension is NOT bundled with htmx itself. It must be downloaded and served
separately. It is also not included in fastapi-tools' vendored assets.

### Fix

1. Downloaded the extension from unpkg and saved it as a vendored static asset:
   ```bash
   curl -sL https://unpkg.com/htmx-ext-json-enc@2.0.1/json-enc.js \
       -o static/js/htmx-ext-json-enc.min.js
   ```
   Version `2.0.1` matches htmx `2.0.4` (the version vendored in `static/js/htmx.min.js`).

2. Added the script tag to `templates/base.html` immediately after the htmx script:
   ```html
   <script src="/vendor/js/htmx.min.js"></script>
   <script src="/static/js/htmx-ext-json-enc.min.js"></script>
   ```

3. Patched `static/js/htmx-ext-json-enc.min.js` to fix an htmx 2.x incompatibility (see e3).

With the extension loaded, any element bearing `hx-ext="json-enc"` will have its form
parameters serialized as `Content-Type: application/json` before the request is sent.

---

## e3 - htmx-ext-json-enc TypeError with htmx 2.x

status: solved

```log
# browser console
TypeError: parameters.forEach is not a function
    at Object.encodeParameters (htmx-ext-json-enc.min.js:19:18)

# server log (from RequestValidationError handler added for debugging)
content-type: application/json | errors: [{'type': 'json_invalid', 'loc': ('body', 0),
  'msg': 'JSON decode error', 'input': {}, 'ctx': {'error': 'Expecting value'}}]
```

### Root cause

The downloaded `htmx-ext-json-enc@2.0.1` has a bug with htmx 2.x. Its `encodeParameters`
callback calls `parameters.forEach(...)`, which assumes `parameters` is a `FormData` object
(htmx 1.x behaviour). In htmx 2.x, htmx passes a plain JS `Object {}` instead of `FormData`.
Plain objects do not have a `.forEach` method, so the callback throws, the JSON body is
never built, and the server receives an empty body - which Pydantic rejects as
`JSON decode error`.

The result: `Content-Type: application/json` was correctly set (the `onEvent` handler ran
first), but the body was empty, giving the server a valid JSON content-type with no parseable
payload.

The `RequestValidationError` handler added to `main.py` for debugging exposed this - the
content-type WAS json, confirming the extension was at least partially active.

### Fix

Patched `static/js/htmx-ext-json-enc.min.js` to handle both the htmx 1.x path (FormData,
which has `.forEach`) and the htmx 2.x path (plain Object, which needs `Object.entries`):

```javascript
if (typeof parameters.forEach === 'function') {
  // FormData path (htmx 1.x / some htmx 2.x configurations)
  parameters.forEach(function(value, key) { addEntry(key, value) })
} else {
  // Plain-object path (htmx 2.x default)
  Object.entries(parameters).forEach(function(entry) { addEntry(entry[0], entry[1]) })
}
```

The file is a local vendored copy, so the patch persists. No CDN dependency.
