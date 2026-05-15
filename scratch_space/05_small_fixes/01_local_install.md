# Local install problems recap

## The problem

When developing across repos (e.g. using unreleased media-downloader changes in kit-hub), the local dependency install gets silently overwritten.

### Root cause

`uv run` re-syncs the environment from `uv.lock` before every command. If `pyproject.toml` points to a git tag (e.g. `media-downloader @ git+...@v0.1.2`), `uv run` will reinstall that tagged version, overwriting whatever was locally installed via `uv pip install -e`.

### What breaks

1. Run `make dev-media-downloader` (which does `uv pip install -e "../media-downloader[all]"`) - works, local changes are available.
2. Run `uv run pytest` - uv re-syncs from lockfile, reinstalls the git-tagged media-downloader, local changes are gone.
3. Tests pass or fail based on the old tagged version, not the local changes.

## The fix

After `make dev-media-downloader`, use `.venv/bin/` commands directly instead of `uv run`:

```bash
# Install local dep
make dev-media-downloader

# Run checks (NOT uv run)
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/pyright
```

## Makefile targets

The Makefile has `dev-*` targets for each local dependency:

```bash
make dev-media-downloader    # uv pip install -e "../media-downloader[all]"
```

## Key rule

**Never use `uv run` when testing with locally installed dependencies.** Always use `.venv/bin/<command>` directly.

## Possible improvements

- Add a `make test` / `make lint` / `make check` target that uses `.venv/bin/` so the pattern is easier to remember.
- Document the local dev workflow in `docs/guides/`.
- Consider using uv workspaces if/when multiple repos need to be co-developed frequently.
