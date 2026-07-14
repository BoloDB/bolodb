"""Local config + path constants.

BoloDB uses Google Gemini for every AI operation, so the config is small:
which Gemini model to use, and each logged-in user's own API key. Keys are
scoped per user_id (:func:`get_api_key`/:func:`set_api_key`) — one user's
saved key is never handed to another user's requests. A key can also be
supplied via the ``GEMINI_API_KEY`` environment variable (handy for Docker
deployments); it's an install-wide fallback used only for users who haven't
saved a personal key, and an explicit key saved from Settings always wins
over it for that user.

Stored at ``~/.bolodb/config.json``. The API key is never held or written in
clear text by the config layer: it is encrypted with a per-install secret
(``~/.bolodb/.secret``, generated once, file mode 0600) the moment it enters
the config — from Settings (:func:`set_api_key`, called from
``controllers/system.py``) — and stays encrypted inside the in-memory config
dict. It is decrypted only at the point of use, when the Gemini provider is
built for a specific user (``create_provider`` in ``backend/app/llm.py``
calls :func:`get_api_key`). Older config files — plaintext keys, pre-Gemini
providers, and the pre-multi-user single shared key — are migrated
transparently on load; a shared legacy key is dropped rather than handed to
any one user (see :func:`load_config`).
"""

import base64
import hashlib
import json
import logging
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

log = logging.getLogger(__name__)


CONFIG_DIR = Path(os.path.expanduser("~")) / ".bolodb"
CONFIG_FILE = CONFIG_DIR / "config.json"
SECRET_FILE = CONFIG_DIR / ".secret"
KB_FILE = CONFIG_DIR / "knowledge.db"
_DB_URL_KEY_FILE = CONFIG_DIR / "db_url.key"

DEFAULT_MODEL = "gemini-flash-latest"

# Models the Settings API accepts. Ordered cheapest → most capable.
ALLOWED_MODELS = (
    "gemini-3.1-flash-lite",  # cheapest; fine for small, simple databases
    "gemini-flash-latest",  # default; best cost/accuracy balance
    "gemma-4-26b-a4b-it",  # most accurate; for large schemas / hard questions
)

DEFAULTS = {
    "provider": "gemini",
    "model": DEFAULT_MODEL,
    # Keyed by user_id, then provider name: {"<user_id>": {"gemini": "<encrypted>"}}.
    # Each logged-in user's key is only ever used to build *their* requests
    # (see ProviderManager in backend/app/llm.py) — never shared across users.
    "api_keys": {},
    "last_db_url": "",
}


def default_config():
    """A fresh default config dict. Always use this (not ``dict(DEFAULTS)`` /
    ``{**DEFAULTS, ...}``) when a caller might mutate ``api_keys`` in place —
    ``DEFAULTS["api_keys"]`` is one shared dict, so a shallow copy would let
    ``set_api_key``/``clear_api_key`` write into it and leak across every
    config built from ``DEFAULTS`` afterward."""
    return {**DEFAULTS, "api_keys": {}}


def _restrict(path):
    """Best-effort owner-only file permissions (no-op where unsupported)."""
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass


def _fernet():
    """Fernet cipher keyed by a per-install secret, created on first use."""
    ensure_dir()
    if SECRET_FILE.exists():
        key = SECRET_FILE.read_bytes().strip()
    else:
        key = Fernet.generate_key()
        SECRET_FILE.write_bytes(key)
        _restrict(SECRET_FILE)
    return Fernet(key)


# Every Fernet token starts with this prefix (base64 of the 0x80 version byte).
# Used to tell encrypted values apart from legacy plaintext keys.
_TOKEN_PREFIX = "gAAAA"


def encrypt_api_key(plain):
    """Encrypt an API key for storage. Call this the moment a key enters the
    config (Settings save, env var) — the config dict only ever holds the
    encrypted form. Empty in, empty out."""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_api_key(stored):
    """Reverse of :func:`encrypt_api_key`, called only at the point of use
    (building the Gemini provider). Legacy plaintext values pass through
    unchanged, so pre-encryption configs keep working."""
    if not stored:
        return ""
    if not stored.startswith(_TOKEN_PREFIX):
        return stored  # legacy plaintext key
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return stored


