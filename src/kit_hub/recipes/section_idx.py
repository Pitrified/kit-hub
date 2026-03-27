"""Section index models for pointing at recipe sub-elements.

These models let the LLM (via ``SectionIdxFinder``) return a precise
pointer to a preparation, ingredient, or step inside a ``RecipeCore`` by
index.

Models:
    SectionPreparation: Points at a preparation section.
    SectionIngredient: Points at an ingredient within a preparation.
    SectionStep: Points at a step within a preparation.
    Section: Wrapper that holds any concrete section pointer.

Type aliases:
    SectionGen: Union of all concrete pointer types.
"""

from pydantic import BaseModel


class SectionPreparation(BaseModel):
    """A pointer to a preparation section.

    Attributes:
        preparation_idx: Zero-based index into ``RecipeCore.preparations``.
    """

    preparation_idx: int


class SectionIngredient(SectionPreparation):
    """A pointer to an ingredient within a preparation.

    Attributes:
        preparation_idx: Zero-based index into ``RecipeCore.preparations``.
        ingredient_idx: Zero-based index into ``Preparation.ingredients``.
    """

    ingredient_idx: int


class SectionStep(SectionPreparation):
    """A pointer to a step within a preparation.

    Attributes:
        preparation_idx: Zero-based index into ``RecipeCore.preparations``.
        step_idx: Zero-based index into ``Preparation.steps``.
    """

    step_idx: int


type SectionGen = SectionStep | SectionIngredient


class Section(BaseModel):
    """Wrapper holding any concrete section pointer.

    The ``section`` field accepts either a ``SectionStep`` or a
    ``SectionIngredient``.  Pydantic resolves the correct type at
    validation time based on which required fields are present in the
    input data.

    Attributes:
        section: The concrete pointer - either a step or ingredient index.
    """

    section: SectionGen
