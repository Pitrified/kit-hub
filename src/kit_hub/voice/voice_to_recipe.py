"""Bridge between a frozen voice session and a structured recipe.

``VoiceToRecipeConverter`` feeds a ``RecipeNote``'s timestamped transcript
into ``RecipeCoreTranscriber`` to produce a structured ``RecipeCore``.

This is the final step in the voice note pipeline::

    RecipeNote.to_string() -> RecipeCoreTranscriber.ainvoke() -> RecipeCore

Example:
    ::

        converter = VoiceToRecipeConverter(transcriber)
        recipe_core = await converter.convert(recipe_note)
"""

from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_note import RecipeNote


class VoiceToRecipeConverter:
    """Convert a frozen voice session into a structured recipe.

    Renders the ``RecipeNote`` as a timestamped transcript string and
    feeds it into ``RecipeCoreTranscriber``.

    Args:
        transcriber: LLM chain that converts free text to a structured
            ``RecipeCore``.
    """

    def __init__(self, transcriber: RecipeCoreTranscriber) -> None:
        """Initialise the converter.

        Args:
            transcriber: LLM chain for structured recipe parsing.
        """
        self._transcriber = transcriber

    async def convert(self, recipe_note: RecipeNote) -> RecipeCore:
        """Convert a ``RecipeNote`` into a structured ``RecipeCore``.

        Renders the note as a timestamped transcript via
        ``RecipeNote.to_string()`` then invokes the transcriber
        asynchronously.

        Args:
            recipe_note: A frozen (or active) voice session log.

        Returns:
            Structured ``RecipeCore`` parsed from the dictation transcript.
        """
        note_text = recipe_note.to_string()
        return await self._transcriber.ainvoke(note_text)