def load_config():
    ensure_dir()
    d = {}
    if CONFIG_FILE.exists():
        try:
            d = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    if not isinstance(d, dict):
        d = {}

    cfg = {**default_config(), **d}

    raw_keys = d.get("api_keys", {})
    if not isinstance(raw_keys, dict):
        raw_keys = {}
    per_user = {}
    for uid, keys in raw_keys.items():
        if not isinstance(keys, dict):
            # Pre-multi-user configs stored a single key shared by every
            # logged-in user (e.g. top-level "gemini": "..."). That's the exact
            # bug this migration closes, so it's deliberately dropped, not
            # carried forward to any user: each account must (re-)enter its own
            # key via Settings. The env var fallback below is unaffected — it's
            # an explicit install-wide default, not a leaked per-user secret.
            continue
        stored_key = keys.get("gemini", "")
        if stored_key and not stored_key.startswith(_TOKEN_PREFIX):
            # Migrate legacy plaintext keys to encrypted form immediately.
            stored_key = encrypt_api_key(stored_key)
        per_user[uid] = {"gemini": stored_key}
    cfg["api_keys"] = per_user

    # Migration: configs written before the Gemini-only switch may name another
    # provider or a non-Gemini model. Coerce both so the app always starts in a
    # valid state instead of erroring on an unknown provider.
    if cfg.get("provider") != "gemini":
        cfg["provider"] = "gemini"
    if cfg.get("model") not in ALLOWED_MODELS:
        cfg["model"] = DEFAULT_MODEL

    return cfg


def get_api_key(cfg, user_id, provider="gemini"):
    """Decrypted API key for one user. Falls back to ``GEMINI_API_KEY`` (an
    explicit, install-wide default) only when that user has no key of their
    own — never to another user's stored key."""
    stored = cfg.get("api_keys", {}).get(user_id, {}).get(provider, "")
    if not stored and provider == "gemini" and os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    return decrypt_api_key(stored)


def set_api_key(cfg, user_id, plain, provider="gemini"):
    """Store ``plain`` encrypted, scoped to ``user_id`` only."""
    cfg.setdefault("api_keys", {}).setdefault(user_id, {})[provider] = encrypt_api_key(
        plain
    )


def clear_api_key(cfg, user_id, provider="gemini"):
    cfg.setdefault("api_keys", {}).setdefault(user_id, {})[provider] = ""


def has_api_key(cfg, user_id, provider="gemini"):
    return bool(get_api_key(cfg, user_id, provider))


def save_config(cfg):
    """Persist config. ``cfg`` only ever carries the API key in encrypted form
    (see :func:`encrypt_api_key`), so nothing sensitive is written in clear
    text."""
    ensure_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    _restrict(CONFIG_FILE)


def _db_url_fernet():
    """Return a Fernet cipher for encrypting/decrypting stored database URLs.

    Uses a separate key file (~/.bolodb/db_url.key) to avoid reusing the
    JWT secret or the recent-connections key.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if _DB_URL_KEY_FILE.exists():
        secret = _DB_URL_KEY_FILE.read_text().strip()
    else:
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        _DB_URL_KEY_FILE.write_text(secret)
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_db_url(url):
    """Encrypt a database URL for safe storage on disk."""
    if not url:
        return url
    return _db_url_fernet().encrypt(url.encode()).decode()


def decrypt_db_url(value):
    """Decrypt a stored database URL. Handles legacy plaintext gracefully."""
    if not value:
        return value
    try:
        return _db_url_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        # Legacy plaintext URL — return as-is.
        return value


def public_config(cfg, user_id):
    """Config as exposed to the frontend — never includes the actual API key,
    only whether *this user* has one set."""
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model", ""),
        "api_keys_set": {
            "gemini": "set" if has_api_key(cfg, user_id, "gemini") else "",
        },
        "last_db_url": decrypt_db_url(cfg.get("last_db_url", "")),
    }
