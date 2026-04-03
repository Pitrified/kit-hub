# Various fixes

## show sources

* save and show instagram urls
* save and show raw voice notes
* save and show transcript of the videos
* save and show original text pasted in

## recording session

what is the point of freezing the session? can it be restarted later? from where

## footer

footer should be fixed at the bottom of the page

## delete button

in `http://localhost:8000/recipes`
delete button is small and at the top of the box, should be centered like `view`

## filter recipes

filter recipes by source, date, type, etc. and show the filters applied
both in the recipes page and in the cook queue
in the queue, if you filter, what happens to the sorting? does it skip up over the other filtered one?

## recipe edit

you can also update notes and other fields, basically everything
also can split/merge steps/preparations, both llm based and manual
also can edit title, tags, etc.

---

## Plan: UI fixes and recipe source tracking

Six features across DB, backend, and frontend layers. Steps are ordered by dependency; features 3-4 are independent of 1-2 and can be parallelized.

### Step 1 - Add source metadata columns to DB

Add an `original_url` (nullable text) and `raw_input_text` (nullable text) column to `RecipeRow` in `src/kit_hub/db/models.py`. Create an Alembic migration.

- `original_url`: full Instagram URL (or any future URL source). Currently only the shortcode lives in `source_id`.
- `raw_input_text`: the exact text that was fed to the LLM transcriber - Instagram caption+transcript, voice session `to_string()` output, or manual pasted text.

Voice audio clips are not persisted with the recipe. Only the timestamped transcript text (from `RecipeNote.to_string()`) is stored in `raw_input_text`.

Files:
- `src/kit_hub/db/models.py` - add `original_url: Mapped[str | None]`, `raw_input_text: Mapped[str | None]`
- `src/kit_hub/db/migrations/versions/` - new Alembic migration
- `src/kit_hub/db/crud_service.py` - extend `create_recipe()` signature with `original_url` and `raw_input_text` params

### Step 2 - Persist source metadata during ingestion

Thread the new fields through all three creation paths.

**Instagram** (`src/kit_hub/ingestion/ingest_service.py`):
- Pass `original_url=url` (the full Instagram URL from the request) to `create_recipe()`
- Pass `raw_input_text=combined_text` (the caption+transcript string built by `_build_text()`)

**Voice** (`src/kit_hub/voice/voice_to_recipe.py` and `src/kit_hub/webapp/api/v1/voice_router.py`):
- Pass `raw_input_text=recipe_note.to_string()` when converting session to recipe

**Manual** (`src/kit_hub/webapp/api/v1/recipe_router.py` create endpoint):
- Pass `raw_input_text=request.text` (the pasted text)

### Step 3 - Show source info on recipe detail page

Add a "Source" section to `templates/pages/recipe_detail.html` that renders:

- **Instagram**: clickable link to `original_url` (reconstructed as `https://www.instagram.com/p/{source_id}/` for older recipes where `original_url` is null). Show `raw_input_text` in a collapsible `<details>` block labelled "Original caption & transcript".
- **Voice note**: show `raw_input_text` (the timestamped transcript) in a collapsible block labelled "Voice transcript".
- **Manual**: show `raw_input_text` in a collapsible block labelled "Original text".

Files:
- `templates/pages/recipe_detail.html` - new source section
- `src/kit_hub/webapp/routers/pages_router.py` - pass `original_url` and `raw_input_text` to template context

### Step 4 - Fix footer to stick to page bottom

The Bulma `.footer` is a normal flow element. On short pages it floats mid-screen.

Add a sticky-footer layout to `app.css` using flexbox on `body`:

```css
body {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

main#main-content {
  flex: 1;
}
```

No changes to `templates/partials/footer.html` or `templates/base.html` needed - the existing structure already has `<body>` > `<main>` > `<footer>`.

Files:
- `static/css/app.css` (kit-hub)
- `/home/pmn/repos/python-project-template/static/css/app.css` - apply the same sticky-footer CSS for consistency across projects. The template repo has an identical `body > main > footer` structure in `base.html` and the same `app.css` baseline.
- look for this same pattern in other projects and apply the sticky footer CSS as needed, all projects share `app.css` started from the template repo.

