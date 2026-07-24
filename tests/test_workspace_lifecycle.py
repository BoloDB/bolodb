"""Tests for the workspace lifecycle controllers added alongside delete/leave
and invite management: ``delete_workspace``, ``leave_workspace``,
``list_pending_invites``, ``rescind_invite`` and ``resend_invite``.

The DB is mocked with the same session-factory pattern used by
``test_pgdatabase_users.py`` — ``async_session`` is a plain sync callable that
returns an AsyncSession, so the factory must be a ``Mock``, not an ``AsyncMock``.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import backend.app.controllers.workspaces as ctrl

WORKSPACE_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
INVITE_ID = str(uuid.uuid4())


def _patch_session(monkeypatch, session):
    factory = Mock()
    factory.return_value = session
    session.__aenter__.return_value = session
    monkeypatch.setattr(ctrl, "async_session", factory)
    return factory


@pytest.fixture(autouse=True)
def _silence_side_effects(monkeypatch):
    """Activity logging and email both open their own connections."""
    monkeypatch.setattr(ctrl, "log_activity", AsyncMock())
    monkeypatch.setattr(
        ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
    )


def _result(value):
    result = Mock()
    result.scalar_one_or_none.return_value = value
    return result


def _member(role="member"):
    return SimpleNamespace(
        workspace_id=uuid.UUID(WORKSPACE_ID), user_id=uuid.UUID(USER_ID), role=role
    )


def _invite(expires_in_days=3, accepted_at=None):
    return SimpleNamespace(
        id=uuid.UUID(INVITE_ID),
        workspace_id=uuid.UUID(WORKSPACE_ID),
        email="new@example.com",
        role="member",
        token="BOLO-TEST-TOKEN",
        accepted_at=accepted_at,
        expires_at=datetime.now(timezone.utc) + timedelta(days=expires_in_days),
    )


# ── delete_workspace ──


@pytest.mark.asyncio
async def test_delete_workspace_removes_the_row(monkeypatch):
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(id=WORKSPACE_ID, name="Acme")
    _patch_session(monkeypatch, session)

    assert await ctrl.delete_workspace(WORKSPACE_ID, USER_ID) == {"ok": True}
    # Deleting the single workspaces row is the whole operation — every
    # workspace-scoped table cascades from it.
    session.delete.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_workspace_404s_when_missing(monkeypatch):
    session = AsyncMock()
    session.get.return_value = None
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.delete_workspace(WORKSPACE_ID, USER_ID)
    assert exc.value.status_code == 404
    session.delete.assert_not_awaited()


# ── leave_workspace ──


@pytest.mark.asyncio
async def test_leave_workspace_removes_a_plain_member(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(_member("member"))
    _patch_session(monkeypatch, session)

    assert await ctrl.leave_workspace(WORKSPACE_ID, USER_ID) == {"ok": True}
    session.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_sole_owner_cannot_leave(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(_member("owner"))
    session.scalar.return_value = 1
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.leave_workspace(WORKSPACE_ID, USER_ID)
    assert exc.value.status_code == 400
    session.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_owner_can_leave_when_another_owner_remains(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(_member("owner"))
    session.scalar.return_value = 2
    _patch_session(monkeypatch, session)

    assert await ctrl.leave_workspace(WORKSPACE_ID, USER_ID) == {"ok": True}
    session.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_leave_workspace_404s_for_non_member(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(None)
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.leave_workspace(WORKSPACE_ID, USER_ID)
    assert exc.value.status_code == 404


# ── list_pending_invites ──


@pytest.mark.asyncio
async def test_list_pending_invites_shape(monkeypatch):
    invite = _invite()
    session = AsyncMock()
    result = Mock()
    result.all.return_value = [(invite, "admin@example.com")]
    session.execute.return_value = result
    _patch_session(monkeypatch, session)

    rows = await ctrl.list_pending_invites(WORKSPACE_ID)
    assert rows == [
        {
            "id": INVITE_ID,
            "email": "new@example.com",
            "role": "member",
            "invited_by": "admin@example.com",
            "expires_at": invite.expires_at,
        }
    ]
    # The token is deliberately absent — listing invites must not leak codes
    # that would let an admin join as someone else.
    assert "token" not in rows[0]


# ── rescind_invite ──


@pytest.mark.asyncio
async def test_rescind_invite_deletes_the_row(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(_invite())
    _patch_session(monkeypatch, session)

    assert await ctrl.rescind_invite(WORKSPACE_ID, INVITE_ID, USER_ID) == {"ok": True}
    session.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_rescind_invite_rejects_an_accepted_invite(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(
        _invite(accepted_at=datetime.now(timezone.utc))
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.rescind_invite(WORKSPACE_ID, INVITE_ID, USER_ID)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_rescind_invite_404s_on_unknown_id(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(None)
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.rescind_invite(WORKSPACE_ID, INVITE_ID, USER_ID)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rescind_invite_404s_on_malformed_id(monkeypatch):
    """A non-UUID path segment is a missing invite, not a 500."""
    session = AsyncMock()
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.rescind_invite(WORKSPACE_ID, "not-a-uuid", USER_ID)
    assert exc.value.status_code == 404


# ── resend_invite ──


@pytest.mark.asyncio
async def test_resend_invite_keeps_a_live_token_and_extends_expiry(monkeypatch):
    invite = _invite(expires_in_days=3)
    original_token = invite.token
    original_expiry = invite.expires_at
    session = AsyncMock()
    session.execute.return_value = _result(invite)
    session.get.return_value = SimpleNamespace(name="Acme")
    _patch_session(monkeypatch, session)

    res = await ctrl.resend_invite(WORKSPACE_ID, INVITE_ID, USER_ID)

    assert res["ok"] is True
    assert res["email_sent"] is True
    # Codes already in someone's inbox must keep working.
    assert invite.token == original_token
    assert invite.expires_at > original_expiry
    ctrl.send_workspace_invite_email.assert_awaited_once_with(
        "new@example.com", "Acme", original_token
    )


@pytest.mark.asyncio
async def test_resend_invite_regenerates_an_expired_token(monkeypatch):
    invite = _invite(expires_in_days=-1)
    original_token = invite.token
    session = AsyncMock()
    session.execute.return_value = _result(invite)
    session.get.return_value = SimpleNamespace(name="Acme")
    _patch_session(monkeypatch, session)

    await ctrl.resend_invite(WORKSPACE_ID, INVITE_ID, USER_ID)

    assert invite.token != original_token
    assert invite.expires_at > datetime.now(timezone.utc)


@pytest.mark.asyncio
async def test_resend_invite_reports_when_email_is_not_configured(monkeypatch):
    monkeypatch.setattr(
        ctrl, "send_workspace_invite_email", AsyncMock(return_value=False)
    )
    session = AsyncMock()
    session.execute.return_value = _result(_invite())
    session.get.return_value = SimpleNamespace(name="Acme")
    _patch_session(monkeypatch, session)

    res = await ctrl.resend_invite(WORKSPACE_ID, INVITE_ID, USER_ID)
    assert res["ok"] is True
    assert res["email_sent"] is False


@pytest.mark.asyncio
async def test_resend_invite_rejects_an_accepted_invite(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(
        _invite(accepted_at=datetime.now(timezone.utc))
    )
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.resend_invite(WORKSPACE_ID, INVITE_ID, USER_ID)
    assert exc.value.status_code == 400
    ctrl.send_workspace_invite_email.assert_not_awaited()


# ── transfer_ownership ──


def _members_result(*members):
    result = Mock()
    scalars = Mock()
    scalars.all.return_value = list(members)
    result.scalars.return_value = scalars
    return result


@pytest.mark.asyncio
async def test_transfer_ownership_promotes_target_and_demotes_actor(monkeypatch):
    target_id = str(uuid.uuid4())
    actor = _member("owner")
    target = SimpleNamespace(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        user_id=uuid.UUID(target_id),
        role="member",
    )
    session = AsyncMock()
    session.execute.return_value = _members_result(actor, target)
    _patch_session(monkeypatch, session)

    res = await ctrl.transfer_ownership(WORKSPACE_ID, USER_ID, target_id)

    assert res == {"ok": True, "new_owner_id": target_id}
    # Both sides move in the same transaction, so the workspace is never left
    # with two owners or none.
    assert target.role == "owner"
    assert actor.role == "admin"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_transfer_ownership_rejects_self(monkeypatch):
    session = AsyncMock()
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.transfer_ownership(WORKSPACE_ID, USER_ID, USER_ID)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_transfer_ownership_404s_when_target_is_not_a_member(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _members_result(_member("owner"))
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.transfer_ownership(WORKSPACE_ID, USER_ID, str(uuid.uuid4()))
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_transfer_ownership_403s_when_actor_is_not_owner(monkeypatch):
    target_id = str(uuid.uuid4())
    actor = _member("admin")
    target = SimpleNamespace(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        user_id=uuid.UUID(target_id),
        role="member",
    )
    session = AsyncMock()
    session.execute.return_value = _members_result(actor, target)
    _patch_session(monkeypatch, session)

    with pytest.raises(HTTPException) as exc:
        await ctrl.transfer_ownership(WORKSPACE_ID, USER_ID, target_id)
    assert exc.value.status_code == 403
    assert target.role == "member"


# ── bulk_invite ──


@pytest.mark.asyncio
async def test_bulk_invite_reports_a_status_per_address(monkeypatch):
    async def fake_invite_user(workspace_id, email, role, inviter_id):
        if email == "taken@example.com":
            raise HTTPException(400, "User is already a member")
        return {"email": email}

    monkeypatch.setattr(ctrl, "invite_user", fake_invite_user)

    res = await ctrl.bulk_invite(
        WORKSPACE_ID,
        ["  New@Example.com ", "taken@example.com", "not-an-email", "new@example.com"],
        "member",
        USER_ID,
    )

    assert res["total"] == 4
    assert res["invited"] == 1
    assert [r["status"] for r in res["results"]] == [
        "invited",
        "already_member",
        "invalid",
        "duplicate",
    ]
    # Addresses are normalised, so casing and stray spaces don't create dupes.
    assert res["results"][0]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_bulk_invite_continues_past_an_unexpected_failure(monkeypatch):
    async def fake_invite_user(workspace_id, email, role, inviter_id):
        if email == "boom@example.com":
            raise HTTPException(400, "Could not process invite")
        return {"email": email}

    monkeypatch.setattr(ctrl, "invite_user", fake_invite_user)

    res = await ctrl.bulk_invite(
        WORKSPACE_ID, ["boom@example.com", "ok@example.com"], "member", USER_ID
    )
    assert [r["status"] for r in res["results"]] == ["failed", "invited"]
    assert res["invited"] == 1


@pytest.mark.asyncio
async def test_bulk_invite_rejects_an_invalid_role(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        await ctrl.bulk_invite(WORKSPACE_ID, ["a@b.com"], "owner", USER_ID)
    assert exc.value.status_code == 400
