# Kit Hub

Personal recipe management application. Centralises recipe discovery, ingestion, LLM-based parsing, voice note dictation, and browsing in a single FastAPI monolith.

Built on [`llm-core`](https://github.com/Pitrified/llm-core) for LLM pipelines, [`media-downloader`](https://github.com/Pitrified/media-downloader) for Instagram/video ingestion, and [`fastapi-tools`](https://github.com/Pitrified/fastapi-tools) for the web layer.

## Installation

### Setup `uv`

Setup [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

### Install the package

Run the following command:

```bash
uv sync --all-extras --all-groups
```

## Docs

Docs are available at [https://pitrified.github.io/kit-hub/](https://pitrified.github.io/kit-hub/).

## Setup

### Environment Variables

Create a `.env` file at `~/cred/kit-hub/.env`. See [`nokeys.env`](nokeys.env) for the required variable names.

For VSCode to recognise the environment file, add the following to the workspace [settings file](.vscode/settings.json):

```json
"python.envFile": "/home/pmn/cred/kit-hub/.env"
```

### Pre-commit

To install the pre-commit hooks, run the following command:

```bash
pre-commit install
```

Run against all the files:

```bash
pre-commit run --all-files
```

### Linting

Use pyright for type checking:

```bash
uv run pyright
```

Use ruff for linting:

```bash
uv run ruff check --fix
uv run ruff format
```

### Testing

To run the tests, use the following command:

```bash
uv run pytest
```

or use the VSCode interface.

## Features

- Recipe data model (`RecipeCore`, `Preparation`, `Ingredient`, `Step`)
- Instagram ingestion via `media-downloader` (scrape, download, cache)
- LLM-based recipe parsing (`RecipeCoreTranscriber`) and step editing (`RecipeCoreEditor`) via `llm-core`
- Live voice note sessions with Whisper transcription while cooking
- Google OAuth authentication with recipe ownership
- Cook-soon sort queue with drag-and-drop reordering
