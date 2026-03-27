"""SectionIdxFinder - maps natural-language location queries to section indices.

Given a natural-language description of a recipe section such as
"step 2 of the sauce preparation", the finder returns a ``Section``
containing a ``SectionStep`` or ``SectionIngredient`` pointer with
zero-based indices.

The prompt is loaded from ``prompts/section_finder/v1.jinja`` relative to
``LlmConfig.prompts_fol``.

Example:
    ::

        llm_config = LlmParams().to_config()
        finder = SectionIdxFinder(llm_config)
        section = finder.invoke("step 2 of the sauce")
        # section.section -> SectionStep(preparation_idx=1, step_idx=1)
"""

from llm_core.chains.structured_chain import StructuredLLMChain
from llm_core.data_models.basemodel_kwargs import BaseModelKwargs
from llm_core.prompts.prompt_loader import PromptLoader
from llm_core.prompts.prompt_loader import PromptLoaderConfig

from kit_hub.config.llm_config import LlmConfig
from kit_hub.recipes.section_idx import Section


class SectionFinderInput(BaseModelKwargs):
    """Input model for the section finder chain.

    Attributes:
        user_instruction: Natural-language description of the recipe
            section to locate (e.g. ``"step 2 of the sauce"``).
    """

    user_instruction: str


class SectionIdxFinder:
    """Map a natural-language location query to a section index pointer.

    Wraps a ``StructuredLLMChain`` using the ``section_finder`` versioned
    Jinja prompt.  Returns a ``Section`` with a ``SectionStep`` or
    ``SectionIngredient`` discriminated union holding zero-based indices.

    Args:
        llm_config: LLM chain configuration including the chat model and
            the prompts root folder.
    """

    def __init__(self, llm_config: LlmConfig) -> None:
        """Build the section finder chain.

        Args:
            llm_config: LLM chain configuration.
        """
        prompt_str = PromptLoader(
            PromptLoaderConfig(
                base_prompt_fol=llm_config.prompts_fol,
                prompt_name="section_finder",
            )
        ).load_prompt()
        self._chain: StructuredLLMChain[SectionFinderInput, Section] = (
            StructuredLLMChain(
                chat_config=llm_config.chat_config,
                prompt_str=prompt_str,
                input_model=SectionFinderInput,
                output_model=Section,
            )
        )

    def invoke(self, user_instruction: str) -> Section:
        """Locate a recipe section synchronously.

        Args:
            user_instruction: Natural-language description of the section.

        Returns:
            ``Section`` with a ``SectionStep`` or ``SectionIngredient``
            pointer carrying zero-based preparation and element indices.
        """
        return self._chain.invoke(SectionFinderInput(user_instruction=user_instruction))

    async def ainvoke(self, user_instruction: str) -> Section:
        """Locate a recipe section asynchronously.

        Args:
            user_instruction: Natural-language description of the section.

        Returns:
            ``Section`` with a ``SectionStep`` or ``SectionIngredient``
            pointer carrying zero-based preparation and element indices.
        """
        return await self._chain.ainvoke(
            SectionFinderInput(user_instruction=user_instruction)
        )
