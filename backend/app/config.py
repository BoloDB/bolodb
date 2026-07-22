"""Local config + path constants.

BoloDB uses OpenRouter (deepseek-v4-flash) for every AI operation. The API key
is read from the OPENROUTER_API_KEY environment variable at startup and
shared across all users — no per-user key storage or encryption is needed.

Stored at ~/.bolodb/config.json. Only non-sensitive settings (last connected
database URL) are persisted; the API key is never written to disk.
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
_DB_URL_KEY_FILE = CONFIG_DIR / "db_url.key"

ACTIVITY_LOG_RETENTION_DAYS = int(os.environ.get("ACTIVITY_LOG_RETENTION_DAYS", "30"))

DEFAULTS = {
    "openrouter_key": "",
    "last_db_url": "",
}


def default_config():
    return dict(DEFAULTS)


def ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CONFIG_DIR, 0o700)
    except OSError:
        pass


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

    # Strip legacy fields that no longer apply
    changed = False
    for key in ("provider", "model", "api_keys"):
        if key in d:
            d.pop(key)
            changed = True

    cfg = {**default_config(), **d}
    # API key is always read fresh from env, never from disk
    cfg["openrouter_key"] = os.environ.get("OPENROUTER_API_KEY", "")

    # Persist sanitized config if legacy fields were removed
    if changed:
        save_config(cfg)

    return cfg


def save_config(cfg):
    ensure_dir()
    # Never persist the API key
    to_save = {k: v for k, v in cfg.items() if k != "openrouter_key"}
    CONFIG_FILE.write_text(json.dumps(to_save, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def _db_url_fernet():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    import base64
    import hashlib

    if _DB_URL_KEY_FILE.exists():
        secret = _DB_URL_KEY_FILE.read_text().strip()
    else:
        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        _DB_URL_KEY_FILE.write_text(secret)
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def encrypt_db_url(url):
    if not url:
        return url
    return _db_url_fernet().encrypt(url.encode()).decode()


def decrypt_db_url(value):
    if not value:
        return value
    try:
        return _db_url_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return value


def public_config(cfg):
    """Config as exposed to the frontend — never includes the API key."""
    return {
        "last_db_url": decrypt_db_url(cfg.get("last_db_url", "")),
    }
