# OpenRouter Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Google Gemini with OpenRouter as the sole AI provider, hardcoded to `deepseek-v4-flash`, with API key read from `OPENROUTER_API_KEY` env var shared across all users.

**Architecture:** Single `OpenRouterProvider` class replaces `GeminiProvider`. Config stripped of per-user key storage. Frontend removes model selector and API key UI. OpenAI SDK used for clean OpenRouter integration.

**Tech Stack:** Python `openai` SDK (added), FastAPI, SvelteKit, httpx (removed from provider layer)

## Global Constraints

- Model hardcoded to `deepseek-v4-flash` — no model selection in UI, no model config field
- API key read from `OPENROUTER_API_KEY` env var — no per-user key storage or encryption
- No user-facing API key input or model selection in Settings
- All users share the same OpenRouter key
- Fernet encryption kept only for DB URLs (`encrypt_db_url`/`decrypt_db_url`)

---

### Task 1: Add openai dependency + OpenRouterProvider

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/llm.py` (replace entire file)
- Test: `tests/test_openrouter.py` (new file)

**Interfaces:**
- Consumes: `LLMProvider` ABC (unchanged interface), config dict with `cfg["openrouter_key"]`
- Produces: `OpenRouterProvider(api_key: str, model: str = "deepseek-v4-flash")` with `complete()` and `health_check()` methods

- [ ] **Step 1: Add `openai` to requirements.txt**

```python
# after httpx line, add:
openai>=1.0.0
```

- [ ] **Step 2: Create test file `tests/test_openrouter.py`**

```python
"""Tests for the OpenRouter provider (backend/app/llm.py)."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.llm import (
    OpenRouterProvider,
    LLMError,
    ProviderManager,
    create_provider,
    SQL_SCHEMA,
)


def _complete(provider, **kwargs):
    return asyncio.run(provider.complete("system prompt", "user prompt", **kwargs))


def _health(provider):
    return asyncio.run(provider.health_check())


# --- request shape ----------------------------------------------------------


@patch("backend.app.llm.openai.OpenAI")
def test_complete_sends_correct_messages(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = type(
        "obj", (),
        {"choices": [type("obj", (),
                         {"message": type("obj", (),
                                          {"content": "Hello"})()})()],
         "usage": None}
    )()

    p = OpenRouterProvider(api_key="sk-test")
    out = _complete(p)
    assert out == "Hello"
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "deepseek-v4-flash"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == "system prompt"
    assert kwargs["messages"][1]["role"] == "user"
    assert kwargs["messages"][1]["content"] == "user prompt"


@patch("backend.app.llm.openai.OpenAI")
def test_complete_passes_json_schema(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = type(
        "obj", (),
        {"choices": [type("obj", (),
                         {"message": type("obj", (),
                                          {"content": "{}"})()})()],
         "usage": None}
    )()

    p = OpenRouterProvider(api_key="sk-test")
    _complete(p, json_mode=True, schema=SQL_SCHEMA)
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["name"] == "sql_result"
    assert kwargs["response_format"]["json_schema"]["strict"] is True


@patch("backend.app.llm.openai.OpenAI")
def test_complete_raises_llm_error_on_api_error(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    from openai import APIError
    mock_client.chat.completions.create.side_effect = APIError(
        message="Bad request", request=None, body=None
    )

    p = OpenRouterProvider(api_key="sk-test")
    with pytest.raises(LLMError):
        _complete(p)


@patch("backend.app.llm.openai.OpenAI")
def test_health_check_ok(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = type(
        "obj", (),
        {"choices": [type("obj", (),
                         {"message": type("obj", (),
                                          {"content": "ok"})()})()],
         "usage": None}
    )()

    p = OpenRouterProvider(api_key="sk-test")
    out = _health(p)
    assert out["ok"] is True


@patch("backend.app.llm.openai.OpenAI")
def test_health_check_fails_without_key(mock_openai):
    p = OpenRouterProvider(api_key="")
    out = _health(p)
    assert out["ok"] is False
    assert "key" in out["error"].lower()


def test_provider_manager_returns_same_instance():
    cfg = {"openrouter_key": "sk-test"}
    mgr = ProviderManager(cfg)
    p1 = mgr.get("user-1")
    p2 = mgr.get("user-1")
    assert p1 is p2
    assert p1.api_key == "sk-test"


def test_provider_manager_reconfigure_clears():
    cfg = {"openrouter_key": "sk-test"}
    mgr = ProviderManager(cfg)
    p1 = mgr.get("user-1")
    mgr.reconfigure({"openrouter_key": "sk-test-2"})
    p2 = mgr.get("user-1")
    assert p1 is not p2
    assert p2.api_key == "sk-test-2"


def test_create_provider_builds_openrouter():
    p = create_provider({"openrouter_key": "sk-test"}, "user-1")
    assert isinstance(p, OpenRouterProvider)
    assert p.model == "deepseek-v4-flash"


def test_create_provider_rejects_missing_key():
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        create_provider({"openrouter_key": ""}, "user-1")
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd /home/somesh/Documents/bolodb && python -m pytest tests/test_openrouter.py -v 2>&1 | head -30
```
Expected: FAIL with various import/module errors

- [ ] **Step 4: Implement OpenRouterProvider in `backend/app/llm.py`**

Replace the entire file content. Key changes:

```python
"""All AI operations for BoloDB, powered by OpenRouter (deepseek-v4-flash).

