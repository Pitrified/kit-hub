# Block 6: Telegram bot

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md), [03-db-layer.md](03-db-layer.md), [04-llm-chains.md](04-llm-chains.md), [05-ingestion.md](05-ingestion.md), [06-voice-notes.md](06-voice-notes.md)

## Goal

Build the Telegram bot as the first UI for kit-hub using `python-telegram-bot` (PTB v22+) with `ApplicationBuilder`. The bot provides the primary way to interact with kit-hub initially: paste IG URLs to ingest recipes, send voice messages to build voice notes, browse recipes, and manage the cook-soon queue.

## Source material

- `tg-central-hub-bot`: `BotParams`, `BotConfig`, `ApplicationBuilder` pattern, command handler structure
- `recipamatic`: voice note API flow, IG ingestion flow

## Design

The bot is a long-running process (polling mode) that has direct access to all kit-hub services. No HTTP API needed between the bot and the backend - they share the same process and Python objects.

```
Telegram API
  -> python-telegram-bot (PTB)
    -> Command/Message handlers
      -> IngestService (IG URLs)
      -> VoiceSessionManager (voice messages)
      -> RecipeCRUDService (browse, sort)
      -> VoiceToRecipeConverter (finalize voice sessions)
```

### Bot entry point

A single script that:
1. Loads env + params
2. Initializes DB, services
3. Builds the PTB Application
4. Registers all handlers
5. Runs polling

### Conversation flows

**IG ingestion** (simplest):
1. User sends a message containing an Instagram URL
2. Bot detects the URL, replies "Downloading..."
3. `IngestService.ingest_ig_url()` runs
4. Bot replies with a formatted recipe card (name, ingredients summary, step count)
5. On error, bot replies with error message

**Voice note session**:
1. User sends `/voice` to start a session
2. Bot creates a session via `VoiceSessionManager.create_session()`
3. User sends voice messages (Telegram `.ogg` files)
4. For each voice message: bot downloads the file, calls `VoiceSessionManager.append_audio()`, replies with the transcribed text
5. User sends `/done` to freeze the session
6. Bot calls `VoiceToRecipeConverter.convert()` and replies with the structured recipe
7. User can `/save` to persist or `/discard` to drop

**Browse recipes**:
1. `/recipes` shows recent recipes as a list (inline keyboard with pagination)
2. Tapping a recipe shows the full detail (name, preparations, ingredients, steps)
3. Long messages split across multiple Telegram messages if needed

**Cook-soon queue**:
1. `/cook` shows the current queue (ordered by `sort_index`)
2. Inline keyboard buttons: move up, move down, remove from queue
3. `/cook add` adds a recipe to the queue (search by name)

**Manual recipe entry**:
1. `/recipe` followed by free text
2. Bot parses via `RecipeCoreTranscriber` and replies with the structured result
3. User can `/save` or provide corrections

## Deliverables

### 1. Bot config - `src/kit_hub/config/bot_config.py`

```python
class BotConfig(BaseModelKwargs):
    token: SecretStr
    parse_mode: str = "HTML"
```

### 2. Bot params - `src/kit_hub/params/bot_params.py`

```python
class MissingBotTokenError(Exception): ...

class BotParams:
    def __init__(self, env_type: EnvType | None = None): ...
    def to_config(self) -> BotConfig: ...
    # Reads BOT_TOKEN from env; raises MissingBotTokenError if absent
    # Token stored as SecretStr, masked in __str__
```

### 3. Bot application builder - `src/kit_hub/bot/bot_app.py`

```python
class KitHubBot:
    """Build and configure the Telegram bot application."""

    def __init__(
        self,
        bot_config: BotConfig,
        ingest_service: IngestService,
        voice_manager: VoiceSessionManager,
        voice_converter: VoiceToRecipeConverter,
        crud: RecipeCRUDService,
    ): ...

    def build(self) -> Application:
        """Create PTB Application, register all handlers, return it."""
        ...

    def _register_handlers(self, app: Application) -> None:
        """Register command + message handlers."""
        ...
```

### 4. Command handlers - `src/kit_hub/bot/handlers/`

Each handler is a module with async handler functions:

**`start.py`**:
- `/start` - welcome message with command list
- `/help` - same as start

**`ingest.py`**:
- Message handler: detect Instagram URLs in any message
- `/ingest <url>` - explicit ingest command
- Both trigger `IngestService.ingest_ig_url()`

**`voice.py`**:
- `/voice` - start voice session
- Voice message handler: download `.ogg`, call `VoiceSessionManager.append_audio()`
- `/done` - freeze session and convert to recipe
- `/save` - persist the converted recipe
- `/discard` - drop the session
- Uses PTB `ConversationHandler` for stateful flow

**`browse.py`**:
- `/recipes` - list recipes with inline keyboard pagination
- Callback query handler for pagination and recipe detail view

**`sort.py`**:
- `/cook` - show cook-soon queue
- Inline keyboard: move up/down, add/remove from queue
- Callback query handler for reordering

**`manual.py`**:
- `/recipe <text>` - parse free text into recipe
- `/save` / `/discard` for the result

### 5. Message formatting - `src/kit_hub/bot/formatting.py`

```python
def format_recipe_card(recipe: RecipeCore) -> str:
    """Format a recipe as a compact Telegram message (HTML)."""
    ...

def format_recipe_detail(recipe: RecipeCore) -> list[str]:
    """Format full recipe detail. May return multiple messages if too long."""
    # Telegram message limit is 4096 chars
    ...

def format_recipe_list(recipes: list[RecipeRow], page: int, total: int) -> str:
    """Format a paginated recipe list."""
    ...

def format_voice_note(note: Note) -> str:
    """Format a single transcribed voice note."""
    ...
```

### 6. Bot entry point - `src/kit_hub/bot/run.py`

```python
def run_bot() -> None:
    """Entry point: load config, build services, start polling."""
    load_env()
    params = get_kit_hub_params()
    # init DB, services, bot
    # app.run_polling()
```

Also exposed as a script in `pyproject.toml`:
```toml
[project.scripts]
kit-hub-bot = "kit_hub.bot.run:run_bot"
```

## Tasks

- [ ] Create `src/kit_hub/config/bot_config.py`
- [ ] Create `src/kit_hub/params/bot_params.py` with `MissingBotTokenError`
- [ ] Wire `BotParams` into `KitHubParams`
- [ ] Create `src/kit_hub/bot/` package
- [ ] Implement `bot_app.py` - `KitHubBot` builder
- [ ] Implement `handlers/start.py`
- [ ] Implement `handlers/ingest.py` - IG URL detection + ingestion
- [ ] Implement `handlers/voice.py` - ConversationHandler for voice sessions
- [ ] Implement `handlers/browse.py` - recipe list + detail with pagination
- [ ] Implement `handlers/sort.py` - cook-soon queue management
- [ ] Implement `handlers/manual.py` - free text recipe entry
- [ ] Implement `formatting.py` - Telegram message formatting
- [ ] Implement `run.py` entry point
- [ ] Add `python-telegram-bot` dependency to `pyproject.toml`
- [ ] Write tests with mocked bot context for each handler
- [ ] Write tests for formatting functions
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
