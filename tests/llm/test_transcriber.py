"""Tests for RecipeCoreTranscriber.

Uses ``FakeChatModelConfig`` from llm-core to avoid real API calls.
The fake model returns a pre-loaded JSON string that validates against
``RecipeCore``.
"""

import json
from pathlib import Path

from langchain_core.messages import AIMessage
from llm_core.testing.fake_chat_model import FakeChatModelConfig
import pytest

from kit_hub.config.llm_config import LlmConfig
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.llm.transcriber import TranscriberInput
from kit_hub.recipes.recipe_core import RecipeCore


@pytest.fixture
def prompts_fol() -> Path:
    """Return the repo-level prompts folder."""
    return Path(__file__).parents[2] / "prompts"


@pytest.fixture
def minimal_recipe_json() -> str:
    """Return a minimal valid RecipeCore as a JSON string."""
    recipe = RecipeCore.model_validate(
        {
            "name": "Simple Pasta",
            "preparations": [
                {
                    "ingredients": [{"name": "pasta", "quantity": "200g"}],
                    "steps": [{"instruction": "Boil pasta for 10 minutes."}],
                }
            ],
        }
    )
    return recipe.model_dump_json()


@pytest.fixture
def llm_config(prompts_fol: Path, minimal_recipe_json: str) -> LlmConfig:
    """Return an LlmConfig backed by a deterministic fake chat model."""
    fake_config = FakeChatModelConfig(
        responses=[AIMessage(content=minimal_recipe_json)]
    )
    return LlmConfig(chat_config=fake_config, prompts_fol=prompts_fol)


class TestTranscriberInput:
    """Tests for the TranscriberInput model."""

    def test_init(self) -> None:
        """TranscriberInput stores recipe_text."""
        inp = TranscriberInput(recipe_text="Boil water.")
        assert inp.recipe_text == "Boil water."

    def test_to_kw(self) -> None:
        """to_kw returns recipe_text at top level."""
        inp = TranscriberInput(recipe_text="Mix flour and eggs.")
        kw = inp.to_kw()
        assert kw == {"recipe_text": "Mix flour and eggs."}


class TestRecipeCoreTranscriber:
    """Tests for RecipeCoreTranscriber."""

    def test_init_builds_chain(self, llm_config: LlmConfig) -> None:
        """Build transcriber chain without raising on valid config."""
        transcriber = RecipeCoreTranscriber(llm_config)
        assert isinstance(transcriber, RecipeCoreTranscriber)

    def test_invoke_returns_recipe_core(self, llm_config: LlmConfig) -> None:
        """Invoke returns a RecipeCore parsed from the fake model response."""
        transcriber = RecipeCoreTranscriber(llm_config)
        result = transcriber.invoke("Boil pasta for 10 minutes.")
        assert isinstance(result, RecipeCore)
        assert result.name == "Simple Pasta"
        assert len(result.preparations) == 1
        prep = result.preparations[0]
        assert prep.ingredients[0].name == "pasta"
        assert prep.steps[0].instruction == "Boil pasta for 10 minutes."

    @pytest.mark.asyncio
    async def test_ainvoke_returns_recipe_core(self, llm_config: LlmConfig) -> None:
        """Ainvoke returns the same output as invoke."""
        transcriber = RecipeCoreTranscriber(llm_config)
        result = await transcriber.ainvoke("Boil pasta for 10 minutes.")
        assert isinstance(result, RecipeCore)
        assert result.name == "Simple Pasta"

    def test_missing_prompts_fol_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when prompts folder has no vN.jinja."""
        fake_config = FakeChatModelConfig(
            responses=[AIMessage(content='{"name": "x", "preparations": []}')]
        )
        bad_config = LlmConfig(
            chat_config=fake_config,
            prompts_fol=tmp_path,
        )
        with pytest.raises(FileNotFoundError):
            RecipeCoreTranscriber(bad_config)

    def test_invoke_preserves_recipe_structure(self, llm_config: LlmConfig) -> None:
        """All recipe fields returned from the chain are valid."""
        transcriber = RecipeCoreTranscriber(llm_config)
        result = transcriber.invoke("Any recipe text.")
        # RecipeCore validates on construction - if we get here, it's valid
        assert result.preparations is not None
        assert len(result.preparations) >= 0


class TestRecipeCoreTranscriberMultiResponse:
    """Tests for multi-response cycling behaviour."""

    def test_cyclic_responses(self, prompts_fol: Path) -> None:
        """FakeChatModel cycles through responses in round-robin order."""
        recipe_a = RecipeCore.model_validate(
            {
                "name": "Recipe A",
                "preparations": [
                    {"ingredients": [], "steps": [{"instruction": "Step A."}]}
                ],
            }
        )
        recipe_b = RecipeCore.model_validate(
            {
                "name": "Recipe B",
                "preparations": [
                    {"ingredients": [], "steps": [{"instruction": "Step B."}]}
                ],
            }
        )
        fake_config = FakeChatModelConfig(
            responses=[
                AIMessage(content=recipe_a.model_dump_json()),
                AIMessage(content=recipe_b.model_dump_json()),
            ]
        )
        llm_config = LlmConfig(chat_config=fake_config, prompts_fol=prompts_fol)
        transcriber = RecipeCoreTranscriber(llm_config)

        result_a = transcriber.invoke("First call")
        result_b = transcriber.invoke("Second call")

        assert result_a.name == "Recipe A"
        assert result_b.name == "Recipe B"


def test_transcriber_end_to_end(prompts_fol: Path, minimal_recipe_json: str) -> None:
    """Module-level smoke test: transcriber returns valid RecipeCore."""
    fake_config = FakeChatModelConfig(
        responses=[AIMessage(content=minimal_recipe_json)]
    )
    llm_config = LlmConfig(chat_config=fake_config, prompts_fol=prompts_fol)
    transcriber = RecipeCoreTranscriber(llm_config)
    recipe = transcriber.invoke("Simple recipe text.")
    assert recipe.name == "Simple Pasta"
    assert json.loads(recipe.model_dump_json())["name"] == "Simple Pasta"
