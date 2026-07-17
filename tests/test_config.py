import json
from contextlib import contextmanager
from unittest.mock import patch

from backend.app.config import (
    default_config,
    load_config,
    save_config,
    public_config,
)


@contextmanager
def _paths(tmp_path, env=None):
    config_dir = tmp_path / ".bolodb"
    with (
        patch("backend.app.config.CONFIG_DIR", config_dir),
        patch("backend.app.config.CONFIG_FILE", config_dir / "config.json"),
        patch("backend.app.config.SECRET_FILE", config_dir / ".secret"),
        patch.dict("os.environ", {"OPENROUTER_API_KEY": "", **(env or {})}),
    ):
        yield config_dir


def test_default_config_no_api_keys():
    cfg = default_config()
    assert "api_keys" not in cfg
    assert "openrouter_key" in cfg
    assert cfg["openrouter_key"] == ""


def test_load_config_no_file(tmp_path):
    with _paths(tmp_path) as config_dir:
        cfg = load_config()
        assert cfg["openrouter_key"] == ""
        assert config_dir.exists()


def test_load_config_with_valid_file(tmp_path):
    with _paths(tmp_path) as config_dir:
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps({"last_db_url": "sqlite:///test.db"})
        )
        cfg = load_config()
        assert cfg["last_db_url"] == "sqlite:///test.db"
        assert cfg["openrouter_key"] == ""


def test_load_config_env_var(tmp_path):
    with _paths(tmp_path, env={"OPENROUTER_API_KEY": "sk-or-test"}):
        cfg = load_config()
        assert cfg["openrouter_key"] == "sk-or-test"


def test_save_config_writes_plain_dict(tmp_path):
    with _paths(tmp_path) as config_dir:
        save_config(
            {"openrouter_key": "sk-or-v1-secret", "last_db_url": "sqlite:///test.db"}
        )
        saved = json.loads((config_dir / "config.json").read_text())
        assert "openrouter_key" not in saved
        assert saved["last_db_url"] == "sqlite:///test.db"


def test_public_config():
    cfg = {
        "openrouter_key": "sk-or-secret",
        "last_db_url": "sqlite:///test.db",
    }
    pub = public_config(cfg)
    assert "openrouter_key" not in pub  # never expose the key
    assert pub["last_db_url"] == "sqlite:///test.db"


def test_legacy_data_is_dropped(tmp_path):
    """Old configs with api_keys, provider, model fields are cleaned up."""
    with _paths(tmp_path) as config_dir:
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "provider": "gemini",
                    "model": "gemini-flash-latest",
                    "api_keys": {"user-1": {"gemini": "AIza-old"}},
                }
            )
        )
        cfg = load_config()
        assert "api_keys" not in cfg
        assert "provider" not in cfg
        assert "model" not in cfg
