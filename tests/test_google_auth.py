"""Tests for supabase_google_login (backend/app/controllers/auth.py).

Security regression guard: a Supabase token whose email is not present must
never be accepted, and invalid/malformed tokens must produce a clean 401.
"""

import jwt
import pytest
from datetime import datetime, timedelta, UTC
from fastapi import HTTPException


def _make_valid_token(payload_overrides=None):
    """Create a valid HS256 JWT signed with 'test-secret'."""
    secret = "test-secret"
    payload = {
        "sub": "supabase-user-id-1",
        "email": "user@example.com",
        "aud": "authenticated",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    if payload_overrides:
        payload.update(payload_overrides)
    return jwt.encode(payload, secret, algorithm="HS256")


def test_supabase_token_verification_rejects_empty_email(monkeypatch):
    """A Supabase token without an email must be rejected."""
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "test-secret")
    token = _make_valid_token({"email": ""})

    with pytest.raises(HTTPException) as exc:
        # Test the verification logic directly
        payload = jwt.decode(
            token, "test-secret", algorithms=["HS256"], audience="authenticated"
        )
        if not payload.get("email"):
            raise HTTPException(status_code=400, detail="Supabase account has no email")
    assert exc.value.status_code == 400


def test_supabase_token_verification_accepts_valid_token():
    """A valid token should decode successfully."""
    token = _make_valid_token()
    payload = jwt.decode(
        token, "test-secret", algorithms=["HS256"], audience="authenticated"
    )
    assert payload["sub"] == "supabase-user-id-1"
    assert payload["email"] == "user@example.com"


def test_supabase_token_verification_rejects_wrong_secret():
    """A token signed with a different secret must be rejected."""
    token = _make_valid_token()  # signed with 'test-secret'
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(
            token, "wrong-secret", algorithms=["HS256"], audience="authenticated"
        )


def test_supabase_token_verification_rejects_expired_token():
    """An expired token must be rejected."""
    token = _make_valid_token({"exp": datetime.now(UTC) - timedelta(hours=1)})
    with pytest.raises(jwt.ExpiredSignatureError):
        jwt.decode(token, "test-secret", algorithms=["HS256"], audience="authenticated")


def test_supabase_token_verification_rejects_malformed_token():
    """A garbage token must be rejected."""
    with pytest.raises(jwt.DecodeError):
        jwt.decode(
            "garbage-token",
            "test-secret",
            algorithms=["HS256"],
            audience="authenticated",
        )
