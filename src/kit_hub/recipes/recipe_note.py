"""Voice note session models.

These models represent a live cooking dictation session.  Audio clips are
transcribed via Whisper and appended as ``Note`` entries to a
``RecipeNote``.  The ``to_string()`` method renders the session log in a
format suitable for feeding into ``RecipeCoreTranscriber``.

Models:
    Note: A single transcribed note with a timestamp.
    RecipeNote: A full dictation session log.
"""

from datetime import UTC
from datetime import datetime

from pydantic import BaseModel
from pydantic import Field


class Note(BaseModel):
    """A single transcribed note recorded during a cooking session.

    Attributes:
        text: The transcribed text content of the note.
        timestamp: When the note was recorded.  Defaults to the current
            datetime at construction time.
    """

    text: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))


class RecipeNote(BaseModel):
    """A live cooking dictation session log.

    Audio clips are uploaded as ``audio/webm`` blobs, transcribed by
    Whisper, and appended as ``Note`` entries.  Call ``to_string()``
    to produce a timestamped transcript suitable for LLM input.

    Attributes:
        start_timestamp: When the session was created.  Defaults to the
            current datetime at construction time.
        notes: Ordered list of transcribed notes.
    """

    start_timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    notes: list[Note] = Field(default_factory=list)

    def add_note(self, text: str) -> None:
        """Append a new note with the current timestamp.

        Args:
            text: The transcribed text to record.
        """
        self.notes.append(Note(text=text))

    def to_string(self) -> str:
        """Render the session log as a timestamped transcript string.

        Each line is formatted as ``MM:SS: note text``, where the
        timestamp is relative to ``start_timestamp``.

        Returns:
            Multi-line string with one ``MM:SS: <text>`` entry per note.
            Returns an empty string when there are no notes.
        """
        lines: list[str] = []
        for note in self.notes:
            delta = note.timestamp - self.start_timestamp
            total_seconds = int(delta.total_seconds())
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            lines.append(f"{minutes:02d}:{seconds:02d}: {note.text}")
        return "\n".join(lines)
