# Voice Notes

The `voice` package handles live cooking dictation sessions. Audio clips are uploaded, transcribed via Whisper, and accumulated as a timestamped `RecipeNote`. The frozen session can then be converted into a structured `RecipeCore` by the LLM transcriber chain.

## Session lifecycle

```
create_session() -> session_id
    -> append_audio(audio_bytes, content_type) [repeat per clip]
       -> Whisper transcribe -> Note appended
    -> freeze_session() -> RecipeNote
    -> VoiceToRecipeConverter.convert(recipe_note) -> RecipeCore
```

## VoiceSessionManager

`VoiceSessionManager` manages the full recording lifecycle. It requires a `notes_dir` (from `KitHubPaths.notes_fol`) and an `AudioTranscriber`.

```python
from kit_hub.params.kit_hub_params import get_kit_hub_paths
from kit_hub.voice.voice_session import VoiceSessionManager

paths = get_kit_hub_paths()
manager = VoiceSessionManager(notes_dir=paths.notes_fol, transcriber=whisper)

session_id = await manager.create_session(user_id="user-42")
note = await manager.append_audio(session_id, audio_bytes, "audio/webm")
recipe_note = await manager.freeze_session(session_id)
```

### Storage layout

Audio clips and session state are stored under `notes_dir/{session_id}/`:

```
data/notes/
    20260101_120000_abc12345/
        clip_0.webm
        clip_1.ogg
        note.json       <- RecipeNote checkpoint (updated after each clip)
```

The `note.json` file is written after every `append_audio` call, so partial sessions survive process restarts if re-loaded from disk.

### Supported audio formats

| MIME type | Extension | Source |
|--|--|--|
| `audio/webm` | `.webm` | Browser `MediaRecorder` (webapp) |
| `audio/ogg` | `.ogg` | Telegram voice messages |
| `audio/mp4` | `.mp4` | General audio |
| `audio/mpeg` | `.mp3` | General audio |
| `audio/wav` | `.wav` | General audio |

### Error handling

- `SessionNotFoundError` - raised when a `session_id` does not exist (inherits `KeyError`).
- `FrozenSessionError` - raised when `append_audio` is called on a frozen session (inherits `ValueError`).

## AudioTranscriber protocol

`AudioTranscriber` is a structural `Protocol` defined in `voice_session.py`. Any object with an `async atranscribe(audio_fp: Path) -> str` method satisfies it. The concrete implementation is typically a Whisper-based transcriber from `llm-core` or `media-downloader`.

## VoiceToRecipeConverter

`VoiceToRecipeConverter` is the bridge between a voice session and a structured recipe. It renders the `RecipeNote` as a timestamped transcript and feeds it into `RecipeCoreTranscriber`.

```python
from kit_hub.voice.voice_to_recipe import VoiceToRecipeConverter

converter = VoiceToRecipeConverter(transcriber=recipe_transcriber)
recipe_core = await converter.convert(recipe_note)
```

The `RecipeNote.to_string()` output looks like:

```
00:00: Start with 200g of farro.
01:23: Simmer for 30 minutes with a pinch of salt.
03:45: Serve hot with a drizzle of olive oil.
```

This timestamped format gives the LLM useful context about the cooking flow and pacing.

## Related

- [`RecipeNote`](../../reference/kit_hub/recipes/recipe_note/) - data model for the session log.
- [`RecipeCoreTranscriber`](../../reference/kit_hub/llm/transcriber/) - LLM chain used by `VoiceToRecipeConverter`.
- `KitHubPaths.notes_fol` - filesystem path for session storage.
