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


@patch("backend.app.llm.openai.AsyncOpenAI")
def test_complete_sends_correct_messages(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = type(
        "obj",
        (),
        {
            "choices": [
                type("obj", (), {"message": type("obj", (), {"content": "Hello"})()})()
            ],
            "usage": None,
        },
    )()

    p = OpenRouterProvider(api_key="sk-test")
    out = _complete(p)
    assert out == "Hello"
    mock_client.chat.completions.create.assert_called_once()
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["model"] == "openai/gpt-4o"
    assert kwargs["messages"][0]["role"] == "system"
    assert kwargs["messages"][0]["content"] == "system prompt"
    assert kwargs["messages"][1]["role"] == "user"
    assert kwargs["messages"][1]["content"] == "user prompt"


@patch("backend.app.llm.openai.AsyncOpenAI")
def test_complete_passes_json_schema(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = type(
        "obj",
        (),
        {
            "choices": [
                type("obj", (), {"message": type("obj", (), {"content": "{}"})()})()
            ],
            "usage": None,
        },
    )()

    p = OpenRouterProvider(api_key="sk-test")
    _complete(p, json_mode=True, schema=SQL_SCHEMA)
    kwargs = mock_client.chat.completions.create.call_args[1]
    assert kwargs["response_format"]["type"] == "json_schema"
    assert kwargs["response_format"]["json_schema"]["name"] == "sql_result"
    assert kwargs["response_format"]["json_schema"]["strict"] is True


@patch("backend.app.llm.openai.AsyncOpenAI")
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


@patch("backend.app.llm.openai.AsyncOpenAI")
def test_health_check_ok(mock_openai):
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.return_value = type(
        "obj",
        (),
        {
            "choices": [
                type("obj", (), {"message": type("obj", (), {"content": "ok"})()})()
            ],
            "usage": None,
        },
    )()

    p = OpenRouterProvider(api_key="sk-test")
    out = _health(p)
    assert out["ok"] is True


@patch("backend.app.llm.openai.AsyncOpenAI")
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
    assert p.model == "openai/gpt-4o"


def test_create_provider_rejects_missing_key():
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        create_provider({"openrouter_key": ""}, "user-1")