This module is the ONLY place in the backend that talks to an AI model.
"""

import asyncio
import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod

import openai

log = logging.getLogger(__name__)

MODEL = "deepseek-v4-flash"


def _redact_error_text(text, max_len=200):
    s = text[:max_len]
    s = re.sub(r"sk-[A-Za-z0-9]{10,}", "[REDACTED_KEY]", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9._-]{20,}", "Bearer [REDACTED]", s)
    return s


class LLMError(Exception):
    def __init__(self, user_message, detail=""):
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail or user_message


def parse_json(text):
    s = text.replace("```json", "").replace("```", "").strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a : b + 1]
    return json.loads(s)


# JSON schemas for structured output. OpenAI strict mode requires
# additionalProperties: false on all objects and explicit "type" on every property.
# Each schema is wrapped with a "name" for OpenAI's response_format API.
SQL_SCHEMA = {
    "name": "sql_result",
    "schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "One read-only SELECT query answering the question.",
            },
            "restatement": {
                "type": "string",
                "description": "One plain sentence describing what the query returns, no jargon.",
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any assumptions made while interpreting the question.",
            },
        },
        "required": ["sql", "restatement", "assumptions"],
        "additionalProperties": False,
    },
}

GLOSSARY_SCHEMA = {
    "name": "glossary",
    "schema": {
        "type": "object",
        "properties": {
            "glossary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "maps_to": {"type": "string"},
                        "sql_hint": {"type": "string"},
                    },
                    "required": ["term", "maps_to", "sql_hint"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["glossary"],
        "additionalProperties": False,
    },
}

STARTERS_SCHEMA = {
    "name": "starters",
    "schema": {
        "type": "object",
        "properties": {
            "starters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "sql": {"type": "string"},
                        "restatement": {"type": "string"},
                    },
                    "required": ["question", "sql", "restatement"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["starters"],
        "additionalProperties": False,
    },
}

EXPLAIN_SCHEMA = {
    "name": "explanation",
    "schema": {
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "2-4 plain sentences a non-technical person understands.",
            }
        },
        "required": ["explanation"],
        "additionalProperties": False,
    },
}

CATALOG_SCHEMA = {
    "name": "catalog",
    "schema": {
        "type": "object",
        "properties": {
            "column_descriptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "column": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["table", "column", "description"],
                    "additionalProperties": False,
                },
            },
            "metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "sql_expression": {"type": "string"},
                    },
                    "required": ["name", "sql_expression"],
                    "additionalProperties": False,
                },
            },
            "synonyms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "entity_type": {"type": "string"},
                        "entity_name": {"type": "string"},
                    },
                    "required": ["term", "entity_type", "entity_name"],
                    "additionalProperties": False,
                },
            },
            "value_maps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "column": {"type": "string"},
                        "db_value": {"type": "string"},
                        "business_label": {"type": "string"},
                    },
                    "required": ["table", "column", "db_value", "business_label"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["column_descriptions", "metrics", "synonyms", "value_maps"],
        "additionalProperties": False,
    },
}

SHORTLIST_SCHEMA = {
    "name": "shortlist",
    "schema": {
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of tables from the catalog that may be needed.",
            }
        },
        "required": ["tables"],
        "additionalProperties": False,
    },
}


def parse_sql_output(raw):
    """Normalize a model SQL response into ``{sql, restatement, assumptions}``."""
    if isinstance(raw, dict):
        obj = raw
    else:
        try:
            obj = parse_json(raw)
        except Exception:
            obj = {}
    if not isinstance(obj, dict):
        obj = {}
    sql = obj.get("sql")
    restatement = obj.get("restatement")
    assumptions = obj.get("assumptions")
    if isinstance(assumptions, str):
        assumptions = [assumptions] if assumptions.strip() else []
    elif isinstance(assumptions, list):
        assumptions = [str(a) for a in assumptions if str(a).strip()]
    else:
        assumptions = []
    sql = (sql if isinstance(sql, str) else ("" if sql is None else str(sql))).strip()
    restatement = (
        restatement
        if isinstance(restatement, str)
        else ("" if restatement is None else str(restatement))
    ).strip()
    return {"sql": sql, "restatement": restatement, "assumptions": assumptions}


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system, user, json_mode=False, schema=None): ...

    @abstractmethod
    async def health_check(self): ...


class OpenRouterProvider(LLMProvider):
    """OpenRouter API via the OpenAI SDK.

    Uses the openai Python library pointed at OpenRouter's base URL.
    All model calls go to ``deepseek-v4-flash``.
    """

    def __init__(self, api_key, model=None):
        self.api_key = api_key
        self.model = model or MODEL
        self._client = openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            max_retries=2,
        )

    async def complete(self, system, user, json_mode=False, schema=None, **kwargs):
        if not self.api_key:
            raise LLMError(
                "OpenRouter API key is not configured. "
                "Set OPENROUTER_API_KEY in the server environment.",
                detail="empty api_key",
            )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        if json_mode and schema:
            schema_copy = dict(schema)
            name = schema_copy.pop("name", "response")
            completion_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "strict": True,
                    "schema": schema_copy,
                },
            }
        elif json_mode:
            completion_kwargs["response_format"] = {"type": "json_object"}

        try:
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: self._client.chat.completions.create(**completion_kwargs),
            )
        except openai.APIError as e:
            raise LLMError(
                "The AI service returned an error. Please try again.",
                detail=f"OpenRouter API error: {_redact_error_text(str(e))}",
            )
        except Exception as e:
            raise LLMError(
                "Could not reach the AI service — check your internet connection.",
                detail=f"OpenRouter error: {_redact_error_text(str(e))}",
            )

        choices = resp.choices if hasattr(resp, "choices") else []
        if not choices:
            raise LLMError(
                "The AI returned an empty answer — please try again.",
                detail="no choices in response",
            )
        text = (choices[0].message.content or "").strip()
        if not text:
            raise LLMError(
                "The AI returned an empty answer — please try again.",
                detail="empty content",
            )
        return text

    async def health_check(self):
        if not self.api_key:
            return {"ok": False, "error": "No OpenRouter API key configured"}
        try:
            await self.complete("Respond with OK", "OK", json_mode=False)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def create_provider(cfg, user_id=None):
    """Build the OpenRouter provider from config.

    ``user_id`` is accepted for backwards compatibility but ignored —
    the OpenRouter key is shared across all users.
    """
    key = cfg.get("openrouter_key", "") or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Set it in the environment or config to use AI features."
        )
    return OpenRouterProvider(api_key=key)


class ProviderManager:
    """Caches one provider (shared across all users since the key is shared)."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._provider = None

    def get(self, user_id=None):
        if self._provider is None:
            self._provider = create_provider(self.cfg)
        return self._provider

    def invalidate(self, user_id=None):
        self._provider = None

    def reconfigure(self, cfg):
        self.cfg = cfg
        self._provider = None
