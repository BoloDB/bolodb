import re
import functools

# Pre-compile regex for performance
_TOKEN_RE = re.compile(r"[a-z0-9]+")

@functools.lru_cache(maxsize=2048)
def _tokens(text):
    # Returns frozenset instead of set to prevent callers from mutating the cache
    return frozenset(t for t in _TOKEN_RE.findall((text or "").lower()) if len(t) > 1)
