"""RecipeCoreTranscriber - converts free text into a structured RecipeCore.

The transcriber wraps a ``StructuredLLMChain`` that takes raw text (an
Instagram caption, a voice transcript, or a manually pasted recipe) and
produces a validated ``RecipeCore``.

The prompt is loaded from ``prompts/transcriber/v1.jinja`` relative to
``LlmConfig.prompts_fol``.  The recipe language is preserved as-is.

Example:
    ::

        llm_config = LlmParams().to_config()
        transcriber = RecipeCoreTranscriber(llm_config)
        recipe = transcriber.invoke("Boil pasta. Add sauce. Serve hot.")
"""

from llm_core.chains.structured_chain import StructuredLLMChain
from llm_core.data_models.basemodel_kwargs import BaseModelKwargs
from llm_core.prompts.prompt_loader import PromptLoader
from llm_core.prompts.prompt_loader import PromptLoaderConfig

from kit_hub.config.llm_config import LlmConfig
from kit_hub.recipes.recipe_core import RecipeCore


class TranscriberInput(BaseModelKwargs):
    """Input model for the transcriber chain.

    Attributes:
        recipe_text: Raw text containing the recipe to parse.
    """

    recipe_text: str


class RecipeCoreTranscriber:
    """Convert free-form recipe text into a structured ``RecipeCore``.

    Wraps a ``StructuredLLMChain`` using the ``transcriber`` versioned
    Jinja prompt.  The recipe language is preserved unchanged.

    Args:
        llm_config: LLM chain configuration including the chat model and
            the prompts root folder.
    """

    def __init__(self, llm_config: LlmConfig) -> None:
        """Build the transcriber chain.

        Args:
            llm_config: LLM chain configuration.
        """
        prompt_str = PromptLoader(
            PromptLoaderConfig(
                base_prompt_fol=llm_config.prompts_fol,
                prompt_name="transcriber",
            )
        ).load_prompt()
        self._chain: StructuredLLMChain[TranscriberInput, RecipeCore] = (
            StructuredLLMChain(
                chat_config=llm_config.chat_config,
                prompt_str=prompt_str,
                input_model=TranscriberInput,
                output_model=RecipeCore,
            )
        )

    def invoke(self, recipe_text: str) -> RecipeCore:
        """Parse recipe text synchronously.

        Args:
            recipe_text: Raw text containing the recipe.

        Returns:
            Structured ``RecipeCore`` parsed from the input text.
        """
        return self._chain.invoke(TranscriberInput(recipe_text=recipe_text))

    async def ainvoke(self, recipe_text: str) -> RecipeCore:
        """Parse recipe text asynchronously.

        Args:
            recipe_text: Raw text containing the recipe.

        Returns:
            Structured ``RecipeCore`` parsed from the input text.
        """
        return await self._chain.ainvoke(TranscriberInput(recipe_text=recipe_text))