```

Replace the rest of `llm.py` with the remaining prompt-building functions (`_context_block`, `_glossary_block`, `_semantic_block`, `_examples_block`, `build_sql_system_prompt`, `generate_sql`, `shortlist_tables`, `explain_sql`, `suggest_catalog`, `generate_glossary`, `generate_starters`) — these are unchanged from the original, just remove the `thinking_budget` parameter from all signatures and calls since OpenRouter/gpt-4o doesn't support Gemini-style thinking.

Update: Remove `thinking_budget` from all function signatures. In `generate_sql`:
```python
async def generate_sql(
    provider,
    question,
    schema_text,
    dialect,
    glossary,
    retrieved,
    max_examples=3,
    context=None,
    feedback="",
    catalog=None,
):
```

In `shortlist_tables`, remove `thinking_budget=0` from the `provider.complete()` call:
```python
raw = await provider.complete(
    system, question, json_mode=True, schema=SHORTLIST_SCHEMA
)
```

In `explain_sql`, remove `thinking_budget=0`:
```python
raw = await provider.complete(
    system, sql, json_mode=True, schema=EXPLAIN_SCHEMA
)
```

In `suggest_catalog`, remove `thinking_budget=0`:
```python
raw = await provider.complete(
    system,
    "Produce the catalog.",
    json_mode=True,
    schema=CATALOG_SCHEMA,
)
```

In `generate_glossary`, remove `thinking_budget=0`:
```python
raw = await provider.complete(
    system,
    "Produce the glossary.",
    json_mode=True,
    schema=GLOSSARY_SCHEMA,
)
```

In `generate_starters`, remove `thinking_budget=0`:
```python
raw = await provider.complete(
    system,
    "Produce starter questions.",
    json_mode=True,
    schema=STARTERS_SCHEMA,
)
```

Also remove the import of `get_api_key` from `backend.app.config` at the top of the file (since config no longer has per-user keys):
```python
# Remove this line:
from backend.app.config import get_api_key
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /home/somesh/Documents/bolodb && python -m pytest tests/test_openrouter.py -v 2>&1 | tail -20
```
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add backend/requirements.txt backend/app/llm.py tests/test_openrouter.py && git commit -m "feat: add OpenRouterProvider, remove GeminiProvider"
```

---

### Task 2: Simplify config.py

**Files:**
- Modify: `backend/app/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: simplified config with only `openrouter_key`, `last_db_url`, no `api_keys` dict

- [ ] **Step 1: Update `tests/test_config.py`**

Replace the entire file:
```python
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
        save_config({"test": "data"})
        assert json.loads((config_dir / "config.json").read_text()) == {"test": "data"}


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
            json.dumps({
                "provider": "gemini",
                "model": "gemini-flash-latest",
                "api_keys": {"user-1": {"gemini": "AIza-old"}},
            })
        )
        cfg = load_config()
        assert "api_keys" not in cfg
        assert "provider" not in cfg
        assert "model" not in cfg
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/somesh/Documents/bolodb && python -m pytest tests/test_config.py -v 2>&1 | tail -30
```
Expected: FAIL

- [ ] **Step 3: Rewrite `backend/app/config.py`**

Replace the entire file:
```python
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
KB_FILE = CONFIG_DIR / "knowledge.db"
_DB_URL_KEY_FILE = CONFIG_DIR / "db_url.key"

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
    d.pop("provider", None)
    d.pop("model", None)
    d.pop("api_keys", None)

    cfg = {**default_config(), **d}
    # API key is always read fresh from env, never from disk
    cfg["openrouter_key"] = os.environ.get("OPENROUTER_API_KEY", "")
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/somesh/Documents/bolodb && python -m pytest tests/test_config.py -v 2>&1 | tail -20
```
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add backend/app/config.py tests/test_config.py && git commit -m "refactor: simplify config, remove per-user API key storage"
```

