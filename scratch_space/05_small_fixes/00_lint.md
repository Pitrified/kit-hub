# Linting problems recap

## Baseline pyright errors (141 total)

The kit-hub codebase has 141 pre-existing pyright errors, none introduced by the webscraper work. Root causes:

### 1. `StrEnum` not recognized (`reportAttributeAccessIssue`)

Pyright does not resolve `StrEnum` from `enum` on Python 3.14. Affects `RecipeSource`, other enums.

- `recipe_enums.py:13` - `"StrEnum" is unknown import symbol`
- Cascading effect: any `RecipeSource` value is seen as `str` rather than `RecipeSource`, causing type mismatches everywhere a `RecipeSource` is expected (e.g. `Literal['manual']` not assignable to `RecipeSource`).

### 2. `dict`/`list` subscript at module level (`reportIndexIssue`)

Using `dict[K, V]` or `list[T]` as a runtime annotation (not inside a function or `TYPE_CHECKING` block) triggers `reportIndexIssue` on older pyright versions.

- Fix option: `from __future__ import annotations` - but this triggers ruff `TC001`/`TC002` rules requiring all type-only imports to move into `TYPE_CHECKING` blocks, which is a large refactor.
- Current approach: leave as-is, consistent with the rest of the codebase.

### 3. Union syntax `X | Y` (`reportGeneralTypeIssues`)

Pyright reports `Alternative syntax for unions requires Python 3.10 or newer` despite targeting 3.14. Likely a pyright version or config mismatch.

## Ruff

Ruff passes clean. No issues.

## Recommendations

- Upgrade pyright to a version that properly supports Python 3.14 and `StrEnum`.
- Alternatively, pin `pythonVersion = "3.14"` in pyrightconfig.json if not already set.
- The `from __future__ import annotations` + TC rule cascade is a codebase-wide decision, not something to fix per-file.
fix it cleanly
