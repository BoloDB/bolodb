"""Every JWT this app issues must only work where it was meant to.

All of them are signed with the same secret and carry a ``user_id``, so a valid
signature says "we minted this" and nothing more. Before the ``typ`` claim the
consumers could not tell them apart, which made a 7-day refresh token, an emailed
password-reset token and a Slack OAuth state each a working session cookie.
"""

import jwt
import pytest
from fastapi import HTTPException

from backend.app import tokens
from backend.app.controllers.auth import (
    create_access_jwt,
    create_jwt,
    reset_password,
)
from backend.app.dependencies import get_current_user

SECRET = "test-jwt-secret-that-is-long-enough-for-hs256"
USER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)


def _encode(claims):
    return jwt.encode(claims, SECRET, algorithm="HS256")


# ── what get_current_user accepts ────────────────────────────────────────


@pytest.mark.asyncio
async def test_access_token_is_accepted():
    pair = create_jwt(USER_ID, "user")
    assert (await get_current_user(pair["access_token"]))["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_create_access_jwt_is_accepted():
    """The token /refresh hands back has to be usable as a session."""
    assert (await get_current_user(create_access_jwt(USER_ID, "user")))[
        "user_id"
    ] == USER_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind",
    [tokens.REFRESH, tokens.PASSWORD_RESET, tokens.SLACK_OAUTH_STATE, "made-up"],
)
async def test_other_kinds_are_not_sessions(kind):
    token = _encode({"user_id": USER_ID, "role": "user", tokens.TYPE_CLAIM: kind})
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_token_from_login_is_not_a_session():
    """The headline case: both halves of the pair used to be interchangeable.

    While they were, the one-hour access lifetime bought nothing — the 7-day
    refresh token opened exactly the same doors.
    """
    pair = create_jwt(USER_ID, "user")
    with pytest.raises(HTTPException) as exc:
        await get_current_user(pair["refresh_token"])
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_untyped_token_is_rejected():
    """Tokens minted before the claim existed are refused, not grandfathered.

    They are indistinguishable from one another, which is the whole problem, and
    they are the ones already in circulation — so accepting them would leave the
    hole open for exactly the population that matters. Everyone signs in once.
    """
    with pytest.raises(HTTPException) as exc:
        await get_current_user(_encode({"user_id": USER_ID, "role": "user"}))
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_a_signature_alone_is_not_enough():
    """Signed by us, but never issued as a session — still refused."""
    forged = _encode({"user_id": USER_ID, "role": "owner", "workspace_id": "w"})
    with pytest.raises(HTTPException):
        await get_current_user(forged)


# ── what the tokens themselves claim ─────────────────────────────────────


def test_login_pair_names_each_half():
    pair = create_jwt(USER_ID, "user")
    access = jwt.decode(pair["access_token"], SECRET, algorithms=["HS256"])
    refresh = jwt.decode(pair["refresh_token"], SECRET, algorithms=["HS256"])
    assert access[tokens.TYPE_CLAIM] == tokens.ACCESS
    assert refresh[tokens.TYPE_CLAIM] == tokens.REFRESH
    # The pair differed only by `exp` before, which is what made them swappable.
    assert access[tokens.TYPE_CLAIM] != refresh[tokens.TYPE_CLAIM]


# ── the refresh endpoint ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_accepts_a_refresh_token():
    from backend.app.routes.auth import refresh_jwt

    pair = create_jwt(USER_ID, "user")
    assert (await refresh_jwt(pair["refresh_token"])).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [tokens.ACCESS, tokens.SLACK_OAUTH_STATE, None])
async def test_refresh_refuses_anything_else(kind):
    """An access token renewing itself here would never have to expire."""
    from backend.app.routes.auth import refresh_jwt

    claims = {"user_id": USER_ID, "role": "user"}
    if kind is not None:
        claims[tokens.TYPE_CLAIM] = kind
    with pytest.raises(HTTPException) as exc:
        await refresh_jwt(_encode(claims))
    assert exc.value.status_code == 401


# ── reset links ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [tokens.ACCESS, tokens.REFRESH, None])
async def test_only_a_reset_token_resets_a_password(kind):
    claims = {"user_id": USER_ID, "jti": "x"}
    if kind is not None:
        claims[tokens.TYPE_CLAIM] = kind
    with pytest.raises(HTTPException) as exc:
        await reset_password(_encode(claims), "N3w-passw0rd!x")
    assert exc.value.status_code == 400