---

### Task 3: Update schema_link.py

**Files:**
- Modify: `backend/app/schema_link.py`

- [ ] **Step 1: Hardcode `model_budget()`**

```python
def model_budget(model=None):
    """Prompt budget — hardcoded for deepseek-v4-flash."""
    return {"tier": "flash", "max_tables": 20, "samples": 2, "max_examples": 5}
```

- [ ] **Step 2: Update tests if `test_schema_link.py` references `model_budget`**

Search for `model_budget` calls in tests:
```bash
cd /home/somesh/Documents/bolodb && grep -n "model_budget" tests/test_schema_link.py
```

If found, update the test calls to not pass a model name.

- [ ] **Step 3: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add backend/app/schema_link.py && git commit -m "refactor: hardcode model_budget for gpt-4o"
```

---

### Task 4: Update controllers, models, routes

**Files:**
- Modify: `backend/app/controllers/system.py`
- Modify: `backend/app/models/api.py`
- Modify: `backend/app/routes/system.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/server.py`

- [ ] **Step 1: Simplify `controllers/system.py`**

```python
import os
import logging

from backend.app import config as cfgmod
from backend.app.secrets import (
    get_jwt_secret,
    get_supabase_url,
    get_supabase_anon_key,
)

log = logging.getLogger(__name__)


async def get_state(user_id, db, cfg, kb):
    config = cfgmod.public_config(cfg)
    config.pop("last_db_url", None)
    s = {"connected": db.connected(user_id), "config": config}
    if db.connected(user_id):
        s["database"] = {
            "url": db.get_info(user_id)["url"],
            "dialect": db.get_dialect(user_id),
            "db_id": db.get_info(user_id)["db_id"],
            "tables": db.get_info(user_id)["tables"],
            "has_knowledge": kb.count_verified(db.get_db_id(user_id)) > 0,
        }
        s["trust"] = kb.trust_level(db.get_db_id(user_id))
        s["glossary"] = kb.get_glossary(db.get_db_id(user_id))
        s["starters"] = [
            v["question"] for v in kb.get_verified(db.get_db_id(user_id))[:6]
        ]
    return s


async def get_health(pg_status="unknown"):
    env_checks = {
        "JWT_SECRET": bool(get_jwt_secret()) if os.getenv("JWT_SECRET") else False,
        "SUPABASE_URL": bool(get_supabase_url()),
        "SUPABASE_ANON_KEY": bool(get_supabase_anon_key()),
        "SUPABASE_JWT_SECRET": bool(os.getenv("SUPABASE_JWT_SECRET")),
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "COOKIE_SECURE": os.getenv("COOKIE_SECURE", "false"),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "(not set, using defaults)"),
        "OPENROUTER_API_KEY": bool(os.getenv("OPENROUTER_API_KEY")),
    }
    jwks_status = "unchecked"
    supabase_url = get_supabase_url()
    if supabase_url:
        try:
            import httpx
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            resp = await httpx.AsyncClient(timeout=5).get(jwks_url)
            if resp.status_code == 200:
                jwks_status = "reachable"
            else:
                jwks_status = f"unexpected_status:{resp.status_code}"
        except Exception as e:
            jwks_status = f"unreachable:{e.__class__.__name__}"
    return {
        "status": "ok" if pg_status == "connected" else "degraded",
        "postgres": pg_status,
        "env": env_checks,
        "supabase_jwks": jwks_status,
    }


async def update_config(user_id, cfg, providers, req_data):
    """Config updates — model and API key are no longer user-configurable."""
    cfgmod.save_config(cfg)
    try:
        h = await providers.get(user_id).health_check()
    except Exception:
        log.exception("Health check failed")
        h = {"ok": False, "error": "Health check failed"}
    return {"config": cfgmod.public_config(cfg), "health": h}
```

- [ ] **Step 2: Simplify `models/api.py`**

```python
from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    # No provider, model, or api_key fields — these are fixed to OpenRouter/gpt-4o
    pass


class ConnectReq(BaseModel):
    db_url: str


class ContextTurn(BaseModel):
    question: str
    sql: str
    restatement: str = ""


class QueryReq(BaseModel):
    question: str
    context: list[ContextTurn] = []
    conversation_id: str | None = None


class VerifyReq(BaseModel):
    question: str
    sql: str
    restatement: str = ""


class FeedbackReq(BaseModel):
    query_id: str = ""
    verdict: str
    reason: str = ""
    question: str = ""
    sql: str = ""
    restatement: str = ""


class RawSQLReq(BaseModel):
    sql: str


class GlossaryItem(BaseModel):
    term: str
    maps_to: str = ""
    sql_hint: str = ""


class StarterItem(BaseModel):
    question: str
    sql: str
    restatement: str = ""


class SaveOnboardReq(BaseModel):
    glossary: list[GlossaryItem] = []
    starters: list[StarterItem] = []


class ColumnDescription(BaseModel):
    table: str
    column: str
    description: str = ""


class MetricDefinition(BaseModel):
    name: str
    description: str = ""
    sql_expression: str = ""


class JoinPath(BaseModel):
    tables: str
    join_condition: str
    description: str = ""


class Synonym(BaseModel):
    term: str
    entity_type: str = ""
    entity_name: str = ""


class ValueMapping(BaseModel):
    table: str
    column: str
    db_value: str
    business_label: str = ""


