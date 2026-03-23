# Block 8: Search + discovery

Parent plan: [00-plan.md](00-plan.md)
Depends on: [02-recipe-models.md](02-recipe-models.md), [03-db-layer.md](03-db-layer.md), [04-llm-chains.md](04-llm-chains.md)

## Goal

Implement semantic search using `llm-core` vector store abstractions. Recipes are indexed on save and queryable by natural language. AI tag extraction runs automatically on new recipes.

## Source material

- `llm-core`: `VectorStoreConfig`, `CChroma`, `EntityStore`, `Vectorable` protocol, `EmbeddingsConfig`
- `recipinator`: ChromaDB + Sentence Transformers prototype (notebook only, not exposed via API)
- `recipinator`: `RecipeTagLink` with `confidence` + `origin` columns

## Design

### Indexing

On recipe create/update:
1. Render recipe as a searchable text blob (name + ingredients + steps + tags)
2. Generate embedding via `llm-core` embeddings
3. Upsert into ChromaDB vector store
4. Run `TagExtractor` to assign AI tags (from Block 3)

### Search

1. User enters natural language query ("pasta with tomato sauce")
2. Embed query
3. ChromaDB similarity search -> ranked recipe IDs
4. Fetch recipe details from SQLite
5. Return ranked results

### Vectorable protocol

`RecipeCore` implements `Vectorable`:

```python
class RecipeDocument:
    """Adapter to make recipes compatible with llm-core Vectorable protocol."""

    @staticmethod
    def to_document(recipe_id: str, recipe: RecipeCore) -> Document:
        """Convert recipe to a LangChain Document for vector indexing."""
        text = _render_recipe_text(recipe)
        return Document(
            page_content=text,
            metadata={"entity_type": "recipe", "recipe_id": recipe_id},
        )

    @staticmethod
    def from_document(doc: Document) -> str:
        """Extract recipe_id from a Document."""
        return doc.metadata["recipe_id"]
```

## Deliverables

### 1. Recipe indexer - `src/kit_hub/search/recipe_indexer.py`

```python
class RecipeIndexer:
    """Index recipes into vector store on create/update."""

    def __init__(self, vector_store: VectorStoreConfig, tag_extractor: TagExtractor): ...

    async def index_recipe(self, recipe_id: str, recipe: RecipeCore) -> None:
        """Index a recipe and extract AI tags."""
        # 1. Render recipe as text
        # 2. Upsert into vector store
        # 3. Run TagExtractor
        # 4. Return tags for DB storage

    async def remove_recipe(self, recipe_id: str) -> None:
        """Remove a recipe from the index."""
        ...
```

### 2. Recipe searcher - `src/kit_hub/search/recipe_searcher.py`

```python
class RecipeSearcher:
    """Search recipes by natural language query."""

    def __init__(self, vector_store: VectorStoreConfig, crud: RecipeCRUDService): ...

    async def search(self, query: str, limit: int = 10) -> list[RecipeRow]:
        """Search recipes by natural language. Returns ranked results."""
        # 1. Embed query
        # 2. Similarity search in vector store
        # 3. Extract recipe_ids from results
        # 4. Fetch full recipes from DB
        # 5. Return in ranked order
        ...
```

### 3. Search config

```python
class SearchConfig(BaseModelKwargs):
    embeddings_config: EmbeddingsConfig  # model + provider
    chroma_persist_dir: Path             # where to store the ChromaDB data
    collection_name: str = "recipes"
```

### 4. API + bot integration

- API: `GET /api/recipes/search?q=<query>&limit=10` -> `RecipeListResponse`
- Bot: `/search <query>` -> list matching recipes with inline keyboard

### 5. Auto-tagging hook

Wire `TagExtractor` into the recipe create flow:
- After `RecipeCRUDService.create_recipe()`, run `RecipeIndexer.index_recipe()`
- Tags from the extractor are persisted via `RecipeCRUDService.add_tags()`
- This runs as a background task (not blocking the create response)

## Tasks

- [ ] Create `src/kit_hub/search/` package
- [ ] Implement `recipe_indexer.py`
- [ ] Implement `recipe_searcher.py`
- [ ] Create `SearchConfig` and `SearchParams`
- [ ] Implement `RecipeDocument` adapter for `Vectorable` protocol
- [ ] Wire auto-tagging into recipe create flow
- [ ] Add `/api/recipes/search` endpoint
- [ ] Add `/search` bot command
- [ ] Write tests with mocked vector store
- [ ] Write tests for tag extraction integration
- [ ] Verify: `uv run pytest && uv run ruff check . && uv run pyright`
