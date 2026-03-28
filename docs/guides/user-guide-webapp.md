# Webapp User Guide

This guide walks through using the kit-hub web application for managing
recipes, reordering the cook-soon queue, and recording voice notes.

## Starting the server

Install webapp dependencies and start the development server:

```bash
uv sync --extra webapp
uvicorn kit_hub.webapp.app:app --reload
```

Open `http://localhost:8000` in a browser. You will see the landing page.
Sign in with Google OAuth to access all features.

## Recipes

### Browsing recipes

Navigate to **Recipes** in the navigation bar. The page shows a card grid of
all your recipes, paginated. Each card displays the recipe name, source, and
creation date. Click a card to view the full recipe.

### Creating a recipe from text

On the Recipes page, expand the "Add Recipe" panel. Paste recipe text (from a
blog, personal notes, or any free-form source) and click **Create**. The
backend sends the text through the LLM transcriber chain, which parses it
into structured preparations, ingredients, and steps. The new recipe appears
in the list.

### Ingesting from Instagram

In the "Add Recipe" panel, paste a public Instagram post URL and click
**Ingest**. The backend downloads the post content via `media-downloader`,
extracts the caption text, runs it through the LLM transcriber, and persists
the structured recipe.

### Viewing recipe detail

Click any recipe card to open the detail page. The page shows:

- Recipe name and source
- Each preparation section with its ingredients and steps
- AI-assigned tags with confidence scores
- Edit and delete buttons

### Editing a step

On the recipe detail page, use the edit form to correct a step. Provide the
exact text of the step to fix and a natural-language description of the
desired correction. The backend uses the `RecipeCoreEditor` LLM chain to
produce a corrected recipe.

### Deleting a recipe

Click the **Delete** button on a recipe card or detail page. The recipe is
permanently removed.

## Cook-soon queue

Navigate to **Cook Queue** in the navigation bar. This page shows all recipes
sorted by priority. Use the **Up** and **Down** buttons to reorder recipes.
Click **Save Order** to persist the new sort order. The queue order is
maintained across sessions.

## Voice notes

Navigate to **Voice Note** in the navigation bar to record a live cooking
session.

### Recording workflow

1. Click **Start Session** to create a new voice recording session on the
   server.
2. Click **Record** to begin capturing audio from your microphone. The browser
   uses the `MediaRecorder` API to capture audio as `audio/webm`.
3. Click **Stop** to end the current clip. The audio is uploaded to the server,
   transcribed by Whisper, and the text appears in the transcript panel.
4. Repeat steps 2-3 for each cooking step or note.
5. Click **Freeze** to lock the session. No further audio clips can be added.
6. Click **Convert to Recipe** to send the complete transcript through the LLM
   transcriber, producing a structured recipe that is saved to the database.

### Audio format

The webapp records audio as `audio/webm` via the browser. Telegram voice
messages (supported by the voice API) use `audio/ogg`. Both formats are
accepted by the upload endpoint.

## API access

All functionality is also available through the JSON API at `/api/v1/`. Visit
`/docs` for the interactive Swagger UI or `/redoc` for the ReDoc reference.

### Authentication

All API endpoints require a valid session cookie. Obtain one by completing
the Google OAuth flow at `/auth/google`. The session cookie is automatically
set by the browser after sign-in.

### Example: list recipes

```bash
curl -b "session=YOUR_SESSION_ID" http://localhost:8000/api/v1/recipes/
```

### Example: create recipe from text

```bash
curl -X POST \
  -b "session=YOUR_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"text": "Mix flour and eggs. Knead for 10 minutes."}' \
  http://localhost:8000/api/v1/recipes/
```

### Example: start voice session

```bash
curl -X POST \
  -b "session=YOUR_SESSION_ID" \
  http://localhost:8000/api/v1/voice/create
```