class CatalogPayload(BaseModel):
    column_descriptions: list[ColumnDescription] = []
    metrics: list[MetricDefinition] = []
    joins: list[JoinPath] = []
    synonyms: list[Synonym] = []
    value_maps: list[ValueMapping] = []
```

- [ ] **Step 3: Update `routes/system.py`**

```python
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.app.dependencies import (
    get_current_user,
    get_db,
    get_cfg,
    get_kb,
    get_providers,
)
from backend.app.models.api import ConfigUpdate
from backend.app.secrets import get_supabase_url, get_supabase_anon_key
import backend.app.controllers.system as ctrl

router = APIRouter()


@router.get("/api/state")
async def state(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    cfg=Depends(get_cfg),
    kb=Depends(get_kb),
):
    user_id = user_token["user_id"]
    return await ctrl.get_state(user_id, db, cfg, kb)


@router.get("/api/health")
async def health():
    pg_status = "connected"
    try:
        from backend.app.pgdatabase import get_engine
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        pg_status = f"disconnected:{e.__class__.__name__}"
    result = await ctrl.get_health(pg_status)
    if pg_status != "connected":
        return JSONResponse(content=result, status_code=503)
    return JSONResponse(content=result)


@router.get("/api/config/public")
async def public_config():
    return JSONResponse(
        {
            "supabase_url": get_supabase_url(),
            "supabase_anon_key": get_supabase_anon_key(),
        }
    )


@router.post("/api/config")
async def update_config(
    req: ConfigUpdate,
    user_token=Depends(get_current_user),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
):
    return await ctrl.update_config(user_token["user_id"], cfg, providers, req)
```

- [ ] **Step 4: Update `dependencies.py`** — no changes needed (already generic)

- [ ] **Step 5: Update `server.py`** — no changes needed (already generic, just passes cfg to ProviderManager)

- [ ] **Step 6: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add backend/app/controllers/system.py backend/app/models/api.py backend/app/routes/system.py && git commit -m "refactor: simplify controllers, models, routes for OpenRouter"
```

---

### Task 5: Update frontend Settings.svelte

**Files:**
- Modify: `frontend/src/lib/components/Settings.svelte`

- [ ] **Step 1: Rewrite Settings.svelte**

```svelte
<script lang="ts">
  import Button from "$lib/components/ui/Button.svelte";
  import DataCatalog from "$lib/components/DataCatalog.svelte";
  import { onMount } from "svelte";

  let {
    onClose,
    onDisconnect,
    openCatalogTrigger = 0,
  }: {
    onClose: () => void;
    onDisconnect?: () => void;
    openCatalogTrigger?: number;
  } = $props();

  let showCatalog = $state(false);

  $effect(() => {
    if (openCatalogTrigger > 0) showCatalog = true;
  });
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  onclick={onClose}
  style="position:fixed;inset:0;z-index:50;background:rgba(20,28,24,.4);backdrop-filter:blur(3px);display:grid;place-items:center;animation:fadein .2s ease both;padding:24px"
>
  <div
    onclick={(e) => e.stopPropagation()}
    class="card"
    style="width:560px;max-width:100%;padding:0;overflow:hidden;animation:pop .25s var(--spring) both"
  >
    <div
      style="padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between"
    >
      <div style="display:flex;align-items:center;gap:10px">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          style="color:var(--brand)"
          ><circle
            cx="12"
            cy="12"
            r="3.2"
            stroke="currentColor"
            stroke-width="1.9"
          /><path
            d="M12 2.5v2.3M12 19.2v2.3M21.5 12h-2.3M4.8 12H2.5M18.7 5.3l-1.6 1.6M6.9 17.1l-1.6 1.6M18.7 18.7l-1.6-1.6M6.9 6.9L5.3 5.3"
            stroke="currentColor"
            stroke-width="1.9"
            stroke-linecap="round"
          /></svg
        >
        <span style="font-weight:800;font-size:17px">Settings</span>
      </div>
      <button
        onclick={onClose}
        aria-label="Close settings"
        class="btn btn-quiet btn-sm"
        style="padding:8px"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
          ><path
            d="M6 6l12 12M18 6L6 18"
            stroke="currentColor"
            stroke-width="2.2"
            stroke-linecap="round"
          /></svg
        >
      </button>
    </div>
    <div style="padding:24px">
      <div
        style="display:flex;align-items:center;gap:10px;padding:12px 13px;border-radius:var(--radius-sm);background:var(--surface-2);border:1.5px solid var(--border);margin-bottom:20px"
      >
        <span
          style="width:30px;height:30px;border-radius:8px;flex-shrink:0;display:grid;place-items:center;background:var(--surface-3);color:var(--brand)"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
            ><path
              d="M13 2L4 14h7l-1 8 9-12h-7l1-8z"
              fill="currentColor"
            /></svg
          >
        </span>
        <div style="min-width:0">
          <div style="font-weight:700;font-size:13.5px">OpenRouter (deepseek-v4-flash)</div>
          <div style="font-size:11px;color:var(--faint);font-weight:600">
            Powers every AI feature in BoloDB
          </div>
        </div>
      </div>

      <div
        style="margin-top:20px;padding-top:20px;border-top:1px solid var(--border)"
      >
        <div
          style="font-size:13px;font-weight:700;color:var(--ink-2);margin-bottom:4px"
        >
          Data catalog
        </div>
        <div
          style="font-size:12px;color:var(--faint);font-weight:550;margin-bottom:10px"
        >
          Teach BoloDB your business terms, metrics, and value meanings so
          answers get more accurate.
        </div>
        <button
          onclick={() => (showCatalog = true)}
          class="btn btn-quiet btn-sm"
          style="font-size:13px;font-weight:650;padding:8px 14px;border:1px solid var(--border);border-radius:var(--radius-sm)"
        >
          Manage data catalog →
        </button>
      </div>
    </div>
    <div
      style="padding:16px 24px;border-top:1px solid var(--border);background:var(--surface-2)"
    >
      {#if onDisconnect}
        <div
          style="margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid var(--border)"
        >
          <div
            style="font-size:12.5px;color:var(--faint);margin-bottom:8px;font-weight:550"
          >
            Want to connect a different database?
          </div>
          <button
            onclick={onDisconnect}
            style="font-size:13px;color:var(--c-low-ink);background:none;border:1px solid #EBC6BD;border-radius:var(--radius-sm);padding:7px 14px;cursor:pointer;font-weight:650"
            >Disconnect &amp; change database</button
          >
        </div>
      {/if}
      <div style="display:flex;justify-content:flex-end;gap:10px">
        <Button kind="ghost" onclick={onClose}>Close</Button>
      </div>
    </div>
  </div>
</div>

{#if showCatalog}
  <DataCatalog onClose={() => (showCatalog = false)} />
{/if}
```

