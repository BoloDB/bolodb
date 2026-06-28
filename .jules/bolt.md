## 2025-02-27 - Cache Poisoning with mutable returns
**Learning:** When using `@functools.lru_cache` to memoize functions that return collections (like `set` or `list`), modifying the returned collection in the caller can inadvertently mutate the cached value (cache poisoning).
**Action:** Always return an immutable type (e.g., `frozenset` instead of `set`, or `tuple` instead of `list`) when memoizing functions that return collections.
