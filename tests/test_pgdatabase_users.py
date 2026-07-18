"""Tests for backend/app/pgdatabase/users.py covering the ``tour_completed``
additions: it must round-trip through ``_user_to_dict``/``get_user_by_id``
and be accepted (not blocked) by ``update_user``'s field allowlist.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import backend.app.pgdatabase.users as users_mod

USER_ID = str(uuid.uuid4())


def _fake_user(**overrides):
    defaults = dict(
        id=uuid.UUID(USER_ID),
        email="a@b.com",
        hashed_pass="hash",
        role="user",
        google_id=None,
        supabase_id=None,
        email_verified=False,
        tour_completed=False,
        created_at=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _patch_session(monkeypatch, session):
    # `async_session` (backend/app/pgdatabase/engine.py) is a plain sync
    # callable that returns an AsyncSession; only entering/exiting the
    # session itself is async. So the factory must be a plain Mock, not an
    # AsyncMock (which would make `async_session()` return an unawaited
    # coroutine instead of the session).
    factory = Mock()
    factory.return_value = session
    session.__aenter__.return_value = session
    monkeypatch.setattr(users_mod, "async_session", factory)
    return factory


@pytest.mark.asyncio
async def test_get_user_by_id_includes_tour_completed_true(monkeypatch):
    session = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = _fake_user(tour_completed=True)
    session.execute.return_value = result
    _patch_session(monkeypatch, session)

    user = await users_mod.get_user_by_id(USER_ID)
    assert user["tour_completed"] is True


@pytest.mark.asyncio
async def test_get_user_by_id_includes_tour_completed_false_by_default(monkeypatch):
    session = AsyncMock()
    result = Mock()
    result.scalar_one_or_none.return_value = _fake_user(tour_completed=False)
    session.execute.return_value = result
    _patch_session(monkeypatch, session)

    user = await users_mod.get_user_by_id(USER_ID)
    assert user["tour_completed"] is False


def test_allowed_user_fields_includes_tour_completed():
    assert "tour_completed" in users_mod._ALLOWED_USER_FIELDS


@pytest.mark.asyncio
async def test_update_user_allows_tour_completed(monkeypatch):
    session = AsyncMock()
    exec_result = AsyncMock()
    exec_result.rowcount = 1
    session.execute.return_value = exec_result
    _patch_session(monkeypatch, session)

    ok = await users_mod.update_user(USER_ID, tour_completed=True)
    assert ok is True
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_user_rejects_disallowed_field_without_touching_db(monkeypatch):
    session = AsyncMock()
    factory = _patch_session(monkeypatch, session)

    ok = await users_mod.update_user(USER_ID, tour_completed=True, is_admin=True)
    assert ok is False
    factory.assert_not_called()
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_update_user_invalid_uuid_returns_false(monkeypatch):
    session = AsyncMock()
    factory = _patch_session(monkeypatch, session)

    ok = await users_mod.update_user("not-a-uuid", tour_completed=True)
    assert ok is False
    factory.assert_not_called()
