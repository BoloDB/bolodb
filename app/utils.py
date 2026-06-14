import re
from functools import lru_cache

@lru_cache(maxsize=1024)
def _tokens(text):
    # Performance optimization: caching tokens prevents redundant regex execution.
    # Return frozenset to prevent cache poisoning via unintended mutations.
    return frozenset(t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 1)
