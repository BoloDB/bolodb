"""Tests for the Gemini provider (backend/app/llm.py).

No real network calls: httpx.AsyncClient is replaced with a fake that records
the request and returns canned responses, so we can verify the request shape
(headers, structured-output config, retry behaviour) and the error taxonomy.
"""

import asyncio

import httpx
import pytest

from backend.app import llm
from backend.app.llm import (
    DEFAULT_GEMINI_MODEL,
    GeminiProvider,
    LLMError,
    ProviderManager,
    create_provider,
    to_gemini_schema,
)


def _gemini_response(text):
    """Minimal successful generateContent payload."""
    return {
        "candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]
    }


class FakeResponse:
    def __init__(self, status_code, json_data=None, text=""):
        self.status_code = status_code
        self._json = json_data or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class FakeAsyncClient:
    """Stands in for httpx.AsyncClient; pops queued responses per request.

    ``queue`` and ``requests`` are class-level so the ``fake_http`` fixture
    (which resets them before each test) can control them without needing a
    reference to each instance.  This is safe because the fixture replaces
    ``httpx.AsyncClient`` globally, so only one FakeAsyncClient exists per
    test.
    """

    queue: list = []
    requests: list = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, headers=None, json=None):
        FakeAsyncClient.requests.append({"url": url, "headers": headers, "json": json})
        item = FakeAsyncClient.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def get(self, url, params=None, headers=None):
        FakeAsyncClient.requests.append({"url": url, "headers": headers})
        item = FakeAsyncClient.queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def fake_http(monkeypatch):
    FakeAsyncClient.queue = []
    FakeAsyncClient.requests = []
    monkeypatch.setattr(llm.httpx, "AsyncClient", FakeAsyncClient)
    # No real sleeping between retries.
    monkeypatch.setattr(llm.asyncio, "sleep", _instant_sleep)
    yield


async def _instant_sleep(_seconds):
    return None


def _complete(provider, **kwargs):
    return asyncio.run(provider.complete("system prompt", "user prompt", **kwargs))


# --- request shape ----------------------------------------------------------


def test_complete_sends_key_header_and_system_instruction():
    FakeAsyncClient.queue = [FakeResponse(200, _gemini_response("hello"))]
    p = GeminiProvider(api_key="AIza-test")
    out = _complete(p)
    assert out == "hello"
    req = FakeAsyncClient.requests[0]
    assert f"/models/{DEFAULT_GEMINI_MODEL}:generateContent" in req["url"]
    assert req["headers"]["X-goog-api-key"] == "AIza-test"
    assert req["json"]["system_instruction"]["parts"][0]["text"] == "system prompt"
    assert req["json"]["contents"][0]["parts"][0]["text"] == "user prompt"


def test_complete_passes_response_schema_for_structured_output():
    FakeAsyncClient.queue = [FakeResponse(200, _gemini_response("{}"))]
    p = GeminiProvider(api_key="k")
    _complete(p, schema=llm.SQL_SCHEMA)
    cfg = FakeAsyncClient.requests[0]["json"]["generationConfig"]
    assert cfg["responseMimeType"] == "application/json"
    # additionalProperties is not part of Gemini's schema dialect
    assert "additionalProperties" not in cfg["responseSchema"]
    assert set(cfg["responseSchema"]["required"]) == {
        "sql",
        "restatement",
        "assumptions",
    }


def test_thinking_budget_sent_for_supported_models():
    FakeAsyncClient.queue = [FakeResponse(200, _gemini_response("x"))]
    p = GeminiProvider(api_key="k", model="gemini-2.5-flash")
    _complete(p, thinking_budget=0)
    cfg = FakeAsyncClient.requests[0]["json"]["generationConfig"]
    assert cfg["thinkingConfig"] == {"thinkingBudget": 0}

    FakeAsyncClient.queue = [FakeResponse(200, _gemini_response("x"))]
    p_gemma = GeminiProvider(api_key="k", model="gemma-4-26b-a4b-it")
    _complete(p_gemma, thinking_budget=0)
    cfg = FakeAsyncClient.requests[1]["json"]["generationConfig"]
    assert cfg["thinkingConfig"] == {"thinkingBudget": 0}

    FakeAsyncClient.queue = [FakeResponse(200, _gemini_response("x"))]
    p_old = GeminiProvider(api_key="k", model="gemini-1.5-flash")
    _complete(p_old, thinking_budget=0)
    cfg = FakeAsyncClient.requests[2]["json"]["generationConfig"]
    assert "thinkingConfig" not in cfg


# --- retries and errors -----------------------------------------------------


def test_500_is_not_retried():
    FakeAsyncClient.queue = [
        FakeResponse(500, text="server exploded"),
        FakeResponse(200, _gemini_response("recovered")),
    ]
    p = GeminiProvider(api_key="k")
    with pytest.raises(LLMError) as exc:
        _complete(p)
    assert "unexpected error" in exc.value.user_message
    assert len(FakeAsyncClient.requests) == 1  # not retried


def test_retries_network_error_then_succeeds():
    FakeAsyncClient.queue = [
        httpx.ConnectError("boom"),
        FakeResponse(200, _gemini_response("recovered")),
    ]
    p = GeminiProvider(api_key="k")
    assert _complete(p) == "recovered"


