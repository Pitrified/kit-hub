"""Tests for SectionIdxFinder.

Uses ``FakeChatModelConfig`` to avoid real API calls.  The fake model
returns a pre-loaded JSON string representing a ``Section`` pointer.
"""

from pathlib import Path

from langchain_core.messages import AIMessage
from llm_core.testing.fake_chat_model import FakeChatModelConfig
import pytest

from kit_hub.config.llm_config import LlmConfig
from kit_hub.llm.section_finder import SectionFinderInput
from kit_hub.llm.section_finder import SectionIdxFinder
from kit_hub.recipes.section_idx import Section
from kit_hub.recipes.section_idx import SectionIngredient
from kit_hub.recipes.section_idx import SectionStep


@pytest.fixture
def prompts_fol() -> Path:
    """Return the repo-level prompts folder."""
    return Path(__file__).parents[2] / "prompts"


def _make_llm_config(prompts_fol: Path, section_json: str) -> LlmConfig:
    """Create an LlmConfig with a fake model returning *section_json*."""
    fake_config = FakeChatModelConfig(responses=[AIMessage(content=section_json)])
    return LlmConfig(chat_config=fake_config, prompts_fol=prompts_fol)


class TestSectionFinderInput:
    """Tests for the SectionFinderInput model."""

    def test_init(self) -> None:
        """SectionFinderInput stores user_instruction."""
        inp = SectionFinderInput(user_instruction="step 2 of the sauce")
        assert inp.user_instruction == "step 2 of the sauce"

    def test_to_kw(self) -> None:
        """to_kw returns user_instruction at top level."""
        inp = SectionFinderInput(user_instruction="the first ingredient")
        kw = inp.to_kw()
        assert kw == {"user_instruction": "the first ingredient"}


class TestSectionIdxFinderStep:
    """Tests for SectionIdxFinder returning a SectionStep."""

    @pytest.fixture
    def step_section_json(self) -> str:
        """JSON for SectionStep(preparation_idx=1, step_idx=2)."""
        section = Section(section=SectionStep(preparation_idx=1, step_idx=2))
        return section.model_dump_json()

    @pytest.fixture
    def llm_config(self, prompts_fol: Path, step_section_json: str) -> LlmConfig:
        """LlmConfig with fake model returning a SectionStep."""
        return _make_llm_config(prompts_fol, step_section_json)

    def test_init_builds_chain(self, llm_config: LlmConfig) -> None:
        """Build finder chain without raising on valid config."""
        finder = SectionIdxFinder(llm_config)
        assert isinstance(finder, SectionIdxFinder)

    def test_invoke_returns_section_step(self, llm_config: LlmConfig) -> None:
        """Invoke returns Section wrapping a SectionStep."""
        finder = SectionIdxFinder(llm_config)
        result = finder.invoke("step 3 of the sauce preparation")
        assert isinstance(result, Section)
        assert isinstance(result.section, SectionStep)
        assert result.section.preparation_idx == 1
        assert result.section.step_idx == 2

    @pytest.mark.asyncio
    async def test_ainvoke_returns_section_step(self, llm_config: LlmConfig) -> None:
        """Ainvoke returns the same Section as invoke."""
        finder = SectionIdxFinder(llm_config)
        result = await finder.ainvoke("step 3 of the sauce preparation")
        assert isinstance(result, Section)
        assert isinstance(result.section, SectionStep)
        assert result.section.step_idx == 2


class TestSectionIdxFinderIngredient:
    """Tests for SectionIdxFinder returning a SectionIngredient."""

    @pytest.fixture
    def ingredient_section_json(self) -> str:
        """JSON for SectionIngredient(preparation_idx=0, ingredient_idx=1)."""
        section = Section(
            section=SectionIngredient(preparation_idx=0, ingredient_idx=1)
        )
        return section.model_dump_json()

    @pytest.fixture
    def llm_config(self, prompts_fol: Path, ingredient_section_json: str) -> LlmConfig:
        """LlmConfig with fake model returning a SectionIngredient."""
        return _make_llm_config(prompts_fol, ingredient_section_json)

    def test_invoke_returns_section_ingredient(self, llm_config: LlmConfig) -> None:
        """Invoke returns Section wrapping a SectionIngredient."""
        finder = SectionIdxFinder(llm_config)
        result = finder.invoke("the second ingredient")
        assert isinstance(result, Section)
        assert isinstance(result.section, SectionIngredient)
        assert result.section.preparation_idx == 0
        assert result.section.ingredient_idx == 1


class TestSectionIdxFinderErrors:
    """Error-case tests for SectionIdxFinder."""

    def test_missing_prompts_fol_raises(self, tmp_path: Path) -> None:
        """FileNotFoundError raised when prompts folder has no vN.jinja."""
        section_json = '{"section": {"preparation_idx": 0, "step_idx": 0}}'
        fake_config = FakeChatModelConfig(responses=[AIMessage(content=section_json)])
        bad_config = LlmConfig(chat_config=fake_config, prompts_fol=tmp_path)
        with pytest.raises(FileNotFoundError):
            SectionIdxFinder(bad_config)
