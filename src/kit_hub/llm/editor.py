"""RecipeCoreEditor - applies a natural-language correction to a recipe step.

The editor takes an existing ``RecipeCore``, the text of the step to
correct, and natural-language instructions for the correction.  It returns
a new ``RecipeCore`` with the targeted step updated and all other content
preserved unchanged.

The prompt is loaded from ``prompts/editor/v1.jinja`` relative to
``LlmConfig.prompts_fol``.

Example:
    ::

        llm_config = LlmParams().to_config()
        editor = RecipeCoreEditor(llm_config)
        updated = editor.invoke(
            old_recipe=recipe,
            old_step="Add 500g of salt",
            new_step="Use 5g of salt, not 500g",
        )
"""

from llm_core.chains.structured_chain import StructuredLLMChain
from llm_core.data_models.basemodel_kwargs import BaseModelKwargs
from llm_core.prompts.prompt_loader import PromptLoader
from llm_core.prompts.prompt_loader import PromptLoaderConfig

from kit_hub.config.llm_config import LlmConfig
from kit_hub.recipes.recipe_core import RecipeCore


class EditorInput(BaseModelKwargs):
    """Input model for the editor chain.

    Attributes:
        old_recipe: JSON-serialised ``RecipeCore`` (via
            ``RecipeCore.model_dump_json()``).
        old_step: The step instruction text that needs to be corrected.
        new_step: Natural-language instructions describing the correction.
    """

    old_recipe: str
    old_step: str
    new_step: str


class RecipeCoreEditor:
    """Apply a natural-language correction to a step in an existing recipe.

    Wraps a ``StructuredLLMChain`` using the ``editor`` versioned Jinja
    prompt.  All preparations and steps not targeted by the correction
    are returned unchanged.

    Args:
        llm_config: LLM chain configuration including the chat model and
            the prompts root folder.
    """

    def __init__(self, llm_config: LlmConfig) -> None:
        """Build the editor chain.

        Args:
            llm_config: LLM chain configuration.
        """
        prompt_str = PromptLoader(
            PromptLoaderConfig(
                base_prompt_fol=llm_config.prompts_fol,
                prompt_name="editor",
            )
        ).load_prompt()
        self._chain: StructuredLLMChain[EditorInput, RecipeCore] = StructuredLLMChain(
            chat_config=llm_config.chat_config,
            prompt_str=prompt_str,
            input_model=EditorInput,
            output_model=RecipeCore,
        )

    def invoke(
        self,
        old_recipe: RecipeCore,
        old_step: str,
        new_step: str,
    ) -> RecipeCore:
        """Apply a correction to a step synchronously.

        Args:
            old_recipe: The existing recipe to correct.
            old_step: The step instruction text that is wrong.
            new_step: Natural-language instructions for the correction.

        Returns:
            A new ``RecipeCore`` with the targeted step corrected.
        """
        return self._chain.invoke(
            EditorInput(
                old_recipe=old_recipe.model_dump_json(),
                old_step=old_step,
                new_step=new_step,
            )
        )

    async def ainvoke(
        self,
        old_recipe: RecipeCore,
        old_step: str,
        new_step: str,
    ) -> RecipeCore:
        """Apply a correction to a step asynchronously.

        Args:
            old_recipe: The existing recipe to correct.
            old_step: The step instruction text that is wrong.
            new_step: Natural-language instructions for the correction.

        Returns:
            A new ``RecipeCore`` with the targeted step corrected.
        """
        return await self._chain.ainvoke(
            EditorInput(
                old_recipe=old_recipe.model_dump_json(),
                old_step=old_step,
                new_step=new_step,
            )
        )