- [ ] **Step 2: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add frontend/src/lib/components/Settings.svelte && git commit -m "feat: simplify Settings — remove model selector and API key UI"
```

---

### Task 6: Update frontend state, data, types, and component props

**Files:**
- Modify: `frontend/src/lib/appState.svelte.ts`
- Modify: `frontend/src/lib/data.ts`
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/components/Sidebar.svelte`
- Modify: `frontend/src/lib/components/AskScreen.svelte`
- Modify: `frontend/src/lib/components/AnswerCard.svelte`
- Modify: `frontend/src/routes/chat/+page.svelte`
- Modify: `frontend/src/routes/dashboard/+page.svelte`

- [ ] **Step 1: Update `appState.svelte.ts`**

Remove `engine`, `modelName`, `apiKeySet`. Update `init()` to not reference these. Update `redirect` logic to skip API key check:

```typescript
import { trustFor, schemaObjToDisplay } from "$lib/data";
import { apiCall } from "$lib/api";
import type { DbInfo, SchemaTable, Toast } from "$lib/types";
import { goto } from "$app/navigation";
import { browser } from "$app/environment";

class AppState {
  verifiedCount = $state(0);
  toast = $state<Toast | null>(null);
  realSchema = $state<SchemaTable[] | null>(null);
  dbInfo = $state<DbInfo | null>(null);
  starters = $state<string[]>([]);
  isLoaded = $state(false);
  theme = $state("dark");
  activeConversationId = $state<string | null>(null);

  constructor() {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("bolodb_theme");
      if (stored) {
        this.theme = stored;
      }
    }
  }

  toggleTheme() {
    const nextTheme = this.theme === "dark" ? "crisp" : "dark";
    this.theme = nextTheme;
    if (typeof window !== "undefined") {
      localStorage.setItem("bolodb_theme", nextTheme);
      document.documentElement.setAttribute("data-theme", nextTheme);
    }
  }

  get prevLevel() {
    return trustFor(this.verifiedCount).key;
  }

  async init(redirect: boolean = true) {
    try {
      const s = await apiCall("/api/state");
      if (s.connected) {
        this.verifiedCount = s.trust?.verified || 0;
        this.dbInfo = s.database || null;
        this.starters = s.starters || [];
        try {
          const schema = await apiCall("/api/schema");
          this.realSchema = schemaObjToDisplay(schema);
        } catch (e) {
          console.error("Failed to load schema:", e);
        }
        this.isLoaded = true;
        if (redirect) {
          if (this.dbInfo?.has_knowledge) {
            goto("/chat");
          } else {
            goto("/onboard");
          }
        }
      } else {
        this.isLoaded = true;
        if (redirect) goto("/connect");
      }
    } catch (e: any) {
      this.isLoaded = true;
      const msg = e.message || "";
      if (
        msg.includes("Access Denied") ||
        msg.includes("Session Expired") ||
        msg.includes("Invalid Token") ||
        msg.includes("401")
      ) {
        if (
          typeof window !== "undefined" &&
          !window.location.pathname.startsWith("/login") &&
          !window.location.pathname.startsWith("/signup") &&
          window.location.pathname !== "/"
        ) {
          goto("/login");
        }
      } else {
        if (redirect) goto("/connect");
      }
    }
  }

  async logout() {
    try {
      await apiCall("/api/auth/logout", {});
    } catch (e) {
      console.error("Failed to logout:", e);
    }
    if (browser) {
      const { default: posthog } = await import("posthog-js");
      posthog.capture("user_logged_out");
      posthog.reset();
    }
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
    this.activeConversationId = null;
    goto("/login");
  }

  async setConnect(isSample: boolean, res: DbInfo) {
    if (res) {
      this.dbInfo = res;
      this.verifiedCount = res.trust?.verified || 0;
      if (res.starters) this.starters = res.starters;
      try {
        const schema = await apiCall("/api/schema");
        this.realSchema = schemaObjToDisplay(schema);
      } catch (e) {
        console.error("Failed to load schema:", e);
      }
      if (res.has_knowledge) {
        goto("/chat");
        return;
      }
    }
    goto("/onboard");
  }

  async setOnboardDone(seedCount: number) {
    try {
      const s = await apiCall("/api/state");
      const n = s.trust?.verified || seedCount;
      this.verifiedCount = n;
      if (s.database) this.dbInfo = s.database;
      if (s.starters) this.starters = s.starters;
    } catch {
      this.verifiedCount = seedCount;
    }
    if (browser) {
      const { default: posthog } = await import("posthog-js");
      posthog.capture("onboarding_completed", {
        seed_count: seedCount,
        dialect: this.dbInfo?.dialect,
      });
    }
  }

  verify(apiCount?: number) {
    const oldLevel = this.prevLevel;
    if (apiCount !== undefined) {
      this.verifiedCount = apiCount;
    } else {
      this.verifiedCount++;
    }
    const newLevel = this.prevLevel;
    const upgraded =
      trustFor(this.verifiedCount).idx >
      trustFor(oldLevel === newLevel ? this.verifiedCount : this.verifiedCount).idx;
    if (
      newLevel !== oldLevel &&
      (newLevel === "assisted" || newLevel === "trusted")
    ) {
      const msg =
        newLevel === "assisted"
          ? {
              title: "Accuracy milestone reached",
              body: "Confident answers now show immediately — new questions still get a second look.",
            }
          : {
              title: "Fully calibrated",
              body: "All answers appear directly now. Reasoning is always one tap away.",
            };
      this.toast = msg;
      setTimeout(() => (this.toast = null), 4200);
    }
  }

  async disconnect() {
    try {
      await apiCall("/api/disconnect", {});
    } catch (e) {
      console.error("Failed to disconnect:", e);
    }
    this.dbInfo = null;
    this.realSchema = null;
    this.verifiedCount = 0;
    this.starters = [];
    this.activeConversationId = null;
    goto("/connect");
  }
}

export const appState = new AppState();
```

