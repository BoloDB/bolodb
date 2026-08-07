"""Config is built from the environment and held in memory — no files.

These tests pin that behaviour: the OpenRouter key comes from the environment
and is never exposed to the frontend, and nothing is read from or written to
disk.
"""

from contextlib import contextmanager
from unittest.mock import patch

from backend.app.config import (
    default_config,
    load_config,
    public_config,
)


@contextmanager
def _env(env=None):
    with patch.dict("os.environ", {"OPENROUTER_API_KEY": "", **(env or {})}):
        yield


def test_default_config_no_api_keys():
    cfg = default_config()
    assert "api_keys" not in cfg
    assert cfg["openrouter_key"] == ""


def test_load_config_reads_key_from_env():
    with _env({"OPENROUTER_API_KEY": "sk-or-test"}):
        cfg = load_config()
        assert cfg["openrouter_key"] == "sk-or-test"


def test_load_config_defaults_when_env_unset():
    with _env():
        cfg = load_config()
        assert cfg["openrouter_key"] == ""


def test_load_config_writes_no_files(tmp_path, monkeypatch):
    """The whole point of the change: loading config touches no disk."""
    monkeypatch.chdir(tmp_path)
    with _env():
        load_config()
    assert list(tmp_path.iterdir()) == []


def test_public_config_never_exposes_the_key():
    """The key must never reach the frontend, whatever else the config holds."""
    pub = public_config({"openrouter_key": "sk-or-secret"})
    assert "openrouter_key" not in pub
    assert pub == {}
