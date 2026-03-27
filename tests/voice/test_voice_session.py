"""Tests for VoiceSessionManager.

Uses a temporary directory for audio storage and an AsyncMock for the
Whisper transcriber, so no external services are called.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from kit_hub.recipes.recipe_note import Note
from kit_hub.recipes.recipe_note import RecipeNote
from kit_hub.voice.voice_session import AudioTranscriber
from kit_hub.voice.voice_session import FrozenSessionError
from kit_hub.voice.voice_session import SessionNotFoundError
from kit_hub.voice.voice_session import VoiceSessionManager

_FAKE_TRANSCRIPT = "Add a pinch of salt."
_FAKE_AUDIO = b"fake-audio-bytes"


@pytest.fixture
def transcriber() -> AudioTranscriber:
    """Return a mock AudioTranscriber that returns a fixed transcript."""
    mock = MagicMock(spec=AudioTranscriber)
    mock.atranscribe = AsyncMock(return_value=_FAKE_TRANSCRIPT)
    return mock


@pytest.fixture
def manager(tmp_path: Path, transcriber: AudioTranscriber) -> VoiceSessionManager:
    """Return a VoiceSessionManager backed by a temporary directory."""
    return VoiceSessionManager(notes_dir=tmp_path, transcriber=transcriber)


class TestCreateSession:
    """Tests for VoiceSessionManager.create_session."""

    async def test_returns_string_id(self, manager: VoiceSessionManager) -> None:
        """create_session returns a non-empty string session ID."""
        session_id = await manager.create_session()
        assert isinstance(session_id, str)
        assert session_id

    async def test_creates_session_directory(
        self, manager: VoiceSessionManager, tmp_path: Path
    ) -> None:
        """create_session creates a subdirectory under notes_dir."""
        session_id = await manager.create_session()
        assert (tmp_path / session_id).is_dir()

    async def test_persists_empty_note_json(
        self, manager: VoiceSessionManager, tmp_path: Path
    ) -> None:
        """create_session writes an initial note.json to disk."""
        session_id = await manager.create_session()
        note_file = tmp_path / session_id / "note.json"
        assert note_file.is_file()
        data = json.loads(note_file.read_text())
        assert data["notes"] == []

    async def test_session_retrievable_after_create(
        self, manager: VoiceSessionManager
    ) -> None:
        """Session is immediately retrievable via get_session."""
        session_id = await manager.create_session()
        result = manager.get_session(session_id)
        assert isinstance(result, RecipeNote)

    async def test_user_id_stored_for_list_filter(
        self, manager: VoiceSessionManager
    ) -> None:
        """Sessions created with user_id appear in list_sessions(user_id=...)."""
        sid_a = await manager.create_session(user_id="user-a")
        sid_b = await manager.create_session(user_id="user-b")
        assert manager.list_sessions(user_id="user-a") == [sid_a]
        assert manager.list_sessions(user_id="user-b") == [sid_b]

    async def test_unique_ids_per_call(self, manager: VoiceSessionManager) -> None:
        """Successive calls produce distinct session IDs."""
        ids = [await manager.create_session() for _ in range(5)]
        assert len(set(ids)) == 5


class TestAppendAudio:
    """Tests for VoiceSessionManager.append_audio."""

    async def test_returns_note_with_transcript(
        self, manager: VoiceSessionManager
    ) -> None:
        """append_audio returns a Note whose text is the transcript."""
        session_id = await manager.create_session()
        note = await manager.append_audio(session_id, _FAKE_AUDIO)
        assert isinstance(note, Note)
        assert note.text == _FAKE_TRANSCRIPT

    async def test_saves_audio_file_to_disk(
        self, manager: VoiceSessionManager, tmp_path: Path
    ) -> None:
        """append_audio writes the raw audio bytes to a clip file."""
        session_id = await manager.create_session()
        await manager.append_audio(session_id, _FAKE_AUDIO, "audio/webm")
        clip = tmp_path / session_id / "clip_0.webm"
        assert clip.is_file()
        assert clip.read_bytes() == _FAKE_AUDIO

    async def test_uses_correct_extension_for_ogg(
        self, manager: VoiceSessionManager, tmp_path: Path
    ) -> None:
        """append_audio uses .ogg extension for audio/ogg content type."""
        session_id = await manager.create_session()
        await manager.append_audio(session_id, _FAKE_AUDIO, "audio/ogg")
        assert (tmp_path / session_id / "clip_0.ogg").is_file()

    async def test_clip_numbers_increment(
        self, manager: VoiceSessionManager, tmp_path: Path
    ) -> None:
        """Successive appends produce clip_0, clip_1, clip_2, ..."""
        session_id = await manager.create_session()
        for _ in range(3):
            await manager.append_audio(session_id, _FAKE_AUDIO)
        session_dir = tmp_path / session_id
        assert (session_dir / "clip_0.webm").is_file()
        assert (session_dir / "clip_1.webm").is_file()
        assert (session_dir / "clip_2.webm").is_file()

    async def test_note_accumulated_in_session(
        self, manager: VoiceSessionManager
    ) -> None:
        """Each append_audio adds a Note to the session's RecipeNote."""
        session_id = await manager.create_session()
        await manager.append_audio(session_id, _FAKE_AUDIO)
        await manager.append_audio(session_id, _FAKE_AUDIO)
        recipe_note = manager.get_session(session_id)
        assert recipe_note is not None
        assert len(recipe_note.notes) == 2

    async def test_persists_note_json_after_append(
        self, manager: VoiceSessionManager, tmp_path: Path
    ) -> None:
        """append_audio updates note.json on disk after each clip."""
        session_id = await manager.create_session()
        await manager.append_audio(session_id, _FAKE_AUDIO)
        data = json.loads((tmp_path / session_id / "note.json").read_text())
        assert len(data["notes"]) == 1
        assert data["notes"][0]["text"] == _FAKE_TRANSCRIPT

    async def test_calls_transcriber_with_audio_path(
        self,
        manager: VoiceSessionManager,
        transcriber: AudioTranscriber,
        tmp_path: Path,
    ) -> None:
        """append_audio passes the saved audio path to the transcriber."""
        session_id = await manager.create_session()
        await manager.append_audio(session_id, _FAKE_AUDIO, "audio/webm")
        expected_path = tmp_path / session_id / "clip_0.webm"
        transcriber.atranscribe.assert_called_once_with(expected_path)  # type: ignore[attr-defined]

    async def test_raises_for_unknown_session(
        self, manager: VoiceSessionManager
    ) -> None:
        """append_audio raises SessionNotFoundError for a missing session."""
        with pytest.raises(SessionNotFoundError):
            await manager.append_audio("nonexistent", _FAKE_AUDIO)

    async def test_raises_for_frozen_session(
        self, manager: VoiceSessionManager
    ) -> None:
        """append_audio raises FrozenSessionError after freeze_session."""
        session_id = await manager.create_session()
        await manager.freeze_session(session_id)
        with pytest.raises(FrozenSessionError):
            await manager.append_audio(session_id, _FAKE_AUDIO)


