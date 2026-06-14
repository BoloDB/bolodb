## 2024-06-14 - Memoize tokens collection with immutable sets
**Learning:** When using `functools.lru_cache` to memoize functions that return collections (like `set` or `list`), there is a risk of cache poisoning if callers mutate the returned collection in place (e.g., using `|=`).
**Action:** Always ensure the return type of memoized collection-returning functions is immutable (e.g., `frozenset` instead of `set`, or `tuple` instead of `list`) to prevent unintended state mutations across calls.
