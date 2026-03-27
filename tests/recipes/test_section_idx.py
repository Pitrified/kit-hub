"""Tests for section index models.

Covers construction, field access, and Pydantic union type discrimination
for ``SectionPreparation``, ``SectionIngredient``, ``SectionStep``, and
``Section``.
"""

from pydantic import ValidationError
import pytest

from kit_hub.recipes.section_idx import Section
from kit_hub.recipes.section_idx import SectionIngredient
from kit_hub.recipes.section_idx import SectionPreparation
from kit_hub.recipes.section_idx import SectionStep


class TestSectionPreparation:
    """Tests for the SectionPreparation model."""

    def test_init(self) -> None:
        """SectionPreparation stores preparation_idx."""
        sp = SectionPreparation(preparation_idx=2)
        assert sp.preparation_idx == 2

    def test_zero_index(self) -> None:
        """preparation_idx of 0 is valid."""
        sp = SectionPreparation(preparation_idx=0)
        assert sp.preparation_idx == 0


class TestSectionIngredient:
    """Tests for the SectionIngredient model."""

    def test_init(self) -> None:
        """SectionIngredient stores both indices."""
        si = SectionIngredient(preparation_idx=1, ingredient_idx=3)
        assert si.preparation_idx == 1
        assert si.ingredient_idx == 3

    def test_is_subclass_of_section_preparation(self) -> None:
        """SectionIngredient is a subclass of SectionPreparation."""
        si = SectionIngredient(preparation_idx=0, ingredient_idx=0)
        assert isinstance(si, SectionPreparation)

    def test_serialise_roundtrip(self) -> None:
        """SectionIngredient round-trips through JSON."""
        si = SectionIngredient(preparation_idx=0, ingredient_idx=2)
        restored = SectionIngredient.model_validate_json(si.model_dump_json())
        assert restored == si


class TestSectionStep:
    """Tests for the SectionStep model."""

    def test_init(self) -> None:
        """SectionStep stores both indices."""
        ss = SectionStep(preparation_idx=0, step_idx=4)
        assert ss.preparation_idx == 0
        assert ss.step_idx == 4

    def test_is_subclass_of_section_preparation(self) -> None:
        """SectionStep is a subclass of SectionPreparation."""
        ss = SectionStep(preparation_idx=0, step_idx=0)
        assert isinstance(ss, SectionPreparation)

    def test_serialise_roundtrip(self) -> None:
        """SectionStep round-trips through JSON."""
        ss = SectionStep(preparation_idx=1, step_idx=0)
        restored = SectionStep.model_validate_json(ss.model_dump_json())
        assert restored == ss


class TestSection:
    """Tests for the Section discriminated union wrapper."""

    def test_section_step_wrapping(self) -> None:
        """Section accepts a SectionStep instance."""
        ss = SectionStep(preparation_idx=0, step_idx=2)
        sec = Section(section=ss)
        assert isinstance(sec.section, SectionStep)
        assert sec.section.step_idx == 2

    def test_section_ingredient_wrapping(self) -> None:
        """Section accepts a SectionIngredient instance."""
        si = SectionIngredient(preparation_idx=1, ingredient_idx=0)
        sec = Section(section=si)
        assert isinstance(sec.section, SectionIngredient)
        assert sec.section.ingredient_idx == 0

    def test_section_from_dict_step(self) -> None:
        """Section resolves SectionStep from a raw dict with step_idx."""
        sec = Section.model_validate({"section": {"preparation_idx": 0, "step_idx": 3}})
        assert isinstance(sec.section, SectionStep)
        assert sec.section.step_idx == 3

    def test_section_from_dict_ingredient(self) -> None:
        """Section resolves SectionIngredient from a raw dict with ingredient_idx."""
        sec = Section.model_validate(
            {"section": {"preparation_idx": 2, "ingredient_idx": 1}}
        )
        assert isinstance(sec.section, SectionIngredient)
        assert sec.section.ingredient_idx == 1

    def test_section_missing_required_field_raises(self) -> None:
        """Section raises ValidationError when no concrete type can be matched."""
        with pytest.raises(ValidationError):
            Section.model_validate({"section": {"preparation_idx": 0}})