### Step 5 - Fix delete button alignment in recipe cards

The delete `<button>` in the card footer uses `button is-ghost is-small` which renders smaller than the `<a>` View link. Both are `card-footer-item` elements but the button's `is-small` class shrinks it.

Remove `is-small` from the delete button and remove `button is-ghost` (a `card-footer-item` already handles styling). Use a plain `<span>` or keep it as a `<button>` but style it to match the `<a>`:

```html
<button class="card-footer-item has-text-danger"
        hx-delete="/api/v1/recipes/{{ recipe.id }}"
        hx-confirm="Delete '{{ recipe.name }}'? This cannot be undone."
        hx-target="#recipe-card-{{ recipe.id }}"
        hx-swap="outerHTML swap:0.3s">
  Delete
</button>
```

Add a small CSS reset so button card-footer-items match anchor card-footer-items:

```css
button.card-footer-item {
  background: none;
  border: none;
  cursor: pointer;
  font-size: inherit;
}
```

Files:
- `templates/pages/recipes.html`
- `static/css/app.css`

### Step 6 - Add unfreeze/resume to voice sessions

Currently `VoiceSessionManager.freeze_session()` sets `frozen=True` permanently and `append_audio()` raises `FrozenSessionError`.

Add an `unfreeze_session(session_id)` method that sets `frozen=False`. Expose it as `POST /api/v1/voice/{session_id}/unfreeze`. Add an "Unfreeze" button to `templates/pages/voice.html` that appears when a session is frozen (next to the "Convert to Recipe" button).

Add a "Frozen Sessions" panel to the voice page. `VoiceSessionManager.list_sessions()` already exists. Add a `list_frozen_sessions()` variant (or filter by frozen state) and render a table/list on `voice.html` showing each frozen session with its `start_timestamp`, note count, and three action buttons:
- **Resume** - calls `POST /api/v1/voice/{session_id}/unfreeze`, then switches the UI to that session for continued dictation.
- **Convert to Recipe** - calls `POST /api/v1/voice/{session_id}/to-recipe`.
- **Delete** - calls a new `DELETE /api/v1/voice/{session_id}` endpoint that removes the session from memory and disk.

The panel loads on page load (server-rendered) and refreshes after any action via HTMX.

Files:
- `src/kit_hub/voice/voice_session.py` - add `unfreeze_session()`, `delete_session()`, `list_frozen_sessions()` methods
- `src/kit_hub/webapp/api/v1/voice_router.py` - add `POST /voice/{session_id}/unfreeze`, `DELETE /voice/{session_id}`, `GET /voice/sessions` (list frozen)
- `templates/pages/voice.html` - frozen sessions panel + unfreeze/delete/convert buttons
- `static/js/voice.js` - handle unfreeze, delete, convert clicks; reload frozen session list after actions

### Step 7 - Filter recipes by source, date, and meal course

**Backend** - extend `list_recipes()` in `src/kit_hub/db/crud_service.py` with optional filter params: `source: RecipeSource | None`, `meal_course: MealCourse | None`, `created_after: datetime | None`, `created_before: datetime | None`. Apply as SQLAlchemy `.where()` clauses.

Propagate filters through:
- `GET /api/v1/recipes/` query params
- `GET /recipes` page route (pass to template)
- `GET /cook` page route (pass to template)

**Frontend - recipes page** (`templates/pages/recipes.html`):
- Add a filter bar above the card grid with dropdowns for source (Instagram/Voice/Manual/All), meal course (enum values + All), and a date range picker (or simple "Last 7 days / 30 days / All").
- Show active filters as removable tags.
- Filters round-trip as query params: `?source=instagram&meal_course=primi&page=1`.

**Frontend - cook queue** (`templates/pages/cook.html`):
- Same filter bar above the table.
- Filtered view shows original sort positions (not compact re-numbering). The `#` column displays the recipe's actual `sort_index`, so filtered-out items create visible gaps.
- Move buttons still work within the filtered set - they swap positions in the full sort order, not the filtered view. The save endpoint receives all recipe IDs including non-visible ones.

