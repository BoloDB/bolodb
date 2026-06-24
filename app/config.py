"""Local config + path constants."""
import json
import os
from pathlib import Path

CONFIG_DIR = Path(os.path.expanduser("~")) / ".bolodb"
CONFIG_FILE = CONFIG_DIR / "config.json"
KB_FILE     = CONFIG_DIR / "knowledge.db"

DEFAULTS = {
    "provider": "ollama",
    "model": "",
    "ollama_url": "http://localhost:11434",
    "api_keys": {"claude": "", "openai": "", "groq": ""},
    "last_db_url": "",
}

def ensure_dir(): CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_config():
    ensure_dir()
    if CONFIG_FILE.exists():
        try:
            d = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg = {**DEFAULTS, **d}
            cfg["api_keys"] = {**DEFAULTS["api_keys"], **d.get("api_keys", {})}
            return cfg
        except Exception: pass
    return dict(DEFAULTS)

def save_config(cfg):
    ensure_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

def public_config(cfg):
    return {
        "provider": cfg.get("provider"),
        "model": cfg.get("model", ""),
        "ollama_url": cfg.get("ollama_url"),
        "api_keys_set": {k: ("set" if v else "") for k, v in cfg.get("api_keys", {}).items()},
        "last_db_url": cfg.get("last_db_url", ""),
    }
