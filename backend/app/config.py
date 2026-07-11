"""Local config + path constants."""

import base64
import hashlib
import json
import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

CONFIG_DIR = Path(os.path.expanduser("~")) / ".bolodb"
CONFIG_FILE = CONFIG_DIR / "config.json"
KB_FILE = CONFIG_DIR / "knowledge.db"
_DB_URL_KEY_FILE = CONFIG_DIR / "db_url.key"

DEFAULTS = {
    "provider": "ollama",
    "model": "",
    "ollama_url": "http://localhost:11434",
    "api_keys": {"claude": "", "openai": "", "groq": ""},
    "last_db_url": "",
}


def ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


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
    # cfg["api_keys"] = {**DEFAULTS["api_keys"], **d.get("api_keys", {})}
    raw_keys = d.get("api_keys", {})
    if not isinstance(raw_keys, dict):
        raw_keys = {}
    cfg["api_keys"] = {**DEFAULTS["api_keys"], **raw_keys}

    # Auto-route localhost to host.docker.internal if running in Docker
    if os.environ.get("RUNNING_IN_DOCKER") and "localhost" in cfg.get("ollama_url", ""):
        cfg["ollama_url"] = cfg["ollama_url"].replace(
            "localhost", "host.docker.internal"
        )

    return cfg


def save_config(cfg):
    ensure_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


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


def public_config(cfg):
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model", ""),
        "ollama_url": cfg.get("ollama_url"),
        "api_keys_set": {
            k: ("set" if v else "") for k, v in cfg.get("api_keys", {}).items()
        },
        "last_db_url": decrypt_db_url(cfg.get("last_db_url", "")),
    }
