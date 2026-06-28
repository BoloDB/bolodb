import re
import functools


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


@functools.lru_cache(maxsize=2048)
def _tokens(text: str | None) -> frozenset[str]:
    """
    Extracts alphanumeric tokens from a string.

    Caching this regex-heavy function speeds up schema linking and similarity searches significantly.
    Returning an immutable frozenset prevents callers from mutating the cached collection.
    """
    if not text:
        return frozenset()

    return frozenset(t for t in _TOKEN_PATTERN.findall(text.lower()) if len(t) > 1)
