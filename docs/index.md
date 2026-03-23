# Kit Hub

Welcome to the **Kit Hub** documentation.

Kit Hub is a personal recipe management application that centralises recipe discovery, ingestion, LLM-based parsing, voice note dictation, and browsing in a single FastAPI monolith.

## Features

- **Recipe data model**: `RecipeCore`, `Preparation`, `Ingredient`, `Step` - a clean Pydantic schema shared across all layers
- **Instagram ingestion**: import recipes from Instagram posts via `media-downloader` (scrape, download, cache)
- **LLM parsing**: `RecipeCoreTranscriber` converts free text (caption, voice transcript, paste) into a structured `RecipeCore` via `llm-core`
- **LLM editing**: `RecipeCoreEditor` + `SectionIdxFinder` apply natural-language corrections to individual steps
- **Voice notes**: dictate recipes while cooking; each audio clip is transcribed with Whisper and appended to a timestamped `RecipeNote` session
- **Cook-soon queue**: drag-and-drop sort order persisted per user
- **Auth**: Google OAuth with recipe ownership and public/private toggle

## Quick Start

```bash
# Install dependencies
uv sync --all-extras --all-groups

# Run tests
uv run pytest

# Start the webapp
uvicorn kit_hub.webapp.app:app --reload

# Start documentation server
uv run mkdocs serve
```

## Project Structure

```
kit-hub/
├── src/kit_hub/         # Main application code
│   ├── config/          # Pydantic config models
│   ├── data_models/     # BaseModelKwargs
│   ├── db/              # SQLAlchemy ORM, CRUD, migrations
│   ├── ingestion/       # Instagram ingestion pipeline
│   ├── llm/             # RecipeCoreTranscriber, editor, finder
│   ├── metaclasses/     # Singleton
│   ├── params/          # KitHubParams, paths, env type
│   ├── recipes/         # RecipeCore and related Pydantic models
│   ├── voice/           # Voice note session
│   └── webapp/          # FastAPI app, routers, auth
├── tests/               # Test suite
├── docs/                # Documentation (you are here)
└── scratch_space/       # Experimental notebooks
```

## Next Steps

- [Getting Started](getting-started.md) - Set up your development environment
- [Guides](guides/uv.md) - Learn about the tools used in this project
- [API Reference](reference/) - Explore the codebase
- [Contributing](contributing.md) - How to contribute to this project
