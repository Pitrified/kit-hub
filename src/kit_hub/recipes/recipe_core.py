"""Core recipe data models.

These Pydantic models represent the canonical recipe schema that the LLM
produces (via ``RecipeCoreTranscriber``) and that is stored as JSON in the
database.  DB-layer concerns such as ``user_id``, ``is_public``, and
``sort_index`` do not belong here.

Models:
    Ingredient: Single ingredient with a name and free-form quantity string.
    Step: One preparation step, either a text instruction or an image.
    Preparation: A named section grouping ingredients and steps.
    RecipeCore: Top-level recipe container holding one or more preparations.
"""

from pydantic import BaseModel

from kit_hub.recipes.recipe_enums import MealCourse
from kit_hub.recipes.recipe_enums import RecipeSource
from kit_hub.recipes.recipe_enums import StepType


class Ingredient(BaseModel):
    """A single ingredient entry.

    Attributes:
        name: Human-readable ingredient name (e.g. ``"flour"``).
        quantity: Amount and unit as a single free-form string
            (e.g. ``"500g"``, ``"2 cups"``).
    """

    name: str
    quantity: str


class Step(BaseModel):
    """One preparation step.

    Attributes:
        type: Content type of the step - text instruction or image placeholder.
            Defaults to ``StepType.TEXT``.
        instruction: The instruction text.  ``None`` when the step is an
            image placeholder without an associated caption.
    """

    type: StepType = StepType.TEXT
    instruction: str | None = None


class Preparation(BaseModel):
    """A named preparation section within a recipe.

    Single-section recipes set ``preparation_name`` to ``None`` so
    the UI can omit the heading.  Multi-section recipes (e.g. a dish with
    a sauce and a base) each carry a distinct name.

    Attributes:
        preparation_name: Display name for this section.
            ``None`` for single-section recipes.
        ingredients: Ordered list of ingredients used in this section.
        steps: Ordered list of preparation steps.
    """

    preparation_name: str | None = None
    ingredients: list[Ingredient]
    steps: list[Step]


class RecipeCore(BaseModel):
    """Top-level recipe container.

    This is the schema the LLM produces and what gets stored as JSON in
    the database.  All DB-layer metadata (user ownership, visibility,
    sort priority) is stored separately in the ORM layer.

    Attributes:
        name: Human-readable recipe name.
        preparations: One or more preparation sections.  The order is
            significant - it mirrors the intended cooking sequence.
        notes: Optional free-text notes or tips for the recipe as a whole
            (e.g. storage advice, variations).
        source: How the recipe entered the system.  ``None`` when unknown.
        meal_course: Italian meal-course classification.  ``None`` when
            not yet classified.
    """

    name: str
    preparations: list[Preparation]
    notes: list[str] | None = None
    source: RecipeSource | None = None
    meal_course: MealCourse | None = None
