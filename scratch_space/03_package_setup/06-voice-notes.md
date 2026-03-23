# Block 5: Voice note session

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md), [04-llm-chains.md](04-llm-chains.md)

## Goal

Reimplement the live cooking dictation flow. A voice session captures timestamped audio clips, transcribes each via Whisper, and stores the result as a `RecipeNote`. The session can then be converted to a clean `RecipeCore` via the LLM transcriber.

## Source material

- `recipamatic`: fully working voice note session with browser `MediaRecorder` -> Whisper -> `RecipeNote`
- `media-downloader`: `TranscriptionHook`, `BaseTranscriber` protocol

## Design

Voice sessions have a lifecycle:

```
create() -> session_id
  -> append_audio(audio_bytes) [repeat]
     -> Whisper transcribe -> Note appended
  -> freeze() -> RecipeNote (immutable)
  -> to_recipe() -> RecipeCoreTranscriber -> RecipeCore
```

Audio files are stored on disk at `data/notes/{session_id}/clip_{n}.webm`. The `RecipeNote` model (from Block 1) stores the text + timestamps. The actual Whisper transcription uses `media-downloader`'s transcription capabilities.

For the Telegram bot, voice messages arrive as `.ogg` files from Telegram's API. For the webapp, audio arrives as `audio/webm` blobs from the browser `MediaRecorder`.

## Deliverables

### 1. Voice session manager - `src/kit_hub/voice/voice_session.py`

```python
class VoiceSessionManager:
    """Manage voice note recording sessions."""

    def __init__(
        self,
        notes_dir: Path,               # data/notes/
        transcriber: BaseTranscriber,   # Whisper from media-downloader
    ): ...

    async def create_session(self, user_id: str | None = None) -> str:
        """Create a new voice session. Returns session_id (timestamp-based)."""
        ...

    async def append_audio(
        self, session_id: str, audio_data: bytes, content_type: str = "audio/webm",
    ) -> Note:
        """Save audio file, transcribe, append Note to session. Returns the new Note."""
        # 1. Save audio to data/notes/{session_id}/clip_{n}.{ext}
        # 2. Transcribe via Whisper
        # 3. Create Note(text=transcript, timestamp=now)
        # 4. Append to in-memory RecipeNote
        # 5. Persist RecipeNote JSON to data/notes/{session_id}/note.json
        # 6. Return the Note
        ...

    async def freeze_session(self, session_id: str) -> RecipeNote:
        """Freeze a session - no more audio can be added. Returns final RecipeNote."""
        ...

    def get_session(self, session_id: str) -> RecipeNote | None:
        """Get an active or frozen session by ID."""
        ...

    def list_sessions(self, user_id: str | None = None) -> list[str]:
        """List session IDs, optionally filtered by user."""
        ...
```

### 2. Voice-to-recipe bridge - `src/kit_hub/voice/voice_to_recipe.py`

```python
class VoiceToRecipeConverter:
    """Convert a frozen voice session into a structured recipe."""

    def __init__(self, transcriber: RecipeCoreTranscriber): ...

    async def convert(self, recipe_note: RecipeNote) -> RecipeCore:
        """Feed RecipeNote.to_string() into RecipeCoreTranscriber."""
        note_text = recipe_note.to_string()
        return await self.transcriber.ainvoke(note_text)
```

This is the "missing bridge" identified in the original plan - connecting voice notes to structured recipes.

### 3. Audio format support

Supported audio formats:
- `audio/webm` - browser MediaRecorder (webapp flow)
- `audio/ogg` - Telegram voice messages (bot flow)
- `audio/mp4`, `audio/mpeg` - general audio files

Whisper handles all of these natively. The `content_type` parameter on `append_audio` determines the file extension for storage.

## Tasks

- [ ] Create `src/kit_hub/voice/` package
- [ ] Implement `voice_session.py` with full lifecycle
- [ ] Implement `voice_to_recipe.py` bridge
- [ ] Write tests: `tests/voice/test_voice_session.py` - create, append (mocked Whisper), freeze, get
- [ ] Write tests: `tests/voice/test_voice_to_recipe.py` - RecipeNote.to_string() -> mocked transcriber
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
