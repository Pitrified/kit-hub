# Various fixes

## e9

all recipes show `sort #0` in the recipe detail page and in the recipe list page

## e10

in the action for mkdocs there is a strict mode which causes the build to fail if there are warnings, which seems incredibly restrictive
disable that and hope the build will succeed, and if it doesn't then we can fix the warnings instead of just ignoring them

## e11

we see env loading from too many places
the dependencies should not autoload env (look at `fastapi-tools` where it was disabled fora similar reason)

```log
2026-03-28 12:54:31.983 | DEBUG    | kit_hub.params.load_env:load_env:15 - Loaded environment variables from /home/pmn/cred/kit-hub/.env
2026-03-28 12:54:32.366 | DEBUG    | llm_core.params.load_env:load_env:15 - Loaded environment variables from /home/pmn/cred/llm-core/.env
2026-03-28 12:54:36.038 | DEBUG    | media_downloader.params.load_env:load_env:17 - .env file not found at /home/pmn/cred/media-downloader/.env
```
