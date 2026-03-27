"""Tests for the RecipeNote and Note voice session models.

Covers note construction, add_note mutation, and to_string timestamp
formatting.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from kit_hub.recipes.recipe_note import Note
from kit_hub.recipes.recipe_note import RecipeNote


class TestNote:
    """Tests for the Note model."""

    def test_init_with_explicit_timestamp(self) -> None:
        """Note stores text and a provided timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        note = Note(text="Add salt.", timestamp=ts)
        assert note.text == "Add salt."
        assert note.timestamp == ts

    def test_default_timestamp_is_set(self) -> None:
        """Note sets timestamp to current time when not provided."""
        before = datetime.now(tz=UTC)
        note = Note(text="Stir gently.")
        after = datetime.now(tz=UTC)
        assert before <= note.timestamp <= after

    def test_serialise_roundtrip(self) -> None:
        """Note round-trips through JSON without data loss."""
        ts = datetime(2024, 6, 15, 9, 30, 0, tzinfo=UTC)
        note = Note(text="Check the oven.", timestamp=ts)
        restored = Note.model_validate_json(note.model_dump_json())
        assert restored == note


class TestRecipeNote:
    """Tests for the RecipeNote model."""

    def test_default_construction(self) -> None:
        """RecipeNote initialises with empty notes list and a start timestamp."""
        before = datetime.now(tz=UTC)
        rn = RecipeNote()
        after = datetime.now(tz=UTC)
        assert before <= rn.start_timestamp <= after
        assert rn.notes == []

    def test_add_note_appends_entry(self) -> None:
        """add_note appends a Note to the notes list."""
        rn = RecipeNote()
        rn.add_note("First note.")
        assert len(rn.notes) == 1
        assert rn.notes[0].text == "First note."

    def test_add_multiple_notes(self) -> None:
        """Multiple add_note calls produce ordered entries."""
        rn = RecipeNote()
        rn.add_note("Chop onions.")
        rn.add_note("Heat oil.")
        rn.add_note("Fry onions.")
        assert len(rn.notes) == 3
        assert rn.notes[1].text == "Heat oil."

    def test_to_string_empty_session(self) -> None:
        """to_string returns an empty string when there are no notes."""
        rn = RecipeNote()
        assert rn.to_string() == ""

    def test_to_string_single_note_at_zero(self) -> None:
        """Note recorded at session start shows 00:00 timestamp."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        rn = RecipeNote(start_timestamp=start)
        rn.notes.append(Note(text="Begin.", timestamp=start))
        result = rn.to_string()
        assert result == "00:00: Begin."

    def test_to_string_relative_timestamps(self) -> None:
        """to_string formats timestamps relative to start_timestamp."""
        start = datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)
        rn = RecipeNote(start_timestamp=start)
        rn.notes.append(
            Note(text="First note.", timestamp=start + timedelta(seconds=30))
        )
        rn.notes.append(
            Note(
                text="Second note.",
                timestamp=start + timedelta(minutes=1, seconds=5),
            )
        )
        rn.notes.append(
            Note(text="Third note.", timestamp=start + timedelta(minutes=10))
        )
        result = rn.to_string()
        lines = result.split("\n")
        assert lines[0] == "00:30: First note."
        assert lines[1] == "01:05: Second note."
        assert lines[2] == "10:00: Third note."

    def test_to_string_three_lines_for_three_notes(self) -> None:
        """to_string produces one line per note."""
        start = datetime(2024, 1, 1, 0, 0, 0, tzinfo=UTC)
        rn = RecipeNote(start_timestamp=start)
        for i in range(3):
            rn.notes.append(
                Note(text=f"note {i}", timestamp=start + timedelta(seconds=i * 10))
            )
        lines = rn.to_string().split("\n")
        assert len(lines) == 3

    def test_add_note_timestamp_is_after_start(self) -> None:
        """Notes added via add_note have timestamps at or after start_timestamp."""
        rn = RecipeNote()
        rn.add_note("Some note.")
        assert rn.notes[0].timestamp >= rn.start_timestamp
