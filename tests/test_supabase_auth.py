"""Tests for supabase_google_login (backend/app/controllers/auth.py).

Security regression guard: a Supabase token whose email is not present must
never be accepted, invalid/malformed tokens must produce a clean 401, and
email linking must only happen when the provider is confirmed as Google
and the email is verified.
"""

import jwt
import pytest
from datetime import datetime, timedelta, UTC
from fastapi import HTTPException

import backend.app.controllers.auth as auth


def _make_valid_token(payload_overrides=None):
    """Create a valid HS256 JWT signed with 'test-secret'."""
    secret = "test-secret"
    payload = {
        "sub": "supabase-user-id-1",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "app_metadata": {"provider": "google", "providers": ["google"]},
        "user_metadata": {
            "email": "user@example.com",
            "email_verified": True,
        },
    }
    if payload_overrides:
        payload.update(payload_overrides)
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.mark.asyncio
async def test_rejects_empty_email(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    token = _make_valid_token({"email": ""})

    # Bypass DB calls — should fail before reaching them
    async def none(*a, **k):
        return None

    monkeypatch.setattr(auth, "get_user_by_supabase_id", none)
    monkeypatch.setattr(auth, "get_user_by_email", none)

    with pytest.raises(HTTPException) as exc:
        await auth.supabase_google_login(token)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_creates_user_for_valid_token(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    token = _make_valid_token({"sub": "supabase-new", "email": "new@example.com"})

    async def none(*a, **k):
        return None

    async def fake_create_user(u):
        return "uid-new"

    monkeypatch.setattr(auth, "get_user_by_supabase_id", none)
    monkeypatch.setattr(auth, "get_user_by_email", none)
    monkeypatch.setattr(auth, "create_user", fake_create_user)

    tokens = await auth.supabase_google_login(token)
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_links_existing_email_when_google_verified(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    token = _make_valid_token({"sub": "supabase-link", "email": "existing@example.com"})

    async def fake_get_by_supabase_id(sid):
        return None

    async def fake_get_by_email(e):
        return {"_id": "existing-id", "role": "user"}

    async def fake_update_user(uid, **kw):
        return None

    monkeypatch.setattr(auth, "get_user_by_supabase_id", fake_get_by_supabase_id)
    monkeypatch.setattr(auth, "get_user_by_email", fake_get_by_email)
    monkeypatch.setattr(auth, "update_user", fake_update_user)

    tokens = await auth.supabase_google_login(token)
    assert "access_token" in tokens
    assert "refresh_token" in tokens


@pytest.mark.asyncio
async def test_rejects_malformed_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")

    with pytest.raises(HTTPException) as exc:
        await auth.supabase_google_login("garbage-token")
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_wrong_secret(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "wrong-secret")
    token = _make_valid_token()

    with pytest.raises(HTTPException) as exc:
        await auth.supabase_google_login(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_rejects_expired_token(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    token = _make_valid_token({"exp": datetime.now(UTC) - timedelta(hours=1)})

    with pytest.raises(HTTPException) as exc:
        await auth.supabase_google_login(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_skips_linking_for_non_google_provider(monkeypatch):
    """Email linking must not happen when the provider is not Google."""
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    token = _make_valid_token(
        {
            "sub": "supabase-nolink",
            "email": "existing@example.com",
            "app_metadata": {"provider": "github"},
            "user_metadata": {"email_verified": True},
        }
    )

    update_called = []

    async def fake_get_by_supabase_id(sid):
        return None

    async def fake_get_by_email(e):
        return None  # pretend no existing account

    async def fake_create_user(u):
        return "uid-new"

    async def fake_update_user(uid, **kw):
        update_called.append((uid, kw))

    monkeypatch.setattr(auth, "get_user_by_supabase_id", fake_get_by_supabase_id)
    monkeypatch.setattr(auth, "get_user_by_email", fake_get_by_email)
    monkeypatch.setattr(auth, "create_user", fake_create_user)
    monkeypatch.setattr(auth, "update_user", fake_update_user)

    tokens = await auth.supabase_google_login(token)
    assert "access_token" in tokens
    assert len(update_called) == 0  # linking was skipped
