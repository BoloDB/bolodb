## 2025-02-27 - Cache Poisoning with mutable returns
**Learning:** When using `@functools.lru_cache` to memoize functions that return collections (like `set` or `list`), modifying the returned collection in the caller can inadvertently mutate the cached value (cache poisoning).
**Action:** Always return an immutable type (e.g., `frozenset` instead of `set`, or `tuple` instead of `list`) when memoizing functions that return collections.
## 2024-05-24 - Async API endpoints blocked by run_in_threadpool
**Learning:** Awaiting `run_in_threadpool` for non-essential I/O (like saving query history to MongoDB) still blocks the API response cycle, increasing latency on endpoints like `/api/query` that should return ASAP.
**Action:** Use `FastAPI.BackgroundTasks` (`background_tasks.add_task(...)`) instead of awaiting `fastapi.concurrency.run_in_threadpool` for non-essential, fire-and-forget I/O operations in FastAPI endpoints. Ensure exception handling (`try...except`) is implemented within the offloaded task function itself.
