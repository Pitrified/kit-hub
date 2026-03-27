"""Tests for VoiceToRecipeConverter.

Uses a mocked RecipeCoreTranscriber to verify the bridge between
RecipeNote.to_string() and the LLM parsing chain.
"""

from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest

from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_note import RecipeNote
from kit_hub.voice.voice_to_recipe import VoiceToRecipeConverter


@pytest.fixture
def fake_recipe() -> RecipeCore:
    """Return a minimal valid RecipeCore."""
    return RecipeCore(
        name="Zuppa di Farro",
        preparations=[
            Preparation(
                ingredients=[Ingredient(name="farro", quantity="200g")],
                steps=[Step(instruction="Simmer farro for 30 minutes.")],
            )
        ],
    )


@pytest.fixture
def transcriber(fake_recipe: RecipeCore) -> RecipeCoreTranscriber:
    """Return a mock RecipeCoreTranscriber that returns fake_recipe."""
    mock = MagicMock(spec=RecipeCoreTranscriber)
    mock.ainvoke = AsyncMock(return_value=fake_recipe)
    return mock


@pytest.fixture
def converter(transcriber: RecipeCoreTranscriber) -> VoiceToRecipeConverter:
    """Return a VoiceToRecipeConverter with mocked transcriber."""
    return VoiceToRecipeConverter(transcriber)


@pytest.fixture
def recipe_note() -> RecipeNote:
    """Return a RecipeNote with two notes."""
    note = RecipeNote()
    note.add_note("Start with 200g of farro.")
    note.add_note("Simmer for 30 minutes.")
    return note


class TestVoiceToRecipeConverter:
    """Tests for VoiceToRecipeConverter."""

    async def test_returns_recipe_core(
        self,
        converter: VoiceToRecipeConverter,
        recipe_note: RecipeNote,
    ) -> None:
        """Convert returns a RecipeCore instance."""
        result = await converter.convert(recipe_note)
        assert isinstance(result, RecipeCore)

    async def test_calls_transcriber_with_note_string(
        self,
        converter: VoiceToRecipeConverter,
        transcriber: RecipeCoreTranscriber,
        recipe_note: RecipeNote,
    ) -> None:
        """Convert passes RecipeNote.to_string() to the transcriber."""
        await converter.convert(recipe_note)
        expected_text = recipe_note.to_string()
        transcriber.ainvoke.assert_called_once_with(expected_text)  # type: ignore[attr-defined]

    async def test_returns_transcriber_output(
        self,
        converter: VoiceToRecipeConverter,
        recipe_note: RecipeNote,
        fake_recipe: RecipeCore,
    ) -> None:
        """Convert returns exactly what the transcriber returns."""
        result = await converter.convert(recipe_note)
        assert result is fake_recipe

    async def test_empty_note_passes_empty_string(
        self,
        converter: VoiceToRecipeConverter,
        transcriber: RecipeCoreTranscriber,
    ) -> None:
        """Convert passes an empty string when the RecipeNote has no notes."""
        empty_note = RecipeNote()
        await converter.convert(empty_note)
        transcriber.ainvoke.assert_called_once_with("")  # type: ignore[attr-defined]