class TestFreezeSession:
    """Tests for VoiceSessionManager.freeze_session."""

    async def test_returns_recipe_note(self, manager: VoiceSessionManager) -> None:
        """freeze_session returns the session's RecipeNote."""
        session_id = await manager.create_session()
        await manager.append_audio(session_id, _FAKE_AUDIO)
        recipe_note = await manager.freeze_session(session_id)
        assert isinstance(recipe_note, RecipeNote)
        assert len(recipe_note.notes) == 1

    async def test_raises_for_unknown_session(
        self, manager: VoiceSessionManager
    ) -> None:
        """freeze_session raises SessionNotFoundError for a missing session."""
        with pytest.raises(SessionNotFoundError):
            await manager.freeze_session("nonexistent")

    async def test_blocks_further_appends(self, manager: VoiceSessionManager) -> None:
        """Frozen session rejects subsequent append_audio calls."""
        session_id = await manager.create_session()
        await manager.freeze_session(session_id)
        with pytest.raises(FrozenSessionError):
            await manager.append_audio(session_id, _FAKE_AUDIO)


class TestGetSession:
    """Tests for VoiceSessionManager.get_session."""

    async def test_returns_none_for_missing(self, manager: VoiceSessionManager) -> None:
        """get_session returns None for an unknown session_id."""
        assert manager.get_session("does-not-exist") is None

    async def test_returns_recipe_note_for_active(
        self, manager: VoiceSessionManager
    ) -> None:
        """get_session returns RecipeNote for an active session."""
        session_id = await manager.create_session()
        result = manager.get_session(session_id)
        assert isinstance(result, RecipeNote)

    async def test_returns_recipe_note_for_frozen(
        self, manager: VoiceSessionManager
    ) -> None:
        """get_session returns RecipeNote for a frozen session."""
        session_id = await manager.create_session()
        await manager.freeze_session(session_id)
        result = manager.get_session(session_id)
        assert isinstance(result, RecipeNote)


class TestListSessions:
    """Tests for VoiceSessionManager.list_sessions."""

    async def test_empty_by_default(self, manager: VoiceSessionManager) -> None:
        """list_sessions returns an empty list when no sessions exist."""
        assert manager.list_sessions() == []

    async def test_lists_all_sessions(self, manager: VoiceSessionManager) -> None:
        """list_sessions returns all created session IDs."""
        sid_1 = await manager.create_session()
        sid_2 = await manager.create_session()
        sessions = manager.list_sessions()
        assert sid_1 in sessions
        assert sid_2 in sessions

    async def test_filters_by_user_id(self, manager: VoiceSessionManager) -> None:
        """list_sessions(user_id=...) only returns sessions for that user."""
        sid_a = await manager.create_session(user_id="alice")
        await manager.create_session(user_id="bob")
        assert manager.list_sessions(user_id="alice") == [sid_a]

    async def test_no_filter_returns_all(self, manager: VoiceSessionManager) -> None:
        """list_sessions() without user_id returns all sessions."""
        await manager.create_session(user_id="alice")
        await manager.create_session(user_id="bob")
        await manager.create_session()
        assert len(manager.list_sessions()) == 3
