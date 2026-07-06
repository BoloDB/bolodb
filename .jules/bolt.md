## 2025-02-27 - Cache Poisoning with mutable returns
**Learning:** When using `@functools.lru_cache` to memoize functions that return collections (like `set` or `list`), modifying the returned collection in the caller can inadvertently mutate the cached value (cache poisoning).
**Action:** Always return an immutable type (e.g., `frozenset` instead of `set`, or `tuple` instead of `list`) when memoizing functions that return collections.
## 2025-02-27 - BackgroundTasks vs run_in_threadpool
**Learning:** When executing non-essential, fire-and-forget I/O operations (like logging query history to MongoDB) within FastAPI endpoints, awaiting `fastapi.concurrency.run_in_threadpool` still blocks the API response cycle because the endpoint waits for the threadpool task to finish.
**Action:** Use FastAPI's `BackgroundTasks` (`background_tasks.add_task(...)`) instead for true fire-and-forget execution, allowing the endpoint to return immediately and reducing overall API latency. Ensure exceptions are handled within the background task itself.
