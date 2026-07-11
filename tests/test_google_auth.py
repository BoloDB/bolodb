"""Tests for google_login (backend/app/controllers/auth.py).

Security regression guard: a Google ID token whose email is not verified must
never be trusted for find-or-link, otherwise an unverified email matching an
existing password account would allow account takeover.
"""

import jwt
import pytest
from fastapi import HTTPException

import backend.app.controllers.auth as auth


class _FakeSigningKey:
    key = "fake-key"


class _FakeJWKClient:
    def __init__(self, *a, **k):
        pass

    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey()


def _patch_verification(monkeypatch, payload):
    monkeypatch.setattr(jwt, "PyJWKClient", _FakeJWKClient)
    monkeypatch.setattr(auth.jwt, "decode", lambda *a, **k: payload)


def test_google_login_rejects_unverified_email(monkeypatch):
    _patch_verification(
        monkeypatch,
        {"sub": "g-1", "email": "victim@example.com", "email_verified": False},
    )
    # would take over an existing account if this were allowed
    monkeypatch.setattr(auth, "get_user_by_google_id", lambda gid: None)
    monkeypatch.setattr(
        auth, "get_user_by_email", lambda e: {"_id": "existing", "role": "user"}
    )

    with pytest.raises(HTTPException) as exc:
        auth.google_login("token", "client-id")
    assert exc.value.status_code == 401


def test_google_login_creates_user_for_verified_email(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    _patch_verification(
        monkeypatch,
        {"sub": "g-2", "email": "new@example.com", "email_verified": True},
    )
    monkeypatch.setattr(auth, "get_user_by_google_id", lambda gid: None)
    monkeypatch.setattr(auth, "get_user_by_email", lambda e: None)

    class _Res:
        inserted_id = "uid-123"

    monkeypatch.setattr(auth, "create_user", lambda u: _Res())

    tokens = auth.google_login("token", "client-id")
    assert "access_token" in tokens
    assert "refresh_token" in tokens
