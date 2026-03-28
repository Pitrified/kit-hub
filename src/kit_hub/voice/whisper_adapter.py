"""Adapter between llm-core FasterWhisperTranscriber and the AudioTranscriber protocol.

``FasterWhisperTranscriber.atranscribe()`` returns a ``TranscriptionResult``
object.  ``VoiceSessionManager`` expects the ``AudioTranscriber`` protocol whose
``atranscribe()`` returns a plain ``str``.  This module bridges the two.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from llm_core.transcription.config.faster_whisper import FasterWhisperConfig
from llm_core.transcription.providers.faster_whisper import FasterWhisperTranscriber
from loguru import logger as lg

if TYPE_CHECKING:
    from pathlib import Path


class WhisperAudioTranscriber:
    """Adapt ``FasterWhisperTranscriber`` to the ``AudioTranscriber`` protocol.

    ``VoiceSessionManager`` requires an object whose ``atranscribe`` coroutine
    returns a plain ``str``.  ``FasterWhisperTranscriber.atranscribe`` returns a
    ``TranscriptionResult`` instead.  This adapter extracts the ``text`` field
    so that the caller always receives a string.

    Attributes:
        _transcriber: The underlying faster-whisper transcriber instance.
    """

    def __init__(self, transcriber: FasterWhisperTranscriber) -> None:
        """Initialise with a pre-built transcriber.

        Args:
            transcriber: A fully loaded ``FasterWhisperTranscriber`` instance.
        """
        self._transcriber = transcriber

    @classmethod
    def from_config(cls, config: FasterWhisperConfig) -> WhisperAudioTranscriber:
        """Build an adapter from a ``FasterWhisperConfig``.

        Args:
            config: Configuration specifying model, device, and compute_type.

        Returns:
            A ready-to-use ``WhisperAudioTranscriber``.
        """
        transcriber = FasterWhisperTranscriber(config=config)
        return cls(transcriber)

    @classmethod
    def from_default(cls) -> WhisperAudioTranscriber:
        """Build an adapter with sensible CPU defaults.

        Uses the ``medium`` model, ``cpu`` device, and ``int8`` compute_type.
        Suitable for a local development box without a GPU.

        Returns:
            A ready-to-use ``WhisperAudioTranscriber``.
        """
        lg.info("Creating WhisperAudioTranscriber with defaults (medium/cpu/int8)")
        config = FasterWhisperConfig(model="medium", device="cpu", compute_type="int8")
        return cls.from_config(config)

    async def atranscribe(self, audio_fp: Path) -> str:
        """Transcribe an audio file and return the transcript as a plain string.

        Delegates to ``FasterWhisperTranscriber.atranscribe`` and extracts the
        ``text`` field from the returned ``TranscriptionResult``.

        Args:
            audio_fp: Path to the audio file to transcribe.

        Returns:
            Transcribed text string.
        """
        result = await self._transcriber.atranscribe(audio_fp)
        return result.text
