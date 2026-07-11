import json
from contextlib import contextmanager
from unittest.mock import patch

from backend.app.config import (
    DEFAULT_MODEL,
    DEFAULTS,
    decrypt_api_key,
    encrypt_api_key,
    load_config,
    save_config,
)


@contextmanager
def _paths(tmp_path, env=None):
    """Point CONFIG_DIR/CONFIG_FILE/SECRET_FILE into tmp_path and pin env."""
    config_dir = tmp_path / ".bolodb"
    with (
        patch("backend.app.config.CONFIG_DIR", config_dir),
        patch("backend.app.config.CONFIG_FILE", config_dir / "config.json"),
        patch("backend.app.config.SECRET_FILE", config_dir / ".secret"),
        patch.dict("os.environ", {"GEMINI_API_KEY": "", **(env or {})}),
    ):
        yield config_dir


def test_load_config_no_file(tmp_path):
    with _paths(tmp_path) as config_dir:
        cfg = load_config()
        assert cfg == dict(DEFAULTS)
        assert config_dir.exists()
        assert not (config_dir / "config.json").exists()


def test_load_config_with_valid_file(tmp_path):
    with _paths(tmp_path) as config_dir:
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "provider": "gemini",
                    "model": "gemini-flash-latest",
                    "api_keys": {"gemini": "AIza-test-123"},  # legacy plaintext
                }
            )
        )
        cfg = load_config()
        assert cfg["provider"] == "gemini"
        assert cfg["model"] == "gemini-flash-latest"
        # plaintext keys from pre-encryption configs are migrated to encrypted
        # form on load, and decrypt back to the original at the point of use
        assert cfg["api_keys"]["gemini"] != "AIza-test-123"
        assert decrypt_api_key(cfg["api_keys"]["gemini"]) == "AIza-test-123"


def test_api_key_is_encrypted_at_rest_and_round_trips(tmp_path):
    with _paths(tmp_path) as config_dir:
        cfg = dict(DEFAULTS)
        # keys enter the config already encrypted (as update_config does)
        cfg["api_keys"] = {"gemini": encrypt_api_key("AIza-super-secret")}
        save_config(cfg)

        raw = (config_dir / "config.json").read_text()
        assert "AIza-super-secret" not in raw  # never clear text on disk
        assert (config_dir / ".secret").exists()

        loaded = load_config()
        assert decrypt_api_key(loaded["api_keys"]["gemini"]) == "AIza-super-secret"


def test_create_provider_decrypts_the_stored_key(tmp_path):
    from backend.app.llm import create_provider

    with _paths(tmp_path):
        cfg = dict(DEFAULTS)
        cfg["api_keys"] = {"gemini": encrypt_api_key("AIza-plain")}
        provider = create_provider(cfg)
        assert provider.api_key == "AIza-plain"


def test_load_config_migrates_old_provider_config(tmp_path):
    """Configs written before the Gemini-only switch are coerced to Gemini."""
    with _paths(tmp_path) as config_dir:
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text(
            json.dumps(
                {
                    "provider": "claude",
                    "model": "claude-3-opus",
                    "ollama_url": "http://localhost:11434",
                    "api_keys": {"claude": "sk-ant-123", "openai": "sk-123"},
                }
            )
        )
        cfg = load_config()
        assert cfg["provider"] == "gemini"
        assert cfg["model"] == DEFAULT_MODEL
        # old vendor keys are dropped, gemini key slot exists
        assert set(cfg["api_keys"]) == {"gemini"}


def test_load_config_env_var_fallback(tmp_path):
    with _paths(tmp_path, env={"GEMINI_API_KEY": "AIza-from-env"}):
        cfg = load_config()
        assert decrypt_api_key(cfg["api_keys"]["gemini"]) == "AIza-from-env"


def test_load_config_saved_key_beats_env_var(tmp_path):
    with _paths(tmp_path, env={"GEMINI_API_KEY": "AIza-from-env"}):
        cfg = dict(DEFAULTS)
        cfg["api_keys"] = {"gemini": encrypt_api_key("AIza-saved")}
        save_config(cfg)
        assert decrypt_api_key(load_config()["api_keys"]["gemini"]) == "AIza-saved"


def test_load_config_invalid_json(tmp_path):
    with _paths(tmp_path) as config_dir:
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text("invalid json {")
        cfg = load_config()
        assert cfg == dict(DEFAULTS)


def test_save_config_without_key_writes_plain_dict(tmp_path):
    with _paths(tmp_path) as config_dir:
        save_config({"test": "data"})
        assert json.loads((config_dir / "config.json").read_text()) == {"test": "data"}


def test_public_config():
    from backend.app.config import public_config

    cfg = {
        "provider": "gemini",
        "model": "gemini-2.5-flash",
        "api_keys": {"gemini": "AIza-secret"},
        "last_db_url": "sqlite:///test.db",
    }

    pub = public_config(cfg)
    assert pub["provider"] == "gemini"
    assert pub["model"] == "gemini-2.5-flash"
    assert pub["api_keys_set"]["gemini"] == "set"
    assert "AIza-secret" not in str(pub)