- [ ] **Step 2: Update `data.ts`**

Remove `providers` array and `GEMINI_KEY_URL`:
```typescript
/** BoloDB — Static data & helpers (formerly window.BOLO) */
import type {
  Provider,
  TrustLevel,
  WrongReason,
  SchemaTable,
  GlossaryItem,
  StarterItem,
  BankItem,
} from "./types";

// ... keep schema, glossary, starters, wrongReasons, suggestions, trustFor, schemaObjToDisplay, humanError, capitalize, formatTime exactly as-is ...
```

(Keep the file but remove lines 118-133: the `providers` array and `GEMINI_KEY_URL`.)

- [ ] **Step 3: Update `types.ts`**

Remove the `Provider` interface if nothing else uses it. Check if `Provider` is imported anywhere:
```bash
cd /home/somesh/Documents/bolodb && grep -rn "Provider" frontend/src --include="*.ts" --include="*.svelte"
```

If `Provider` is only used in `data.ts`, remove the interface from `types.ts` and remove the import in `data.ts`.

- [ ] **Step 4: Update `Sidebar.svelte`**

Remove `engine`, `modelName`, `apiKeySet` from props. Update the display to show "OpenRouter" and "gpt-4o" statically:

```svelte
let { verifiedCount, onSettings, schema, dbInfo, onConversationSelect, activeConversationId, conversationTrigger = 0 }:
  { verifiedCount: number; onSettings: () => void; schema: SchemaTable[] | null; dbInfo: DbInfo | null; onConversationSelect?: (id: string) => void; activeConversationId?: string | null; conversationTrigger?: number } = $props();
```

Replace any `{modelName || prov.model}` with the hardcoded `gpt-4o`.

- [ ] **Step 5: Update `AskScreen.svelte`**

Remove `engine`, `modelName`, `setModelName`, `apiKeySet`, `setApiKeyStatus` from props. Replace the model name display with hardcoded "gpt-4o". Remove the Settings import's modelName/setModelName props.

- [ ] **Step 6: Update `chat/+page.svelte`**

Remove `modelName`, `apiKeySet`, `setModelName`, `setApiKeyStatus` props from `AskScreen`:

```svelter
<AskScreen
  verifiedCount={appState.verifiedCount}
  onVerify={(apiCount) => appState.verify(apiCount)}
  onUpdateStarters={(s) => appState.starters = s}
  toast={appState.toast}
  realSchema={appState.realSchema}
  dbInfo={appState.dbInfo}
  starters={appState.starters}
  onDisconnect={() => appState.disconnect()}
  onActiveConversationChange={(id) => appState.activeConversationId = id}
/>
```

- [ ] **Step 7: Update `dashboard/+page.svelte`**

Remove the `modelName` reference:
```svelter
<!-- Before: -->
{#if appState.modelName}
  <span ...>{appState.modelName}</span>
{/if}

<!-- After: -->
<span ...>gpt-4o</span>
```

- [ ] **Step 8: Update `AnswerCard.svelte`**

Remove the `modelName` prop or replace display with hardcoded "gpt-4o".

