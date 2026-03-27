"""Tests for TagExtractor.

Uses ``FakeChatModelConfig`` to avoid real API calls.  The fake model
returns a pre-loaded JSON string representing a ``TagExtractorOutput``
with a list of ``RecipeTagAssignment`` objects.
"""

from pathlib import Path

from langchain_core.messages import AIMessage
from llm_core.testing.fake_chat_model import FakeChatModelConfig
import pytest

from kit_hub.config.llm_config import LlmConfig
from kit_hub.llm.tag_extractor import TagExtractor
from kit_hub.llm.tag_extractor import TagExtractorInput
from kit_hub.llm.tag_extractor import TagExtractorOutput
from kit_hub.llm.tag_extractor import _recipe_to_text
from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_enums import StepType
from kit_hub.recipes.tag import RecipeTagAssignment


@pytest.fixture
def prompts_fol() -> Path:
    """Return the repo-level prompts folder."""
    return Path(__file__).parents[2] / "prompts"


@pytest.fixture
def sample_recipe() -> RecipeCore:
    """Return a minimal pasta recipe for tag extraction tests."""
    return RecipeCore(
        name="Pasta al Pomodoro",
        preparations=[
            Preparation(
                preparation_name="Main",
                ingredients=[
                    Ingredient(name="pasta", quantity="200g"),
                    Ingredient(name="tomato sauce", quantity="300ml"),
                ],
                steps=[
                    Step(instruction="Boil pasta."),
                    Step(instruction="Add sauce and serve."),
                ],
            )
        ],
    )


@pytest.fixture
def tags_json() -> str:
    """JSON for a TagExtractorOutput with two tags."""
    output = TagExtractorOutput(
        tags=[
            RecipeTagAssignment(tag_name="pasta", confidence=0.95, origin="ai"),
            RecipeTagAssignment(tag_name="italian", confidence=0.85, origin="ai"),
        ]
    )
    return output.model_dump_json()


@pytest.fixture
def llm_config(prompts_fol: Path, tags_json: str) -> LlmConfig:
    """Return an LlmConfig backed by a fake model returning tags."""
    fake_config = FakeChatModelConfig(responses=[AIMessage(content=tags_json)])
    return LlmConfig(chat_config=fake_config, prompts_fol=prompts_fol)


class TestTagExtractorInput:
    """Tests for the TagExtractorInput model."""

    def test_init(self) -> None:
        """TagExtractorInput stores recipe_name and recipe_text."""
        inp = TagExtractorInput(recipe_name="Pasta", recipe_text="Boil pasta.")
        assert inp.recipe_name == "Pasta"
        assert inp.recipe_text == "Boil pasta."

    def test_to_kw(self) -> None:
        """to_kw returns both fields at top level."""
        inp = TagExtractorInput(recipe_name="Pasta", recipe_text="Boil pasta.")
        kw = inp.to_kw()
        assert set(kw.keys()) == {"recipe_name", "recipe_text"}


class TestTagExtractorOutput:
    """Tests for the TagExtractorOutput model."""

    def test_init(self) -> None:
        """TagExtractorOutput stores a list of RecipeTagAssignment."""
        tags = [RecipeTagAssignment(tag_name="vegan", confidence=0.9, origin="ai")]
        output = TagExtractorOutput(tags=tags)
        assert len(output.tags) == 1
        assert output.tags[0].tag_name == "vegan"

    def test_empty_tags(self) -> None:
        """TagExtractorOutput accepts an empty tag list."""
        output = TagExtractorOutput(tags=[])
        assert output.tags == []


class TestRecipeToText:
    """Tests for the _recipe_to_text helper."""

    def test_renders_preparation_name(self, sample_recipe: RecipeCore) -> None:
        """Preparation name appears as a heading in the output."""
        text = _recipe_to_text(sample_recipe)
        assert "## Main" in text

    def test_renders_ingredients(self, sample_recipe: RecipeCore) -> None:
        """Ingredient names and quantities appear in the output."""
        text = _recipe_to_text(sample_recipe)
        assert "pasta" in text
        assert "200g" in text

    def test_renders_steps(self, sample_recipe: RecipeCore) -> None:
        """Step instructions appear in the output."""
        text = _recipe_to_text(sample_recipe)
        assert "Boil pasta." in text

    def test_no_preparation_name(self) -> None:
        """Section without a name does not render a heading."""
        recipe = RecipeCore(
            name="Simple",
            preparations=[
                Preparation(
                    ingredients=[Ingredient(name="egg", quantity="2")],
                    steps=[Step(instruction="Fry.")],
                )
            ],
        )
        text = _recipe_to_text(recipe)
        assert "##" not in text
        assert "egg" in text

    def test_skips_image_steps(self) -> None:
        """Steps with no instruction text (image placeholders) are omitted."""
        recipe = RecipeCore(
            name="Photo Recipe",
            preparations=[
                Preparation(
                    ingredients=[],
                    steps=[
                        Step(type=StepType.IMAGE),
                        Step(instruction="Serve."),
                    ],
                )
            ],
        )
        text = _recipe_to_text(recipe)
        assert "Serve." in text
        # The image step has no instruction, so only indexed steps with
        # instructions appear; total numbered lines should be 1
        numbered = [
            line for line in text.splitlines() if line.strip().startswith(("1.", "2."))
        ]
        assert len(numbered) == 1


class TestTagExtractor:
    """Tests for TagExtractor."""

    def test_init_builds_chain(self, llm_config: LlmConfig) -> None:
        """Build extractor chain without raising on valid config."""
        extractor = TagExtractor(llm_config)
        assert isinstance(extractor, TagExtractor)

    def test_invoke_returns_tag_list(
        self, llm_config: LlmConfig, sample_recipe: RecipeCore
    ) -> None:
        """Invoke returns a list of RecipeTagAssignment."""
        extractor = TagExtractor(llm_config)
        tags = extractor.invoke(sample_recipe)
        assert isinstance(tags, list)
        assert len(tags) == 2
        names = {t.tag_name for t in tags}
        assert "pasta" in names
        assert "italian" in names

    def test_invoke_tag_confidence_range(
        self, llm_config: LlmConfig, sample_recipe: RecipeCore
    ) -> None:
        """All confidence scores are in [0.0, 1.0]."""
        extractor = TagExtractor(llm_config)
        tags = extractor.invoke(sample_recipe)
        for tag in tags:
            assert 0.0 <= tag.confidence <= 1.0

    def test_invoke_tag_origin_is_ai(
        self, llm_config: LlmConfig, sample_recipe: RecipeCore
    ) -> None:
        """All tags from the extractor have origin='ai'."""
        extractor = TagExtractor(llm_config)
        tags = extractor.invoke(sample_recipe)
        for tag in tags:
            assert tag.origin == "ai"

    @pytest.mark.asyncio
    async def test_ainvoke_returns_tag_list(
        self, llm_config: LlmConfig, sample_recipe: RecipeCore
    ) -> None:
        """Ainvoke returns the same tag list as invoke."""
        extractor = TagExtractor(llm_config)
        tags = await extractor.ainvoke(sample_recipe)
        assert isinstance(tags, list)
        assert len(tags) == 2

    def test_missing_prompts_fol_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when prompts folder has no vN.jinja."""
        fake_config = FakeChatModelConfig(responses=[AIMessage(content='{"tags": []}')])
        bad_config = LlmConfig(chat_config=fake_config, prompts_fol=tmp_path)
        with pytest.raises(FileNotFoundError):
            TagExtractor(bad_config)
