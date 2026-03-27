"""Tests for RecipeCoreEditor.

Uses ``FakeChatModelConfig`` to avoid real API calls.  The fake model
returns a pre-loaded JSON string representing the corrected ``RecipeCore``.
"""

from pathlib import Path

from langchain_core.messages import AIMessage
from llm_core.testing.fake_chat_model import FakeChatModelConfig
import pytest

from kit_hub.config.llm_config import LlmConfig
from kit_hub.llm.editor import EditorInput
from kit_hub.llm.editor import RecipeCoreEditor
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step


@pytest.fixture
def prompts_fol() -> Path:
    """Return the repo-level prompts folder."""
    return Path(__file__).parents[2] / "prompts"


@pytest.fixture
def sample_recipe() -> RecipeCore:
    """Return a minimal recipe used as the 'old_recipe' in editor tests."""
    return RecipeCore(
        name="Pasta al Pomodoro",
        preparations=[
            Preparation(
                ingredients=[
                    Ingredient(name="pasta", quantity="500g"),
                    Ingredient(name="salt", quantity="500g"),
                ],
                steps=[
                    Step(instruction="Boil pasta."),
                    Step(instruction="Add 500g of salt."),
                ],
            )
        ],
    )


@pytest.fixture
def corrected_recipe_json(sample_recipe: RecipeCore) -> str:
    """Return a corrected recipe that fixes the salt quantity."""
    corrected = sample_recipe.model_copy(deep=True)
    corrected.preparations[0].ingredients[1].quantity = "5g"
    corrected.preparations[0].steps[1].instruction = "Add 5g of salt."
    return corrected.model_dump_json()


@pytest.fixture
def llm_config(prompts_fol: Path, corrected_recipe_json: str) -> LlmConfig:
    """Return an LlmConfig backed by a fake model returning the corrected recipe."""
    fake_config = FakeChatModelConfig(
        responses=[AIMessage(content=corrected_recipe_json)]
    )
    return LlmConfig(chat_config=fake_config, prompts_fol=prompts_fol)


class TestEditorInput:
    """Tests for the EditorInput model."""

    def test_init(self) -> None:
        """EditorInput stores all three fields."""
        inp = EditorInput(
            old_recipe='{"name": "test"}',
            old_step="old step",
            new_step="new step",
        )
        assert inp.old_recipe == '{"name": "test"}'
        assert inp.old_step == "old step"
        assert inp.new_step == "new step"

    def test_to_kw(self) -> None:
        """to_kw returns all fields at top level."""
        inp = EditorInput(
            old_recipe="recipe json",
            old_step="wrong step",
            new_step="correct step",
        )
        kw = inp.to_kw()
        assert set(kw.keys()) == {"old_recipe", "old_step", "new_step"}


class TestRecipeCoreEditor:
    """Tests for RecipeCoreEditor."""

    def test_init_builds_chain(self, llm_config: LlmConfig) -> None:
        """Build editor chain without raising on valid config."""
        editor = RecipeCoreEditor(llm_config)
        assert isinstance(editor, RecipeCoreEditor)

    def test_invoke_returns_corrected_recipe(
        self,
        llm_config: LlmConfig,
        sample_recipe: RecipeCore,
    ) -> None:
        """Invoke returns a corrected RecipeCore from the fake model response."""
        editor = RecipeCoreEditor(llm_config)
        result = editor.invoke(
            old_recipe=sample_recipe,
            old_step="Add 500g of salt.",
            new_step="Use 5g of salt, not 500g.",
        )
        assert isinstance(result, RecipeCore)
        assert result.name == "Pasta al Pomodoro"
        assert result.preparations[0].steps[1].instruction == "Add 5g of salt."
        assert result.preparations[0].ingredients[1].quantity == "5g"

    @pytest.mark.asyncio
    async def test_ainvoke_returns_corrected_recipe(
        self,
        llm_config: LlmConfig,
        sample_recipe: RecipeCore,
    ) -> None:
        """Ainvoke returns the same corrected recipe as invoke."""
        editor = RecipeCoreEditor(llm_config)
        result = await editor.ainvoke(
            old_recipe=sample_recipe,
            old_step="Add 500g of salt.",
            new_step="Use 5g of salt, not 500g.",
        )
        assert isinstance(result, RecipeCore)
        assert result.preparations[0].steps[1].instruction == "Add 5g of salt."

    def test_invoke_serialises_old_recipe_as_json(
        self,
        sample_recipe: RecipeCore,
    ) -> None:
        """Verify old_recipe JSON round-trip before the editor chain receives it."""
        serialised = sample_recipe.model_dump_json()
        restored = RecipeCore.model_validate_json(serialised)
        assert restored.name == sample_recipe.name

    def test_missing_prompts_fol_raises(
        self,
        tmp_path: Path,
        corrected_recipe_json: str,
    ) -> None:
        """FileNotFoundError raised when prompts folder has no vN.jinja."""
        fake_config = FakeChatModelConfig(
            responses=[AIMessage(content=corrected_recipe_json)]
        )
        bad_config = LlmConfig(chat_config=fake_config, prompts_fol=tmp_path)
        with pytest.raises(FileNotFoundError):
            RecipeCoreEditor(bad_config)
