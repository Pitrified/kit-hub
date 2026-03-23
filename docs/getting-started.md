# Getting Started

This guide will help you set up your development environment and get started with Kit Hub.

## Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) package manager
- An OpenAI API key (for LLM-based recipe parsing and Whisper transcription)
- A Google OAuth client ID and secret (for user authentication)

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Pitrified/kit-hub.git
cd kit-hub
```

### 2. Install Dependencies

```bash
# Install all dependencies (including dev tools and webapp)
uv sync --all-extras --all-groups

# Or install specific groups
uv sync --group test    # Testing only
uv sync --group lint    # Linting only
uv sync --group docs    # Documentation only
```

### 3. Configure Environment Variables

Create a credentials file at `~/cred/kit-hub/.env`. See [`nokeys.env`](https://github.com/Pitrified/kit-hub/blob/main/nokeys.env) for the required variable names.

```bash
mkdir -p ~/cred/kit-hub
cp nokeys.env ~/cred/kit-hub/.env
# then fill in real values
```

For VSCode, add to `.vscode/settings.json`:

```json
{
  "python.envFile": "/home/YOUR_USER/cred/kit-hub/.env"
}
```

### 4. Verify Installation

```bash
# Run tests
uv run pytest

# Check code style
uv run ruff check .

# Type checking
uv run pyright
```

## Running the Webapp

```bash
uvicorn kit_hub.webapp.app:app --reload
```

The app will be available at `http://localhost:8000`.

## Development Workflow

### Running Tests

```bash
uv run pytest
uv run pytest -v              # Verbose output
uv run pytest tests/config/   # Run specific test directory
```

### Code Quality

```bash
# Lint and format
uv run ruff check .
uv run ruff format .

# Type checking
uv run pyright
```

### Pre-commit Hooks

Pre-commit hooks are configured to run automatically on each commit:

```bash
# Install hooks (first time only)
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files
```

## Building Documentation

```bash
# Start local server with hot reload
uv run mkdocs serve

# Build static site
uv run mkdocs build
```