**Text search** - add a `search: str | None` query param alongside the other filters. Backend applies `ilike(f"%{search}%")` on `RecipeRow.name`. Frontend renders a text input above the filter dropdowns. On the recipes page, use HTMX `hx-trigger="keyup changed delay:300ms"` to re-fetch the card grid as the user types (debounced 300ms). On the cook queue, same pattern but target the table body. The search param round-trips in query params like the other filters: `?search=pasta&source=instagram`.

Files:
- `src/kit_hub/db/crud_service.py` - filter params on `list_recipes()` including `search`
- `src/kit_hub/webapp/api/v1/recipe_router.py` - query params on list endpoint
- `src/kit_hub/webapp/routers/pages_router.py` - pass filters to both pages; add HTMX partial endpoints for live search
- `templates/pages/recipes.html` - search input + filter bar
- `templates/pages/cook.html` - search input + filter bar
- `static/css/app.css` - filter bar styling (if needed)
- `static/js/cook.js` - adapt sorting to handle filtered views

### Step 8 - Full recipe editing (manual + LLM-assisted)

Two editing modes on the recipe detail page.

**Manual inline editing:**
- Make recipe name, notes, ingredients, and steps editable inline. Use `contenteditable` or switch to input fields on an "Edit" toggle.
- Add/remove ingredients and steps with + / x buttons.
- Add/remove/rename preparations.
- Edit tags (add/remove, toggle ai/manual origin).
- Edit meal course via dropdown.
- "Save" button sends `PUT /api/v1/recipes/{recipe_id}` with the full updated `RecipeCore`.

**LLM-assisted editing (extend current):**
- Current edit form targets one step. Extend it to also handle:
  - Ingredient corrections ("change 200g flour to 250g")
  - Preparation-level changes ("merge the sauce and pasta sections")
  - Split a step into multiple steps
  - Merge consecutive steps
- The `RecipeCoreEditor` prompt (in `llm-core`) may need a new version (`v2.jinja`) that accepts broader edit instructions beyond single-step corrections.
- `SectionIdxFinder` already maps natural-language references to indices.

**UI flow:**
- Recipe detail page gets a persistent "Edit mode" toggle in the header.
- In edit mode, all fields become editable. A floating action bar shows "Save", "Cancel", and "AI Edit" (opens the LLM correction form).
- The LLM form dropdown expands from "steps only" to "steps, ingredients, preparations, or full recipe".

Files:
- `templates/pages/recipe_detail.html` - inline edit mode, expanded LLM form
- `templates/partials/edit_recipe_form.html` - broader edit targets
- `src/kit_hub/webapp/api/v1/recipe_router.py` - ensure `PUT` handles full `RecipeCore`
- `src/kit_hub/webapp/routers/pages_router.py` - extend page edit endpoint
- `src/kit_hub/llm/editor.py` - support broader edit scope
- `src/kit_hub/llm/prompts/editor/v2.jinja` - new prompt version for full edits
- `static/js/` - new `recipe-edit.js` for inline editing logic
- `static/css/app.css` - edit mode styling

### Notes

1. Step 1-2 (DB + ingestion) must land before step 3 (show sources). Steps 4-6 are independent and can ship first.
2. Existing recipes will have `NULL` for `original_url` and `raw_input_text`. The detail template must handle this gracefully (fallback to reconstructing Instagram URL from shortcode, or "Source text not available").
3. The migration should be non-destructive (nullable columns, no data loss).
4. Step 7 (filters) and step 8 (editing) are independent of each other and of steps 1-6.
5. Step 8 is the largest feature. Consider splitting into sub-PRs: (a) manual inline editing of name/notes/tags, (b) inline ingredient/step editing, (c) preparation split/merge, (d) expanded LLM editor.
6. Cook queue filtering with original sort positions means the JS sort logic needs updating - `saveOrder()` must reconstruct the full ordered list (including hidden recipes) before POSTing.
7. The HTMX live search on recipes/cook pages needs a partial template variant (just the card grid or table body) to swap in results without a full page reload. Consider extracting the grid/tbody into a dedicated partial.
