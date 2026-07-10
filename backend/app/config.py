"""Local config + path constants.

BoloDB uses Google Gemini for every AI operation, so the config is small:
which Gemini model to use and the API key for it. The key can also be supplied
via the ``GEMINI_API_KEY`` environment variable (handy for Docker deployments)
— an explicit key saved from Settings always wins over the environment.

Stored at ``~/.bolodb/config.json``. The API key is never written to disk in
clear text: it is encrypted with a per-install secret (``~/.bolodb/.secret``,
generated once, file mode 0600) before saving and decrypted on load. Older
config files — plaintext keys and pre-Gemini providers alike — are migrated
transparently on load.
"""

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

DEFAULT_MODEL = "gemini-2.5-flash"

# Models the Settings API accepts. Ordered cheapest → most capable.
ALLOWED_MODELS = (
    "gemini-2.5-flash-lite",  # cheapest; fine for small, simple databases
    "gemini-2.5-flash",  # default; best cost/accuracy balance
    "gemini-2.5-pro",  # most accurate; for large schemas / hard questions
)

DEFAULTS = {
    "provider": "gemini",
    "model": DEFAULT_MODEL,
    "api_keys": {"gemini": ""},
    "last_db_url": "",
}


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


def _encrypt(value):
    if not value:
        return ""
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(stored):
    """Decrypt a stored key. Legacy plaintext values (from configs written
    before encryption-at-rest) are returned as-is and get encrypted the next
    time the config is saved."""
    if not stored:
        return ""
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError):
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

    cfg = {**DEFAULTS, **d}

    raw_keys = d.get("api_keys", {})
    if not isinstance(raw_keys, dict):
        raw_keys = {}
    cfg["api_keys"] = {"gemini": _decrypt(raw_keys.get("gemini", ""))}

    # Migration: configs written before the Gemini-only switch may name another
    # provider or a non-Gemini model. Coerce both so the app always starts in a
    # valid state instead of erroring on an unknown provider.
    if cfg.get("provider") != "gemini":
        cfg["provider"] = "gemini"
    if not str(cfg.get("model", "")).startswith("gemini-"):
        cfg["model"] = DEFAULT_MODEL

    # Env fallback: lets deployments inject the key without touching the file.
    if not cfg["api_keys"]["gemini"] and os.environ.get("GEMINI_API_KEY"):
        cfg["api_keys"]["gemini"] = os.environ["GEMINI_API_KEY"]

    return cfg


def save_config(cfg):
    """Persist config. The API key is encrypted before it touches disk; the
    in-memory ``cfg`` the app keeps using is not modified."""
    ensure_dir()
    to_write = json.loads(json.dumps(cfg))  # deep copy; never mutate the caller's cfg
    keys = to_write.get("api_keys")
    if isinstance(keys, dict) and keys.get("gemini"):
        keys["gemini"] = _encrypt(keys["gemini"])
    CONFIG_FILE.write_text(json.dumps(to_write, indent=2), encoding="utf-8")
    _restrict(CONFIG_FILE)


def public_config(cfg):
    """Config as exposed to the frontend — never includes the actual API key,
    only whether one is set."""
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model", ""),
        "api_keys_set": {
            k: ("set" if v else "") for k, v in cfg.get("api_keys", {}).items()
        },
        "last_db_url": cfg.get("last_db_url", ""),
    }
