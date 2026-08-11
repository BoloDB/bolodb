"""Changing a password must end the sessions that existed before it.

There was no server-side session state at all, so a token outlived the password
it was obtained with. Someone who suspected their account was compromised could
change their password and the attacker would keep working for up to seven days —
the app had no way to eject anyone.
"""

import jwt
import pytest
from fastapi import HTTPException

import backend.app.dependencies as deps
from backend.app import tokens
from backend.app.controllers.auth import create_jwt

SECRET = "test-jwt-secret-that-is-long-enough-for-hs256"
USER_ID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def jwt_secret(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SECRET)


@pytest.fixture
def stored_version(monkeypatch):
    """Stands in for users.token_version, settable per test."""
    box = {"value": 0}

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def scalar(self, _stmt):
            return box["value"]

    monkeypatch.setattr(deps, "async_session", lambda: _Session())
    return box


@pytest.mark.asyncio
async def test_a_token_from_the_current_generation_works(stored_version):
    pair = create_jwt(USER_ID, "user", token_version=0)
    assert (await deps.get_current_user(pair["access_token"]))["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_changing_the_password_ends_an_existing_session(stored_version):
    """The headline case, in the order it actually happens."""
    pair = create_jwt(USER_ID, "user", token_version=0)
    assert await deps.get_current_user(pair["access_token"])  # attacker is in

    stored_version["value"] = 1  # victim changes their password

    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(pair["access_token"])
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_a_token_minted_after_the_change_still_works(stored_version):
    """Revocation must retire the old generation, not lock the account."""
    stored_version["value"] = 1
    pair = create_jwt(USER_ID, "user", token_version=1)
    assert await deps.get_current_user(pair["access_token"])


@pytest.mark.asyncio
async def test_a_stale_refresh_token_cannot_mint_a_fresh_session(stored_version):
    """Otherwise /refresh quietly undoes the revocation.

    The refresh token is the long-lived half — leaving this endpoint unchecked
    would hand a revoked holder a brand-new valid access token for another week.
    """
    import backend.app.routes.auth as auth_routes

    pair = create_jwt(USER_ID, "user", token_version=0)
    stored_version["value"] = 1

    with pytest.raises(HTTPException) as exc:
        await auth_routes.refresh_jwt(pair["refresh_token"])
    assert exc.value.status_code == 401


@pytest.fixture
def changed_password(monkeypatch, stored_version):
    """Drive the real change-password flow with the DB write stubbed out.

    The stub bumps the same box ``stored_version`` reads, so a token this flow
    hands back is checked against the version its own revocation landed on.
    """
    import backend.app.controllers.auth as auth_ctl

    async def _get_user(_user_id):
        return {"id": USER_ID, "hashed_pass": "stored-hash", "role": "user"}

    async def _verify(plain, _hashed):
        return plain == "old-password"

    async def _hash(_plain):
        return "new-hash"

    async def _set_and_revoke(_user_id, _hashed):
        stored_version["value"] += 1
        return stored_version["value"]

    monkeypatch.setattr(auth_ctl, "get_user_by_id", _get_user)
    monkeypatch.setattr(auth_ctl, "verify_password", _verify)
    monkeypatch.setattr(auth_ctl, "hash_password", _hash)
    monkeypatch.setattr(auth_ctl, "validate_password_strength", lambda _p: None)
    monkeypatch.setattr(auth_ctl, "set_password_and_revoke_sessions", _set_and_revoke)
    return auth_ctl


@pytest.mark.asyncio
async def test_changing_your_own_password_does_not_sign_you_out(changed_password):
    """The revocation is indiscriminate, so the caller is one of its casualties.

    Returning 200 without new cookies logs the person out by their own request:
    every later call 401s and there is no way back, because /refresh checks the
    version too and the refresh token died with the access token.
    """
    import backend.app.routes.auth as auth_routes

    old = create_jwt(USER_ID, "user", token_version=0)
    assert await deps.get_current_user(old["access_token"])  # signed in before

    req = auth_routes.ChangePasswordReq(
        old_password="old-password", new_password="new-password"
    )
    response = await auth_routes.change_password(req, {"user_id": USER_ID})

    assert response.status_code == 200
    cookies = response.headers.getlist("set-cookie")
    issued = {
        name: value
        for name, _, value in (c.split(";")[0].partition("=") for c in cookies)
    }
    assert "access_token" in issued and "refresh_token" in issued

    # The old pair is gone...
    with pytest.raises(HTTPException):
        await deps.get_current_user(old["access_token"])
    # ...and the pair handed back in its place is a working session.
    assert (await deps.get_current_user(issued["access_token"]))["user_id"] == USER_ID


@pytest.mark.asyncio
async def test_the_replacement_refresh_token_can_still_renew(changed_password):
    """Half a fix is no fix: a dead refresh token means a one-hour account."""
    import backend.app.routes.auth as auth_routes

    req = auth_routes.ChangePasswordReq(
        old_password="old-password", new_password="new-password"
    )
    response = await auth_routes.change_password(req, {"user_id": USER_ID})
    cookies = response.headers.getlist("set-cookie")
    issued = {
        name: value
        for name, _, value in (c.split(";")[0].partition("=") for c in cookies)
    }

    async def _get_me(_user_id):
        return {"id": USER_ID, "email_verified": True}

    changed_password.get_me = _get_me
    renewed = await auth_routes.refresh_jwt(issued["refresh_token"])
    assert renewed.status_code == 200


@pytest.mark.asyncio
async def test_a_wrong_current_password_changes_nothing(changed_password):
    """The revocation must not fire before the old password is proven."""
    import backend.app.routes.auth as auth_routes

    req = auth_routes.ChangePasswordReq(
        old_password="not-the-password", new_password="new-password"
    )
    with pytest.raises(HTTPException) as exc:
        await auth_routes.change_password(req, {"user_id": USER_ID})
    assert exc.value.status_code == 401

    old = create_jwt(USER_ID, "user", token_version=0)
    assert await deps.get_current_user(old["access_token"])  # still signed in


@pytest.mark.asyncio
async def test_a_token_predating_the_claim_is_not_revoked(stored_version):
    """Absent reads as 0 — the generation every user starts at.

    Adding the column must not itself sign anyone out; only a real revocation
    should.
    """
    legacy = jwt.encode(
        {"user_id": USER_ID, "role": "user", tokens.TYPE_CLAIM: tokens.ACCESS},
        SECRET,
        algorithm="HS256",
    )
    assert await deps.get_current_user(legacy)


@pytest.mark.asyncio
async def test_a_token_for_a_deleted_account_is_not_a_session(monkeypatch):
    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def scalar(self, _stmt):
            return None

    monkeypatch.setattr(deps, "async_session", lambda: _Session())
    pair = create_jwt(USER_ID, "user", token_version=0)
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(pair["access_token"])
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_a_malformed_subject_is_refused(stored_version):
    bad = jwt.encode(
        {"user_id": "not-a-uuid", "role": "user", tokens.TYPE_CLAIM: tokens.ACCESS},
        SECRET,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        await deps.get_current_user(bad)


def test_password_and_revocation_land_in_one_transaction():
    """Both or neither.

    As two separate awaits, a failure in between leaves the password changed and
    the old sessions alive — the worst outcome available, because the user has
    been told their account is secured and it is not. In the reset flow the
    token is already consumed by then, so they cannot even retry the link.
    """
    import inspect

    from backend.app.controllers import auth
    from backend.app.pgdatabase.users import set_password_and_revoke_sessions

    source = inspect.getsource(set_password_and_revoke_sessions)
    assert "hashed_pass=hashed_pass" in source
    assert "token_version=User.token_version + 1" in source
    # One execute, one commit — not two statements hoping both land.
    assert source.count("await session.commit()") == 1

    for flow in (auth.change_password, auth.reset_password):
        body = inspect.getsource(flow)
        assert "set_password_and_revoke_sessions" in body, flow.__name__
        assert "bump_token_version" not in body, flow.__name__


def test_the_version_is_bumped_in_sql_not_read_modify_write():
    """Two concurrent revocations must not settle on the same number.

    A read-then-write would let the second overwrite the first with a value the
    first had already issued tokens against.
    """
    import inspect

    from backend.app.pgdatabase.users import bump_token_version

    source = inspect.getsource(bump_token_version)
    assert "User.token_version + 1" in source
