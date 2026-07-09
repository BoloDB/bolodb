## 2025-02-27 - Cache Poisoning with mutable returns
**Learning:** When using `@functools.lru_cache` to memoize functions that return collections (like `set` or `list`), modifying the returned collection in the caller can inadvertently mutate the cached value (cache poisoning).
**Action:** Always return an immutable type (e.g., `frozenset` instead of `set`, or `tuple` instead of `list`) when memoizing functions that return collections.
## 2024-05-24 - Async API Event Loop Blocking via run_in_threadpool
**Learning:** In FastAPI async endpoints, awaiting `run_in_threadpool` for non-essential, fire-and-forget I/O operations (like logging to MongoDB) still blocks the API response cycle because the endpoint waits for the threadpool task to finish before returning the response. This needlessly increases endpoint latency for operations the client doesn't need to wait for.
**Action:** Use `FastAPI.BackgroundTasks` (`background_tasks.add_task(...)`) instead of `run_in_threadpool` for fire-and-forget I/O operations in async endpoints to offload the work without blocking the response cycle. Ensure internal exception handling is placed within the offloaded task function itself.
