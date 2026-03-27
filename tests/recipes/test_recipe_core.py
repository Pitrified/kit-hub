"""Tests for recipe core models.

Covers model creation, field defaults, validation, and JSON serialisation
for ``Ingredient``, ``Step``, ``Preparation``, and ``RecipeCore``.
"""

from pydantic import ValidationError
import pytest

from kit_hub.recipes.recipe_core import Ingredient
from kit_hub.recipes.recipe_core import Preparation
from kit_hub.recipes.recipe_core import RecipeCore
from kit_hub.recipes.recipe_core import Step
from kit_hub.recipes.recipe_enums import MealCourse
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.recipe_enums import StepType


class TestIngredient:
    """Tests for the Ingredient model."""

    def test_init(self) -> None:
        """Basic construction sets name and quantity."""
        ing = Ingredient(name="flour", quantity="500g")
        assert ing.name == "flour"
        assert ing.quantity == "500g"

    def test_serialise_to_dict(self) -> None:
        """model_dump returns expected keys and values."""
        ing = Ingredient(name="eggs", quantity="3")
        result = ing.model_dump()
        assert result == {"name": "eggs", "quantity": "3"}

    def test_roundtrip_json(self) -> None:
        """model_dump / model_validate_json round-trip is lossless."""
        ing = Ingredient(name="salt", quantity="1 tsp")
        restored = Ingredient.model_validate_json(ing.model_dump_json())
        assert restored == ing


class TestStep:
    """Tests for the Step model."""

    def test_default_type_is_text(self) -> None:
        """Step defaults to StepType.TEXT when type is omitted."""
        step = Step(instruction="Mix the ingredients.")
        assert step.type is StepType.TEXT

    def test_image_step(self) -> None:
        """Step can represent an image placeholder."""
        step = Step(type=StepType.IMAGE)
        assert step.type is StepType.IMAGE
        assert step.instruction is None

    def test_text_step_with_instruction(self) -> None:
        """Text step stores its instruction string."""
        step = Step(instruction="Preheat oven to 180 C.")
        assert step.instruction == "Preheat oven to 180 C."

    def test_serialise_to_dict(self) -> None:
        """model_dump reflects type as string value."""
        step = Step(instruction="Fold gently.")
        result = step.model_dump()
        assert result["type"] == "text"
        assert result["instruction"] == "Fold gently."


class TestPreparation:
    """Tests for the Preparation model."""

    def test_single_section_recipe_has_no_name(self) -> None:
        """preparation_name defaults to None for single-section recipes."""
        prep = Preparation(ingredients=[], steps=[])
        assert prep.preparation_name is None

    def test_named_preparation(self) -> None:
        """preparation_name is stored when provided."""
        prep = Preparation(preparation_name="Sauce", ingredients=[], steps=[])
        assert prep.preparation_name == "Sauce"

    def test_with_ingredients_and_steps(self) -> None:
        """Preparation stores non-empty ingredients and steps lists."""
        ing = Ingredient(name="butter", quantity="50g")
        step = Step(instruction="Melt the butter.")
        prep = Preparation(ingredients=[ing], steps=[step])
        assert len(prep.ingredients) == 1
        assert len(prep.steps) == 1
        assert prep.ingredients[0].name == "butter"
        assert prep.steps[0].instruction == "Melt the butter."

    def test_serialise_roundtrip(self) -> None:
        """Preparation round-trips through JSON without data loss."""
        ing = Ingredient(name="sugar", quantity="2 tbsp")
        step = Step(instruction="Stir until dissolved.")
        prep = Preparation(
            preparation_name="Syrup",
            ingredients=[ing],
            steps=[step],
        )
        restored = Preparation.model_validate_json(prep.model_dump_json())
        assert restored == prep


class TestRecipeCore:
    """Tests for the RecipeCore model."""

    def _simple_recipe(self) -> RecipeCore:
        """Return a minimal valid RecipeCore for reuse in tests."""
        ing = Ingredient(name="pasta", quantity="200g")
        step = Step(instruction="Boil water.")
        prep = Preparation(ingredients=[ing], steps=[step])
        return RecipeCore(name="Pasta al burro", preparations=[prep])

    def test_minimal_construction(self) -> None:
        """RecipeCore can be built with only name and preparations."""
        recipe = self._simple_recipe()
        assert recipe.name == "Pasta al burro"
        assert len(recipe.preparations) == 1

    def test_optional_fields_default_to_none(self) -> None:
        """notes, source, and meal_course default to None."""
        recipe = self._simple_recipe()
        assert recipe.notes is None
        assert recipe.source is None
        assert recipe.meal_course is None

    def test_with_all_optional_fields(self) -> None:
        """RecipeCore accepts all optional fields."""
        ing = Ingredient(name="lemon", quantity="1")
        prep = Preparation(ingredients=[ing], steps=[])
        recipe = RecipeCore(
            name="Lemon tart",
            preparations=[prep],
            notes=["Best served cold.", "Use unwaxed lemons."],
            source=RecipeSource.MANUAL,
            meal_course=MealCourse.DOLCI,
        )
        assert recipe.notes == ["Best served cold.", "Use unwaxed lemons."]
        assert recipe.source is RecipeSource.MANUAL
        assert recipe.meal_course is MealCourse.DOLCI

    def test_source_from_string(self) -> None:
        """RecipeCore accepts string values for StrEnum fields via model_validate."""
        prep = Preparation(ingredients=[], steps=[])
        recipe = RecipeCore.model_validate(
            {
                "name": "Test",
                "preparations": [prep.model_dump()],
                "source": "instagram",
            }
        )
        assert recipe.source is RecipeSource.INSTAGRAM

    def test_meal_course_from_string(self) -> None:
        """RecipeCore accepts string values for MealCourse via model_validate."""
        prep = Preparation(ingredients=[], steps=[])
        recipe = RecipeCore.model_validate(
            {
                "name": "Risotto",
                "preparations": [prep.model_dump()],
                "meal_course": "primi",
            }
        )
        assert recipe.meal_course is MealCourse.PRIMI

    def test_serialise_roundtrip(self) -> None:
        """RecipeCore round-trips through JSON without data loss."""
        recipe = self._simple_recipe()
        restored = RecipeCore.model_validate_json(recipe.model_dump_json())
        assert restored == recipe

    def test_multi_preparation_recipe(self) -> None:
        """RecipeCore supports multiple preparation sections."""
        base_prep = Preparation(
            preparation_name="Base",
            ingredients=[Ingredient(name="flour", quantity="300g")],
            steps=[Step(instruction="Mix flour and water.")],
        )
        sauce_prep = Preparation(
            preparation_name="Sauce",
            ingredients=[Ingredient(name="tomatoes", quantity="400g")],
            steps=[Step(instruction="Simmer sauce.")],
        )
        recipe = RecipeCore(
            name="Pizza Margherita",
            preparations=[base_prep, sauce_prep],
        )
        assert len(recipe.preparations) == 2
        assert recipe.preparations[0].preparation_name == "Base"
        assert recipe.preparations[1].preparation_name == "Sauce"

    def test_invalid_source_raises(self) -> None:
        """An unrecognised source string raises a ValidationError."""
        prep = Preparation(ingredients=[], steps=[])
        with pytest.raises(ValidationError):
            RecipeCore.model_validate(
                {
                    "name": "Test",
                    "preparations": [prep.model_dump()],
                    "source": "unknown_source",
                }
            )
