"""Voice note session lifecycle management.

``VoiceSessionManager`` creates recording sessions, accepts audio clips,
transcribes each clip immediately, and freezes the session once recording
is complete.

Session lifecycle::

    create_session() -> session_id
        -> append_audio(audio_data) [repeat, once per clip]
           -> Whisper transcribe -> Note appended
        -> freeze_session() -> RecipeNote
        -> (caller) note.to_string() -> RecipeCoreTranscriber -> RecipeCore

Audio files are stored at ``notes_dir/{session_id}/clip_{n}.{ext}``.
Session state is persisted as ``notes_dir/{session_id}/note.json``.

Example:
    ::

        manager = VoiceSessionManager(notes_dir=paths.notes_fol, transcriber=whisper)
        session_id = await manager.create_session(user_id="user-42")
        note = await manager.append_audio(session_id, audio_bytes, "audio/webm")
        recipe_note = await manager.freeze_session(session_id)
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Protocol

from loguru import logger as lg

from kit_hub.recipes.recipe_note import Note
from kit_hub.recipes.recipe_note import RecipeNote

_CONTENT_TYPE_EXT: dict[str, str] = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
}

_NOTE_FILE = "note.json"


class AudioTranscriber(Protocol):
    """Structural protocol for async audio-to-text transcription.

    Any object with an ``atranscribe`` coroutine satisfies this protocol.
    The concrete implementation is typically a Whisper-based transcriber
    from ``llm-core`` or ``media-downloader``.
    """

    async def atranscribe(self, audio_fp: Path) -> str:
        """Transcribe an audio file and return the transcript text.

        Args:
            audio_fp: Path to the audio file to transcribe.

        Returns:
            Transcribed text string.
        """
        ...


class SessionNotFoundError(KeyError):
    """Raised when a requested voice session does not exist.

    Args:
        session_id: The session ID that was not found.
    """

    def __init__(self, session_id: str) -> None:
        """Initialise with the missing session ID.

        Args:
            session_id: The session ID that was not found.
        """
        self.session_id = session_id
        super().__init__(session_id)


class FrozenSessionError(ValueError):
    """Raised when audio is appended to an already-frozen session.

    Args:
        session_id: The frozen session ID.
    """

    def __init__(self, session_id: str) -> None:
        """Initialise with the frozen session ID.

        Args:
            session_id: The frozen session ID.
        """
        self.session_id = session_id
        msg = f"Session is frozen and cannot accept more audio: {session_id}"
        super().__init__(msg)


@dataclass
class _SessionEntry:
    """Internal storage for a single voice session.

    Attributes:
        note: The accumulated ``RecipeNote`` for this session.
        frozen: Whether the session has been frozen.
        user_id: Optional owner identifier.
    """

    note: RecipeNote
    frozen: bool = False
    user_id: str | None = None
    clip_count: int = field(default=0)


def _make_session_id() -> str:
    """Generate a timestamp-based session ID with a random suffix.

    Returns:
        Unique session ID string.
    """
    ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    import uuid  # noqa: PLC0415

    suffix = uuid.uuid4().hex[:8]
    return f"{ts}_{suffix}"


def _ext_for(content_type: str) -> str:
    """Map a MIME content type to a file extension.

    Args:
        content_type: MIME type string (e.g. ``"audio/webm"``).

    Returns:
        File extension without a leading dot. Falls back to ``"webm"``
        for unknown types.
    """
    return _CONTENT_TYPE_EXT.get(content_type, "webm")


class VoiceSessionManager:
    """Manage voice note recording sessions.

    Each session has a unique ID and stores audio clips on disk alongside
    a ``note.json`` checkpoint. Sessions transition from active to frozen
    on a single ``freeze_session()`` call.

    Attributes:
        _notes_dir: Root directory for all session subdirectories.
        _transcriber: Whisper-compatible async transcriber.
        _sessions: In-memory mapping of session IDs to ``_SessionEntry``.

    Args:
        notes_dir: Root directory where session folders are created.
        transcriber: Async audio transcriber (Whisper or compatible).
    """

    def __init__(
        self,
        notes_dir: Path,
        transcriber: AudioTranscriber,
    ) -> None:
        """Initialise the session manager.

        Args:
            notes_dir: Root directory where session folders are created.
            transcriber: Async audio transcriber.
        """
        self._notes_dir = notes_dir
        self._transcriber = transcriber
        self._sessions: dict[str, _SessionEntry] = {}

    async def create_session(self, user_id: str | None = None) -> str:
        """Create a new voice session.

        Creates the session directory and persists an empty ``note.json``.

        Args:
            user_id: Optional owner identifier stored with the session.

        Returns:
            Unique session ID string.
        """
        session_id = _make_session_id()
        session_dir = self._notes_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)
        note = RecipeNote()
        entry = _SessionEntry(note=note, user_id=user_id)
        self._sessions[session_id] = entry
        self._persist(session_id, note)
        lg.info(f"Created voice session {session_id!r} for user {user_id!r}")
        return session_id

    async def append_audio(
        self,
        session_id: str,
        audio_data: bytes,
        content_type: str = "audio/webm",
    ) -> Note:
        """Save an audio clip, transcribe it, and append the result.

        Writes the raw audio bytes to disk, transcribes asynchronously,
        creates a ``Note`` with the current timestamp, and appends it to
        the session's ``RecipeNote``. The checkpoint JSON is updated.

        Args:
            session_id: ID of an active (non-frozen) session.
            audio_data: Raw audio bytes from the client or bot.
            content_type: MIME type of the audio data. Used to choose the
                file extension for the saved clip.

        Returns:
            The newly created ``Note`` containing the transcription.

        Raises:
            SessionNotFoundError: If ``session_id`` does not exist.
            FrozenSessionError: If the session has already been frozen.
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            raise SessionNotFoundError(session_id)
        if entry.frozen:
            raise FrozenSessionError(session_id)

        session_dir = self._notes_dir / session_id
        ext = _ext_for(content_type)
        audio_fp = session_dir / f"clip_{entry.clip_count}.{ext}"
        audio_fp.write_bytes(audio_data)
        entry.clip_count += 1

        transcript = await self._transcriber.atranscribe(audio_fp)
        new_note = Note(text=transcript)
        entry.note.notes.append(new_note)
        self._persist(session_id, entry.note)
        lg.debug(f"Appended note to {session_id!r}: {transcript[:60]!r}")
        return new_note

    async def freeze_session(self, session_id: str) -> RecipeNote:
        """Mark a session as frozen and return the final ``RecipeNote``.

        After freezing, ``append_audio`` will raise ``FrozenSessionError``
        for this session.

        Args:
            session_id: ID of the session to freeze.

        Returns:
            The frozen ``RecipeNote`` with all accumulated notes.

        Raises:
            SessionNotFoundError: If ``session_id`` does not exist.
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            raise SessionNotFoundError(session_id)
        entry.frozen = True
        lg.info(f"Frozen voice session {session_id!r}")
        return entry.note

    def get_session(self, session_id: str) -> RecipeNote | None:
        """Return the ``RecipeNote`` for a session, or ``None`` if absent.

        Args:
            session_id: Session ID to look up.

        Returns:
            The session's ``RecipeNote``, or ``None`` if not found.
        """
        entry = self._sessions.get(session_id)
        return entry.note if entry is not None else None

    def list_sessions(self, user_id: str | None = None) -> list[str]:
        """List session IDs, optionally filtered by owner.

        Args:
            user_id: When provided, only sessions with a matching
                ``user_id`` are returned.

        Returns:
            List of session ID strings.
        """
        if user_id is None:
            return list(self._sessions)
        return [sid for sid, e in self._sessions.items() if e.user_id == user_id]

    def list_frozen_sessions(
        self,
        user_id: str | None = None,
    ) -> list[tuple[str, RecipeNote]]:
        """List frozen sessions with their ``RecipeNote``, optionally by owner.

        Args:
            user_id: When provided, only sessions with a matching
                ``user_id`` are returned.

        Returns:
            List of ``(session_id, RecipeNote)`` tuples for frozen sessions.
        """
        results: list[tuple[str, RecipeNote]] = []
        for sid, entry in self._sessions.items():
            if not entry.frozen:
                continue
            if user_id is not None and entry.user_id != user_id:
                continue
            results.append((sid, entry.note))
        return results

    async def unfreeze_session(self, session_id: str) -> RecipeNote:
        """Re-open a frozen session so more audio clips can be appended.

        Args:
            session_id: ID of the session to unfreeze.

        Returns:
            The unfrozen ``RecipeNote``.

        Raises:
            SessionNotFoundError: If ``session_id`` does not exist.
        """
        entry = self._sessions.get(session_id)
        if entry is None:
            raise SessionNotFoundError(session_id)
        entry.frozen = False
        lg.info(f"Unfrozen voice session {session_id!r}")
        return entry.note

    def delete_session(self, session_id: str) -> None:
        """Remove a session from memory and delete its files from disk.

        Args:
            session_id: ID of the session to delete.

        Raises:
            SessionNotFoundError: If ``session_id`` does not exist.
        """
        entry = self._sessions.pop(session_id, None)
        if entry is None:
            raise SessionNotFoundError(session_id)
        session_dir = self._notes_dir / session_id
        if session_dir.exists():
            import shutil  # noqa: PLC0415

            shutil.rmtree(session_dir)
        lg.info(f"Deleted voice session {session_id!r}")

    def _persist(self, session_id: str, note: RecipeNote) -> None:
        """Write the session's ``RecipeNote`` to ``note.json``.

        Args:
            session_id: Session ID whose note to persist.
            note: ``RecipeNote`` to serialise.
        """
        note_file = self._notes_dir / session_id / _NOTE_FILE
        note_file.write_text(note.model_dump_json(), encoding="utf-8")
