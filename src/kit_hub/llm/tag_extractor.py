"""TagExtractor - extracts recipe tags with confidence scores using an LLM.

Given a recipe name and the full recipe rendered as text, the extractor
returns a list of ``RecipeTagAssignment`` objects with confidence scores.
All generated tags have their ``origin`` set to ``"ai"``.

The prompt is loaded from ``prompts/tag_extractor/v1.jinja`` relative to
``LlmConfig.prompts_fol``.

Example:
    ::

        llm_config = LlmParams().to_config()
        extractor = TagExtractor(llm_config)
        tags = extractor.invoke(recipe)
        # tags -> [RecipeTagAssignment(tag_name="pasta", confidence=0.95,
        #          origin="ai"), ...]
"""

from llm_core.chains.structured_chain import StructuredLLMChain
from llm_core.data_models.basemodel_kwargs import BaseModelKwargs
from llm_core.prompts.prompt_loader import PromptLoader
from llm_core.prompts.prompt_loader import PromptLoaderConfig
from pydantic import BaseModel

from kit_hub.config.llm_config import LlmConfig
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.tag import RecipeTagAssignment


class TagExtractorInput(BaseModelKwargs):
    """Input model for the tag extractor chain.

    Attributes:
        recipe_name: The name of the recipe.
        recipe_text: Full recipe rendered as plain text for the LLM.
    """

    recipe_name: str
    recipe_text: str


class TagExtractorOutput(BaseModel):
    """Output model for the tag extractor chain.

    Attributes:
        tags: List of tag assignments with confidence scores and
            ``origin`` set to ``"ai"``.
    """

    tags: list[RecipeTagAssignment]


def _recipe_to_text(recipe: RecipeCore) -> str:
    """Render a ``RecipeCore`` as plain text for LLM input.

    Args:
        recipe: The recipe to render.

    Returns:
        Multi-line string with preparations, ingredients, and steps.
    """
    lines: list[str] = []
    for prep in recipe.preparations:
        if prep.preparation_name:
            lines.append(f"## {prep.preparation_name}")
        lines.append("Ingredients:")
        lines.extend(f"  - {ing.name}: {ing.quantity}" for ing in prep.ingredients)
        lines.append("Steps:")
        for i, step in enumerate(prep.steps, start=1):
            if step.instruction:
                lines.append(f"  {i}. {step.instruction}")
    return "\n".join(lines)


class TagExtractor:
    """Extract recipe tags with AI-assigned confidence scores.

    Wraps a ``StructuredLLMChain`` using the ``tag_extractor`` versioned
    Jinja prompt.  All returned tags have ``origin`` set to ``"ai"``.

    Args:
        llm_config: LLM chain configuration including the chat model and
            the prompts root folder.
    """

    def __init__(self, llm_config: LlmConfig) -> None:
        """Build the tag extractor chain.

        Args:
            llm_config: LLM chain configuration.
        """
        prompt_str = PromptLoader(
            PromptLoaderConfig(
                base_prompt_fol=llm_config.prompts_fol,
                prompt_name="tag_extractor",
            )
        ).load_prompt()
        self._chain: StructuredLLMChain[TagExtractorInput, TagExtractorOutput] = (
            StructuredLLMChain(
                chat_config=llm_config.chat_config,
                prompt_str=prompt_str,
                input_model=TagExtractorInput,
                output_model=TagExtractorOutput,
            )
        )

    def invoke(self, recipe: RecipeCore) -> list[RecipeTagAssignment]:
        """Extract tags from a recipe synchronously.

        Args:
            recipe: The recipe to tag.

        Returns:
            List of ``RecipeTagAssignment`` with ``origin="ai"`` and
            confidence scores in ``[0.0, 1.0]``.
        """
        result = self._chain.invoke(
            TagExtractorInput(
                recipe_name=recipe.name,
                recipe_text=_recipe_to_text(recipe),
            )
        )
        return result.tags

    async def ainvoke(self, recipe: RecipeCore) -> list[RecipeTagAssignment]:
        """Extract tags from a recipe asynchronously.

        Args:
            recipe: The recipe to tag.

        Returns:
            List of ``RecipeTagAssignment`` with ``origin="ai"`` and
            confidence scores in ``[0.0, 1.0]``.
        """
        result = await self._chain.ainvoke(
            TagExtractorInput(
                recipe_name=recipe.name,
                recipe_text=_recipe_to_text(recipe),
            )
        )
        return result.tags
