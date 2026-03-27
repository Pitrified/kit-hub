"""LLM configuration model.

Defines the shape of the LLM chain settings.  No environment variables
are read here - that belongs in ``LlmParams``.

See Also:
    ``LlmParams`` - the companion class that loads actual values.
    ``docs/guides/params_config.md`` - Config / Params pattern reference.
"""

from pathlib import Path

from llm_core.chat.config.base import ChatConfig

from kit_hub.data_models.basemodel_kwargs import BaseModelKwargs


class LlmConfig(BaseModelKwargs):
    """LLM chain configuration.

    Attributes:
        chat_config: Provider and model configuration used to create the
            underlying chat model.  Any ``ChatConfig`` subclass is accepted
            (e.g. ``ChatOpenAIConfig``, ``FakeChatModelConfig`` in tests).
        prompts_fol: Root folder containing versioned Jinja prompt
            subdirectories (``transcriber/``, ``editor/``, etc.).
    """

    chat_config: ChatConfig
    prompts_fol: Path
