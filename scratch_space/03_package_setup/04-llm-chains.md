# Block 3: LLM chains

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md)

## Goal

Reimplement the LLM pipelines using `llm-core` `StructuredLLMChain[InputT, OutputT]` with versioned Jinja prompts. Each chain is a thin wrapper around a `StructuredLLMChain` instance.

## Source material

- `recipamatic`: `RecipeCoreTranscriber`, `RecipeCoreEditor`, `SectionIdxFinder` (all working, direct LangChain usage)
- `llm-core`: `StructuredLLMChain` generic dataclass, `PromptLoader`, `ChatConfig` hierarchy

## Pattern

Every chain follows this structure:

```python
from llm_core.chains.structured_chain import StructuredLLMChain
from llm_core.chat.config.openai import ChatOpenAIConfig

chain = StructuredLLMChain(
    chat_config=ChatOpenAIConfig(model="gpt-4o-mini"),
    prompt_str=PromptLoader(prompts_fol / "transcriber", version="auto").load(),
    input_model=TranscriberInput,
    output_model=RecipeCore,
)
result: RecipeCore = chain.invoke(TranscriberInput(recipe_text="..."))
```

Input models extend `BaseModelKwargs` and field names must match `{{ var }}` placeholders in the Jinja template. Output models are plain `BaseModel`.

## Deliverables

### 1. LLM config - `src/kit_hub/config/llm_config.py`

```python
class LlmConfig(BaseModelKwargs):
    chat_config: ChatOpenAIConfig  # or ChatConfig if we want provider flexibility
    temperature: float = 0.2
```

### 2. LLM params - `src/kit_hub/params/llm_params.py`

```python
class LlmParams:
    def __init__(self, env_type: EnvType | None = None): ...
    def to_config(self) -> LlmConfig: ...
    # dev: gpt-4o-mini, temp=0.2
    # prod: gpt-4o-mini, temp=0.2 (same for now)
```

### 3. RecipeCoreTranscriber - `src/kit_hub/llm/transcriber.py`

Input: free text (IG caption, voice transcript, manual paste)
Output: structured `RecipeCore`

```python
class TranscriberInput(BaseModelKwargs):
    recipe_text: str

class RecipeCoreTranscriber:
    def __init__(self, llm_config: LlmConfig): ...
    def invoke(self, recipe_text: str) -> RecipeCore: ...
    async def ainvoke(self, recipe_text: str) -> RecipeCore: ...
```

Prompt (`src/kit_hub/llm/prompts/transcriber/v1.jinja`):
```
You have a text recipe.
You are an expert cook, but you are not pretentious.

Your task is to convert the text recipe into a list of ingredients and steps.
Follow the specified format.
Do not change the ingredients, quantities, or steps from the provided recipe.
Do not change the language of the recipe.

If the recipe is presented in several steps, you can combine the relevant ones
into a single preparation with a descriptive name.

The recipe is: {{ recipe_text }}
```

### 4. RecipeCoreEditor - `src/kit_hub/llm/editor.py`

Input: old recipe JSON + old step text + correction instructions
Output: corrected `RecipeCore`

```python
class EditorInput(BaseModelKwargs):
    old_recipe: str    # RecipeCore.model_dump_json()
    old_step: str      # the step text to correct
    new_step: str      # correction instructions

class RecipeCoreEditor:
    def __init__(self, llm_config: LlmConfig): ...
    def invoke(self, old_recipe: RecipeCore, old_step: str, new_step: str) -> RecipeCore: ...
    async def ainvoke(self, old_recipe: RecipeCore, old_step: str, new_step: str) -> RecipeCore: ...
```

Prompt (`src/kit_hub/llm/prompts/editor/v1.jinja`):
```
You have a recipe.
You are an expert cook, but you are not pretentious.

The recipe is: {{ old_recipe }}

This step is wrong: {{ old_step }}

Please correct it keeping in mind that: {{ new_step }}

Do not change the other steps.
Do not remove or edit the other preparations, return them unchanged.
```

### 5. SectionIdxFinder - `src/kit_hub/llm/section_finder.py`

Input: natural language location query (e.g. "step 2 of the sauce preparation")
Output: `Section` with `SectionGen` discriminated union

```python
class SectionFinderInput(BaseModelKwargs):
    user_instruction: str

class SectionIdxFinder:
    def __init__(self, llm_config: LlmConfig): ...
    def invoke(self, user_instruction: str) -> Section: ...
    async def ainvoke(self, user_instruction: str) -> Section: ...
```

Prompt (`src/kit_hub/llm/prompts/section_finder/v1.jinja`):
```
The user is editing a recipe.
The user instruction identifies a section of the recipe.

User instruction: {{ user_instruction }}

Extract the information required to identify the section:
* Preparation index
* Ingredient or step index
```

### 6. TagExtractor - `src/kit_hub/llm/tag_extractor.py` (new)

Input: recipe name + full recipe text
Output: list of tags with confidence scores

```python
class TagExtractorInput(BaseModelKwargs):
    recipe_name: str
    recipe_text: str  # full recipe rendered as text

class TagExtractorOutput(BaseModel):
    tags: list[RecipeTagAssignment]

class TagExtractor:
    def __init__(self, llm_config: LlmConfig): ...
    def invoke(self, recipe: RecipeCore) -> list[RecipeTagAssignment]: ...
    async def ainvoke(self, recipe: RecipeCore) -> list[RecipeTagAssignment]: ...
```

Prompt (`src/kit_hub/llm/prompts/tag_extractor/v1.jinja`):
```
You are a cooking expert. Given a recipe, extract relevant tags.

Tags should describe:
- Main ingredients (e.g. "chicken", "pasta", "tomato")
- Cooking method (e.g. "baked", "fried", "grilled", "slow-cooked")
- Cuisine style (e.g. "italian", "japanese", "mexican")
- Dietary properties (e.g. "vegetarian", "gluten-free", "vegan")
- Difficulty level (e.g. "quick", "beginner", "advanced")

For each tag, provide a confidence score between 0.0 and 1.0.
Set origin to "ai" for all tags.

Recipe name: {{ recipe_name }}
Recipe: {{ recipe_text }}
```

## Tasks

- [ ] Create `src/kit_hub/config/llm_config.py`
- [ ] Create `src/kit_hub/params/llm_params.py`
- [ ] Wire `LlmParams` into `KitHubParams`
- [ ] Create `src/kit_hub/llm/` package
- [ ] Create `src/kit_hub/llm/prompts/` directory with all `v1.jinja` files
- [ ] Implement `transcriber.py`
- [ ] Implement `editor.py`
- [ ] Implement `section_finder.py`
- [ ] Implement `tag_extractor.py`
- [ ] Write tests with mocked LLM responses for each chain
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