def test_gives_up_after_max_attempts():
    FakeAsyncClient.queue = [FakeResponse(429, text="quota")] * 5
    p = GeminiProvider(api_key="k")
    with pytest.raises(LLMError) as exc:
        _complete(p)
    assert "busy" in exc.value.user_message
    assert len(FakeAsyncClient.requests) == 3  # 1 try + 2 retries, then stop


def test_invalid_key_is_not_retried():
    FakeAsyncClient.queue = [FakeResponse(403, text="API key not valid")]
    p = GeminiProvider(api_key="bad")
    with pytest.raises(LLMError) as exc:
        _complete(p)
    assert "API key" in exc.value.user_message
    assert len(FakeAsyncClient.requests) == 1


def test_missing_key_fails_fast_without_network():
    p = GeminiProvider(api_key="")
    with pytest.raises(LLMError) as exc:
        _complete(p)
    assert "No Gemini API key" in exc.value.user_message
    assert FakeAsyncClient.requests == []


def test_blocked_prompt_raises_friendly_error():
    FakeAsyncClient.queue = [
        FakeResponse(200, {"promptFeedback": {"blockReason": "SAFETY"}})
    ]
    p = GeminiProvider(api_key="k")
    with pytest.raises(LLMError) as exc:
        _complete(p)
    assert "rephras" in exc.value.user_message


def test_empty_candidates_raise():
    FakeAsyncClient.queue = [FakeResponse(200, {"candidates": []})]
    p = GeminiProvider(api_key="k")
    with pytest.raises(LLMError):
        _complete(p)


# --- health check -----------------------------------------------------------


def test_health_check_without_key():
    out = asyncio.run(GeminiProvider(api_key="").health_check())
    assert out["ok"] is False
    assert "key" in out["error"].lower()


def test_health_check_ok():
    FakeAsyncClient.queue = [FakeResponse(200, {"models": []})]
    out = asyncio.run(GeminiProvider(api_key="k").health_check())
    assert out["ok"] is True


# --- provider factory -------------------------------------------------------


def test_create_provider_builds_gemini():
    p = create_provider(
        {"provider": "gemini", "model": "", "api_keys": {"user-1": {"gemini": "k"}}},
        "user-1",
    )
    assert isinstance(p, GeminiProvider)
    assert p.model == DEFAULT_GEMINI_MODEL


def test_create_provider_rejects_unknown():
    with pytest.raises(ValueError):
        create_provider({"provider": "ollama", "api_keys": {}}, "user-1")


def test_provider_manager_caches_per_user_and_never_cross_leaks():
    cfg = {
        "provider": "gemini",
        "api_keys": {"user-1": {"gemini": "a"}, "user-2": {"gemini": "b"}},
    }
    mgr = ProviderManager(cfg)

    first = mgr.get("user-1")
    assert mgr.get("user-1") is first  # cached, same instance
    assert first.api_key == "a"

    second = mgr.get("user-2")
    assert second is not first
    assert second.api_key == "b"  # user-2 never sees user-1's key


def test_provider_manager_invalidate_rebuilds_one_user():
    cfg = {"provider": "gemini", "api_keys": {"user-1": {"gemini": "a"}}}
    mgr = ProviderManager(cfg)
    first = mgr.get("user-1")

    cfg["api_keys"]["user-1"]["gemini"] = "a2"
    mgr.invalidate("user-1")
    second = mgr.get("user-1")
    assert second is not first
    assert second.api_key == "a2"


def test_provider_manager_reconfigure_clears_all_users():
    mgr = ProviderManager(
        {"provider": "gemini", "api_keys": {"user-1": {"gemini": "a"}}}
    )
    first = mgr.get("user-1")
    mgr.reconfigure({"provider": "gemini", "api_keys": {"user-1": {"gemini": "b"}}})
    second = mgr.get("user-1")
    assert first is not second
    assert second.api_key == "b"


# --- table shortlist (two-stage linking) ------------------------------------


def test_shortlist_tables_filters_to_real_names_case_insensitively():
    class OneShotProvider:
        def __init__(self, reply):
            self.reply = reply
            self.system = None

        async def complete(self, system, user, json_mode=False, schema=None, **kw):
            self.system = system
            return self.reply

    schema = {
        "Orders": {"columns": [{"name": "id"}]},
        "products": {"columns": [{"name": "id"}]},
    }
    p = OneShotProvider('{"tables": ["orders", "PRODUCTS", "made_up_table"]}')
    out = asyncio.run(llm.shortlist_tables(p, "question?", schema))
    # canonical names returned; the invented table is dropped
    assert out == {"Orders", "products"}
    # the catalog listed every table with its columns
    assert "Orders(id)" in p.system and "products(id)" in p.system


# --- schema conversion ------------------------------------------------------


def test_to_gemini_schema_strips_unsupported_keys():
    out = to_gemini_schema(
        {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "a": {"type": "array", "items": {"type": "string"}, "minItems": 1}
            },
            "required": ["a"],
        }
    )
    assert "additionalProperties" not in out
    assert "minItems" not in out["properties"]["a"]
    assert out["properties"]["a"]["items"] == {"type": "string"}
