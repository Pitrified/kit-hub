# LLM Chains

The `kit_hub.llm` package provides four `StructuredLLMChain`-backed wrappers
that convert free-form text into structured recipe data. Each chain loads a
versioned Jinja2 prompt from `prompts/<chain_name>/v1.jinja` and produces a
typed Pydantic output.

## Configuration

### LlmConfig

Defined in [`LlmConfig`](../../reference/kit_hub/config/llm_config/), the
config carries:

- `chat_config` - Any `ChatConfig` subclass (e.g. `ChatOpenAIConfig`).
- `prompts_fol` - Root folder containing versioned prompt subdirectories.

### LlmParams

[`LlmParams`](../../reference/kit_hub/params/llm_params/) follows the
Config / Params pattern. Both `dev` and `prod` stages currently use
`gpt-4o-mini` at `temperature=0.2`. The OpenAI API key is read automatically
by `ChatOpenAIConfig` from the `OPENAI_API_KEY` environment variable.

`LlmParams` is wired into [`KitHubParams`](../../reference/kit_hub/params/kit_hub_params/)
as `params.llm`. Use `params.llm.to_config()` to obtain an `LlmConfig` ready
for chain construction.

Prompts are stored at `prompts/` in the repo root and accessed via
`KitHubPaths.prompts_fol`.

## Chains

All chains follow the same pattern: accept an `LlmConfig` in `__init__`,
then expose `invoke()` and `ainvoke()` for sync and async use.

### RecipeCoreTranscriber

[`RecipeCoreTranscriber`](../../reference/kit_hub/llm/transcriber/) converts
free-form recipe text - an Instagram caption, a voice transcript, or manually
pasted content - into a structured `RecipeCore`. The recipe language is
preserved unchanged.

```python
from kit_hub.llm.transcriber import RecipeCoreTranscriber
from kit_hub.params.kit_hub_params import get_kit_hub_params

params = get_kit_hub_params()
transcriber = RecipeCoreTranscriber(params.llm.to_config())
recipe = transcriber.invoke("Boil pasta for 10 minutes. Add sauce. Serve.")
```

Prompt: `prompts/transcriber/v1.jinja`

### RecipeCoreEditor

[`RecipeCoreEditor`](../../reference/kit_hub/llm/editor/) applies a
natural-language correction to a specific step in an existing recipe. All
other preparations and steps are returned unchanged.

```python
from kit_hub.llm.editor import RecipeCoreEditor

editor = RecipeCoreEditor(params.llm.to_config())
updated = editor.invoke(
    old_recipe=recipe,
    old_step="Add 500g of salt.",
    new_step="Use 5g of salt, not 500g.",
)
```

Prompt: `prompts/editor/v1.jinja`

### SectionIdxFinder

[`SectionIdxFinder`](../../reference/kit_hub/llm/section_finder/) maps a
natural-language location query to a zero-based `(preparation_idx, step_idx)`
or `(preparation_idx, ingredient_idx)` pointer. Returns a `Section` containing
a `SectionStep` or `SectionIngredient` discriminated union.

```python
from kit_hub.llm.section_finder import SectionIdxFinder
from kit_hub.recipes.section_idx import SectionStep

finder = SectionIdxFinder(params.llm.to_config())
section = finder.invoke("step 2 of the sauce preparation")
if isinstance(section.section, SectionStep):
    prep_idx = section.section.preparation_idx
    step_idx = section.section.step_idx
```

Prompt: `prompts/section_finder/v1.jinja`

### TagExtractor

[`TagExtractor`](../../reference/kit_hub/llm/tag_extractor/) extracts
descriptive tags from a recipe with confidence scores. All returned tags
have `origin="ai"`. Tags describe main ingredients, cooking methods, cuisine
style, dietary properties, and difficulty level.

```python
from kit_hub.llm.tag_extractor import TagExtractor

extractor = TagExtractor(params.llm.to_config())
tags = extractor.invoke(recipe)
# tags -> [RecipeTagAssignment(tag_name="pasta", confidence=0.95, origin="ai"), ...]
```

Prompt: `prompts/tag_extractor/v1.jinja`

## Prompt versioning

Prompts live in subdirectories under `prompts/`:

```
prompts/
  transcriber/v1.jinja
  editor/v1.jinja
  section_finder/v1.jinja
  tag_extractor/v1.jinja
```

`PromptLoader` from `llm-core` resolves `version="auto"` by scanning for
the highest `vN.jinja` file in the subdirectory. To introduce a new prompt
version, create `v2.jinja` in the relevant subdirectory - the loader picks it
up automatically.

## Testing

All chains are tested with `FakeChatModelConfig` from `llm-core`'s testing
utilities. The fake model returns pre-loaded JSON strings that exercise the
structured output parsing without any API calls. See `tests/llm/` for
examples.
