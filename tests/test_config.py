import json
from pathlib import Path
from unittest.mock import patch

from app import config
from app.config import load_config, DEFAULTS

def test_load_config_no_file(tmp_path):
    config_dir = tmp_path / ".bolodb"
    config_file = config_dir / "config.json"

    with patch("app.config.CONFIG_DIR", config_dir), patch("app.config.CONFIG_FILE", config_file):
        cfg = load_config()
        assert cfg == dict(DEFAULTS)
        assert config_dir.exists()
        assert not config_file.exists()

def test_load_config_with_valid_file(tmp_path):
    config_dir = tmp_path / ".bolodb"
    config_file = config_dir / "config.json"
    config_dir.mkdir()

    custom_data = {
        "provider": "claude",
        "model": "claude-3-opus",
        "api_keys": {
            "claude": "sk-ant-123",
            "openai": "sk-123"
        }
    }
    config_file.write_text(json.dumps(custom_data))

    with patch("app.config.CONFIG_DIR", config_dir), patch("app.config.CONFIG_FILE", config_file):
        cfg = load_config()
        assert cfg["provider"] == "claude"
        assert cfg["model"] == "claude-3-opus"
        assert cfg["ollama_url"] == DEFAULTS["ollama_url"]
        assert cfg["api_keys"]["claude"] == "sk-ant-123"
        assert cfg["api_keys"]["openai"] == "sk-123"
        assert cfg["api_keys"]["groq"] == DEFAULTS["api_keys"]["groq"]

def test_load_config_invalid_json(tmp_path):
    config_dir = tmp_path / ".bolodb"
    config_file = config_dir / "config.json"
    config_dir.mkdir()

    config_file.write_text("invalid json {")

    with patch("app.config.CONFIG_DIR", config_dir), patch("app.config.CONFIG_FILE", config_file):
        cfg = load_config()
        assert cfg == dict(DEFAULTS)

def test_save_config(tmp_path):
    config_dir = tmp_path / ".bolodb"
    config_file = config_dir / "config.json"

    with patch("app.config.CONFIG_DIR", config_dir), patch("app.config.CONFIG_FILE", config_file):
        from app.config import save_config
        save_config({"test": "data"})

        assert config_dir.exists()
        assert config_file.exists()
        assert json.loads(config_file.read_text()) == {"test": "data"}

def test_public_config():
    from app.config import public_config
    cfg = {
        "provider": "claude",
        "model": "claude-3-5-sonnet",
        "ollama_url": "http://localhost:11434",
        "api_keys": {
            "claude": "sk-ant-123",
            "openai": ""
        },
        "last_db_url": "sqlite:///test.db"
    }

    pub = public_config(cfg)
    assert pub["provider"] == "claude"
    assert pub["model"] == "claude-3-5-sonnet"
    assert pub["api_keys_set"]["claude"] == "set"
    assert pub["api_keys_set"]["openai"] == ""
    assert "sk-ant-123" not in str(pub)
