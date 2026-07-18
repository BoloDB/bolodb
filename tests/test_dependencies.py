"""Tests for backend/app/dependencies.py.

``get_kb`` was repointed from ``app.state.kb`` (the old SQLite
``KnowledgeBase``) to ``app.state.kbs`` (the new async, PostgreSQL-backed
``KnowledgeService``) as part of the knowledge-to-postgres migration.
"""

from types import SimpleNamespace

from backend.app.dependencies import (
    get_cfg,
    get_db,
    get_kb,
    get_providers,
    get_session_log,
)


def _fake_request(**state_kwargs):
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(**state_kwargs)))


def test_get_kb_returns_app_state_kbs():
    sentinel = object()
    request = _fake_request(kbs=sentinel)
    assert get_kb(request) is sentinel


def test_get_kb_does_not_read_legacy_kb_attribute():
    """Regression guard: get_kb must read `kbs`, not the retired `kb` attribute."""
    request = _fake_request(kbs="new-service", kb="old-service")
    assert get_kb(request) == "new-service"


def test_get_db_returns_app_state_db():
    sentinel = object()
    request = _fake_request(db=sentinel)
    assert get_db(request) is sentinel


def test_get_providers_returns_app_state_providers():
    sentinel = object()
    request = _fake_request(providers=sentinel)
    assert get_providers(request) is sentinel


def test_get_session_log_returns_app_state_session_log():
    sentinel = object()
    request = _fake_request(session_log=sentinel)
    assert get_session_log(request) is sentinel


def test_get_cfg_returns_app_state_cfg():
    sentinel = object()
    request = _fake_request(cfg=sentinel)
    assert get_cfg(request) is sentinel
