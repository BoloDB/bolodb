## 2024-06-22 - Prevent unnecessary re-renders in standalone React frontend by memoizing inline array transformations
**Learning:** In the standalone single-file frontend (`static/index.html`), passing inline array transformations directly as props (e.g., `rows={window.rowsToArrays(...)}`) to components wrapped in `React.memo` (like `ResultTable`) defeats memoization because the array reference changes on every render.
**Action:** Always wrap expensive or inline data transformations passed to memoized components in a `React.useMemo` hook to ensure referential stability and prevent useless re-renders of child components.

## 2025-02-27 - Cache Poisoning with mutable returns
**Learning:** When using `@functools.lru_cache` to memoize functions that return collections (like `set` or `list`), modifying the returned collection in the caller can inadvertently mutate the cached value (cache poisoning).
**Action:** Always return an immutable type (e.g., `frozenset` instead of `set`, or `tuple` instead of `list`) when memoizing functions that return collections.
