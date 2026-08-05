"""Signing in must require the address to have been proven.

Signup sends a code, but nothing ever required it, so an account could be used
on an address its owner never agreed to. That is the ingredient account
pre-hijacking needs: register victim@corp.com, never verify, wait for the real
owner to sign in with Google, and `supabase_google_login` links their identity
into the account already standing — whose password the registrant still knows.
"""

import pytest
from fastapi import HTTPException

import backend.app.controllers.auth as auth

EMAIL = "victim@corp.com"
PASSWORD = "correct-horse-battery-staple"


def _user(**over):
    base = {
        "_id": "11111111-1111-1111-1111-111111111111",
        "email": EMAIL,
        "hashed_pass": "not-checked-here",
        "role": "user",
        "email_verified": True,
    }
    base.update(over)
    return base


@pytest.fixture(autouse=True)
def wiring(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret-long-enough-for-hs256-please")
    monkeypatch.setattr(auth, "verify_password", _password_matches)


async def _password_matches(password, _hashed):
    return password == PASSWORD


def _returns(user):
    async def _get(_email):
        return user

    return _get


@pytest.mark.asyncio
async def test_verified_user_can_sign_in(monkeypatch):
    monkeypatch.setattr(auth, "get_user_by_email", _returns(_user()))
    assert "access_token" in await auth.login(EMAIL, PASSWORD)


@pytest.mark.asyncio
@pytest.mark.parametrize("value", [False, None])
async def test_unverified_user_cannot_sign_in(monkeypatch, value):
    monkeypatch.setattr(
        auth, "get_user_by_email", _returns(_user(email_verified=value))
    )
    with pytest.raises(HTTPException) as exc:
        await auth.login(EMAIL, PASSWORD)
    assert exc.value.status_code == 403
    assert "verify" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_missing_flag_is_treated_as_unverified(monkeypatch):
    """Absent must fail closed — an older row without the key is not proof."""
    user = _user()
    del user["email_verified"]
    monkeypatch.setattr(auth, "get_user_by_email", _returns(user))
    with pytest.raises(HTTPException) as exc:
        await auth.login(EMAIL, PASSWORD)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_wrong_password_on_an_unverified_account_says_nothing_new(monkeypatch):
    """Verification state is only disclosed to someone who proved the password.

    Otherwise the 403 becomes an oracle for which addresses are registered.
    """
    monkeypatch.setattr(
        auth, "get_user_by_email", _returns(_user(email_verified=False))
    )
    with pytest.raises(HTTPException) as exc:
        await auth.login(EMAIL, "wrong-password")
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid credentials"


@pytest.mark.asyncio
async def test_unknown_account_is_unchanged(monkeypatch):
    monkeypatch.setattr(auth, "get_user_by_email", _returns(None))
    with pytest.raises(HTTPException) as exc:
        await auth.login(EMAIL, PASSWORD)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_social_only_account_is_unchanged(monkeypatch):
    """No password hash means no password login, verified or not."""
    monkeypatch.setattr(auth, "get_user_by_email", _returns(_user(hashed_pass=None)))
    with pytest.raises(HTTPException) as exc:
        await auth.login(EMAIL, PASSWORD)
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid credentials"


# ── the refresh endpoint ─────────────────────────────────────────────────


def _refresh_token_for(user_id="11111111-1111-1111-1111-111111111111"):
    import jwt

    from backend.app.secrets import get_jwt_secret

    return jwt.encode(
        {"user_id": user_id, "role": "user"}, get_jwt_secret(), algorithm="HS256"
    )


@pytest.mark.asyncio
async def test_refresh_refuses_an_unverified_account(monkeypatch):
    """Checking only at login leaves a week-long way around it.

    A refresh token issued before the rule existed would keep minting access
    tokens and never meet the login path again.
    """
    import backend.app.routes.auth as routes

    async def _get_me(_uid):
        return _user(email_verified=False)

    monkeypatch.setattr(routes.backend.app.controllers.auth, "get_me", _get_me)
    with pytest.raises(HTTPException) as exc:
        await routes.refresh_jwt(_refresh_token_for())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_still_works_for_a_verified_account(monkeypatch):
    import backend.app.routes.auth as routes

    async def _get_me(_uid):
        return _user()

    monkeypatch.setattr(routes.backend.app.controllers.auth, "get_me", _get_me)
    assert (await routes.refresh_jwt(_refresh_token_for())).status_code == 200
