# Block 1: Recipe data model + validation

Parent plan: [00-plan.md](00-plan.md)

## Goal

Port the canonical recipe schema to clean Pydantic models in `src/kit_hub/recipes/`. This is the foundation for every other block.

## Source material

- `recipamatic`: `RecipeCore`, `Preparation`, `Ingredient`, `Step`, `StepType`, `RecipeNote`, `Note`, `RecipeSource`
- `recipinator`: `Tag`, `RecipeTagLink` (confidence + origin), `Author`
- `cookbook`: 8 Italian meal courses as categories

## Deliverables

### 1. Enums - `src/kit_hub/recipes/recipe_enums.py`

```python
class StepType(StrEnum):
    TEXT = "text"
    IMAGE = "image"

class RecipeSource(StrEnum):
    INSTAGRAM = "instagram"
    VOICE_NOTE = "voice_note"
    MANUAL = "manual"

class MealCourse(StrEnum):
    """Italian meal course buckets from cookbook."""
    PANI = "pani"
    ANTIPASTI = "antipasti"
    PRIMI = "primi"
    SECONDI = "secondi"
    FRITTI = "fritti"
    CONTORNI = "contorni"
    DOLCI = "dolci"
    ALCOL = "alcol"
```

### 2. Core recipe models - `src/kit_hub/recipes/recipe_core.py`

```python
class Ingredient(BaseModel):
    name: str
    quantity: str  # amount + unit as single string, e.g. "500g", "2 cups"

class Step(BaseModel):
    type: StepType = StepType.TEXT
    instruction: str | None = None

class Preparation(BaseModel):
    preparation_name: str | None = None  # None for single-section recipes
    ingredients: list[Ingredient]
    steps: list[Step]

class RecipeCore(BaseModel):
    name: str
    preparations: list[Preparation]
    notes: list[str] | None = None
    source: RecipeSource | None = None
    meal_course: MealCourse | None = None
    # user_id, is_public, sort_index live in the DB layer, not here
    # this model is what the LLM produces and what gets stored as JSON
```

Design decisions:
- `user_id`, `is_public`, `sort_index` are DB-layer concerns, not part of the LLM output model
- `RecipeCore` is the LLM-facing schema (what `RecipeCoreTranscriber` outputs)
- `meal_course` is optional; AI can attempt to classify but humans can override
- `StepType.IMAGE` is included for future use (cookbook has image steps)

### 3. Section index models - `src/kit_hub/recipes/section_idx.py`

```python
class SectionPreparation(BaseModel):
    preparation_idx: int

class SectionIngredient(SectionPreparation):
    ingredient_idx: int

class SectionStep(SectionPreparation):
    step_idx: int

type SectionGen = SectionStep | SectionIngredient

class Section(BaseModel):
    section: SectionGen
```

### 4. Tag model - `src/kit_hub/recipes/tag.py`

```python
class Tag(BaseModel):
    name: str
    usefulness: int = 0

class RecipeTagAssignment(BaseModel):
    tag_name: str
    confidence: float  # 0.0 to 1.0
    origin: str  # "ai" or "manual"
```

### 5. Voice note models - `src/kit_hub/recipes/recipe_note.py`

```python
class Note(BaseModel):
    text: str
    timestamp: datetime = Field(default_factory=datetime.now)

class RecipeNote(BaseModel):
    start_timestamp: datetime = Field(default_factory=datetime.now)
    notes: list[Note] = Field(default_factory=list)

    def add_note(self, text: str) -> None: ...
    def to_string(self) -> str: ...
        # Returns "MM:SS: note text\n..." relative to start_timestamp
```

### 6. Package init - `src/kit_hub/recipes/__init__.py`

Re-export all public models.

## Tasks

- [ ] Create `src/kit_hub/recipes/` package
- [ ] Implement `recipe_enums.py`
- [ ] Implement `recipe_core.py`
- [ ] Implement `section_idx.py`
- [ ] Implement `tag.py`
- [ ] Implement `recipe_note.py`
- [ ] Write `__init__.py` with re-exports
- [ ] Write tests: `tests/recipes/test_recipe_core.py` - model creation, validation, serialization
- [ ] Write tests: `tests/recipes/test_recipe_note.py` - add_note, to_string formatting
- [ ] Write tests: `tests/recipes/test_section_idx.py` - union type discrimination
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
