import re


def _tokens(text):
    return set(t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 1)