- [ ] **Step 9: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add frontend/src/lib/appState.svelte.ts frontend/src/lib/data.ts frontend/src/lib/types.ts frontend/src/lib/components/Sidebar.svelte frontend/src/lib/components/AskScreen.svelte frontend/src/lib/components/AnswerCard.svelte frontend/src/routes/chat/+page.svelte frontend/src/routes/dashboard/+page.svelte && git commit -m "feat: strip modelName/engine/apiKeySet from frontend state"
```

---

### Task 7: Update env, docker-compose, and docs

**Files:**
- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Create: `docs/03-the-ai-layer-openrouter.md`
- Remove: `docs/03-the-ai-layer-gemini.md`

- [ ] **Step 1: Update `.env.example`**

Replace:
```
# ── AI ──
# Google Gemini API key (https://aistudio.google.com/apikey)
# Used to generate SQL from natural-language questions.
# Users can also supply their own key in-app; this is the fallback.
GEMINI_API_KEY=
```
with:
```
# ── AI ──
# OpenRouter API key (https://openrouter.ai/keys)
# Used to generate SQL from natural-language questions via deepseek-v4-flash.
OPENROUTER_API_KEY=
```

- [ ] **Step 2: Update `docker-compose.yml`**

Replace `GEMINI_API_KEY=${GEMINI_API_KEY}` with `OPENROUTER_API_KEY=${OPENROUTER_API_KEY}`.

- [ ] **Step 3: Write `docs/03-the-ai-layer-openrouter.md`**

Create a concise doc:
```markdown
# AI Layer — OpenRouter

BoloDB uses OpenRouter (deepseek-v4-flash) for all AI operations:
- SQL generation (question → SQL)
- SQL explanation (SQL → plain English)
- Glossary suggestion (onboarding)
- Starter question generation (onboarding)
- Semantic catalog suggestion
- Two-stage schema linking (table shortlisting)

## Configuration

Set `OPENROUTER_API_KEY` in the environment. The key is shared across all
users — there is no per-user API key storage.

## Architecture

All AI operations funnel through `backend/app/llm.py`:

- `OpenRouterProvider` — wraps the OpenAI SDK pointed at
  `https://openrouter.ai/api/v1`. Uses `deepseek-v4-flash` with
  `max_retries=2` and `temperature=0.1`.
- `create_provider()` — factory function, called at startup.
- `ProviderManager` — caches a single shared provider instance.

## Structured Output

All AI responses use OpenAI's `response_format: { type: "json_schema" }`
with `strict: true`. Schemas are defined as module-level constants in
`llm.py` with the `"name"` wrapper required by the API.

## Adding a Different Model

To change the model, edit `MODEL` in `backend/app/llm.py` or set
`OPENROUTER_MODEL` in the environment (if implemented).
```

- [ ] **Step 4: Remove old Gemini doc**

```bash
cd /home/somesh/Documents/bolodb && git rm docs/03-the-ai-layer-gemini.md
```

- [ ] **Step 5: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add .env.example docker-compose.yml docs/03-the-ai-layer-openrouter.md && git commit -m "docs: update env, docker-compose, and AI layer docs for OpenRouter"
```

---

### Task 8: Update structured output and remaining tests

**Files:**
- Modify: `tests/test_structured_output.py`
- Remove: `tests/test_gemini.py` (already replaced by `tests/test_openrouter.py` in Task 0)

- [ ] **Step 1: Update `tests/test_structured_output.py`**

The `test_schema_shape` test checks `SQL_SCHEMA` for `additionalProperties` and required fields. Since `SQL_SCHEMA` now has a `"name"` wrapper, update it:

```python
def test_schema_shape():
    inner = SQL_SCHEMA["schema"]
    assert inner["type"] == "object"
    assert set(inner["required"]) == {"sql", "restatement", "assumptions"}
    assert inner["additionalProperties"] is False
    assert inner["properties"]["assumptions"]["type"] == "array"
    assert SQL_SCHEMA["name"] == "sql_result"
```

- [ ] **Step 2: Run all tests**

```bash
cd /home/somesh/Documents/bolodb && python -m pytest tests/ -v 2>&1 | tail -40
```
Expected: all tests pass

- [ ] **Step 3: Commit**

```bash
cd /home/somesh/Documents/bolodb && git add tests/ && git commit -m "test: update structured output and config tests for OpenRouter"
```

---

## Spec Coverage Check

| Spec Requirement | Tasks Covering It |
|---|---|
| Remove Gemini integration | Task 1 (new OpenRouterProvider), Task 2 (config cleanup) |
| Add OpenRouter with OpenAI SDK | Task 1 |
| Hardcode model to deepseek-v4-flash | Task 1 (`MODEL = "deepseek-v4-flash"`) |
| Read shared key from env var | Task 2 (`OPENROUTER_API_KEY`) |
| Strip per-user API key storage | Task 2, Task 4 (controllers) |
| Strip model selector UI | Task 5 (Settings.svelte) |
| Strip API key UI | Task 5 (Settings.svelte) |
| Simplify schema_link.py | Task 3 |
| Update tests | Task 1 (test_openrouter.py), Task 2 (test_config.py), Task 8 (test_structured_output.py) |
| Update .env.example / docker-compose | Task 7 |
| Update docs | Task 7 |
| Strip frontend state (modelName, etc.) | Task 6 |

## Execution Order

Recommended task order (sequential dependencies):
1. Task 1 (OpenRouterProvider + tests)
2. Task 2 (config.py + tests)
3. Task 3 (schema_link.py)
4. Task 4 (controllers/models/routes)
5. Task 5 (Settings.svelte)
6. Task 6 (frontend state/components)
7. Task 7 (env/docker/docs)
8. Task 8 (remaining tests)
