"""Empirical verification test suite for Workspace Defaults integration.

Tests cover:
1. Invite creation and resending using `default_invite_role` and `invite_expiry_days`.
2. Activity log retention filtering using `activity_retention_days`.
3. Fallbacks when WorkspaceSettings is missing.
4. Edge cases, boundary timestamps, precedence rules, and dynamic updates.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import backend.app.controllers.workspaces as ws_ctrl
import backend.app.controllers.activity as activity_ctrl
from backend.app.models.workspace_settings import WorkspaceSettings


WORKSPACE_ID = str(uuid.uuid4())
INVITER_ID = str(uuid.uuid4())
MEMBER_USER_ID = str(uuid.uuid4())


def _result(value):
    res = Mock(name="QueryResult")
    res.scalar_one_or_none = Mock(return_value=value)
    return res


def _patch_session(monkeypatch, session, target_module=ws_ctrl):
    factory = Mock()
    factory.return_value = session
    session.__aenter__.return_value = session
    monkeypatch.setattr(target_module, "async_session", factory)
    return factory


@pytest.fixture(autouse=True)
def _silence_side_effects(monkeypatch):
    monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
    monkeypatch.setattr(
        ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
    )


# =====================================================================
# 1. INVITE CREATION & RESENDING WORKSPACE DEFAULTS TESTS
# =====================================================================


@pytest.mark.asyncio
async def test_invite_user_uses_custom_default_invite_role(monkeypatch):
    """When role is None, invite_user must default to settings.default_invite_role."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        default_invite_role="admin",
        invite_expiry_days=7,
    )
    session = AsyncMock()

    res_settings = _result(settings)
    res_user = _result(None)
    res_member = _result(None)
    res_invite = _result(None)

    session.execute.side_effect = [res_settings, res_user, res_member, res_invite]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    invite = await ws_ctrl.invite_user(
        WORKSPACE_ID, "new_admin@example.com", role=None, inviter_id=INVITER_ID
    )

    assert invite["role"] == "admin"
    assert invite["email"] == "new_admin@example.com"


@pytest.mark.asyncio
async def test_invite_user_explicit_role_overrides_workspace_default(monkeypatch):
    """Explicit role parameter must override default_invite_role in WorkspaceSettings."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        default_invite_role="admin",
        invite_expiry_days=7,
    )
    session = AsyncMock()

    res_settings = _result(settings)
    res_user = _result(None)
    res_member = _result(None)
    res_invite = _result(None)

    session.execute.side_effect = [res_settings, res_user, res_member, res_invite]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    invite = await ws_ctrl.invite_user(
        WORKSPACE_ID,
        "explicit_member@example.com",
        role="member",
        inviter_id=INVITER_ID,
    )

    assert invite["role"] == "member"


@pytest.mark.asyncio
async def test_invite_user_custom_expiry_days_calculation(monkeypatch):
    """invite_expiry_days from settings must calculate exact expires_at timestamp."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        default_invite_role="member",
        invite_expiry_days=30,
    )
    session = AsyncMock()

    res_settings = _result(settings)
    res_user = _result(None)
    res_member = _result(None)
    res_invite = _result(None)

    session.execute.side_effect = [res_settings, res_user, res_member, res_invite]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    start_time = datetime.now(timezone.utc)
    invite = await ws_ctrl.invite_user(
        WORKSPACE_ID, "thirty_day@example.com", role=None, inviter_id=INVITER_ID
    )

    expected_expiry = start_time + timedelta(days=30)
    diff = abs((invite["expires_at"] - expected_expiry).total_seconds())
    assert diff < 5


@pytest.mark.asyncio
async def test_invite_user_boundary_expiry_days(monkeypatch):
    """Test boundary expiry values (1 day and 365 days)."""
    for expiry_val in (1, 365):
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="member",
            invite_expiry_days=expiry_val,
        )
        session = AsyncMock()

        session.execute.side_effect = [
            _result(settings),
            _result(None),
            _result(None),
            _result(None),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        _patch_session(monkeypatch, session, ws_ctrl)

        start_time = datetime.now(timezone.utc)
        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID,
            f"boundary_{expiry_val}@example.com",
            role=None,
            inviter_id=INVITER_ID,
        )

        expected_expiry = start_time + timedelta(days=expiry_val)
        diff = abs((invite["expires_at"] - expected_expiry).total_seconds())
        assert diff < 5


@pytest.mark.asyncio
async def test_invite_user_fallback_when_settings_missing(monkeypatch):
    """When no WorkspaceSettings record exists, fallback to default role='member' and expiry=7 days."""
    session = AsyncMock()

    # Settings is None
    res_settings = _result(None)
    res_user = _result(None)
    res_member = _result(None)
    res_invite = _result(None)

    session.execute.side_effect = [res_settings, res_user, res_member, res_invite]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    start_time = datetime.now(timezone.utc)
    invite = await ws_ctrl.invite_user(
        WORKSPACE_ID, "fallback@example.com", role=None, inviter_id=INVITER_ID
    )

    assert invite["role"] == "member"
    expected_expiry = start_time + timedelta(days=7)
    diff = abs((invite["expires_at"] - expected_expiry).total_seconds())
    assert diff < 5


@pytest.mark.asyncio
async def test_invite_user_invalid_role_raises_400(monkeypatch):
    """Invalid role string (e.g. 'owner' or 'guest') must raise HTTP 400."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        default_invite_role="member",
        invite_expiry_days=7,
    )
    session = AsyncMock()
    session.execute.return_value = _result(settings)
    _patch_session(monkeypatch, session, ws_ctrl)

    for invalid_role in ("owner", "superadmin", "guest"):
        with pytest.raises(HTTPException) as exc_info:
            await ws_ctrl.invite_user(
                WORKSPACE_ID,
                "invalid_role@example.com",
                role=invalid_role,
                inviter_id=INVITER_ID,
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "Invalid role for invite"


@pytest.mark.asyncio
async def test_resend_invite_uses_custom_invite_expiry_days(monkeypatch):
    """Resending invite must extend expires_at using WorkspaceSettings.invite_expiry_days."""
    invite_id = str(uuid.uuid4())
    existing_invite = SimpleNamespace(
        id=uuid.UUID(invite_id),
        workspace_id=uuid.UUID(WORKSPACE_ID),
        email="resend@example.com",
        token="mock_invite_token_val",
        accepted_at=None,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Expired
    )
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        invite_expiry_days=14,
    )

    session = AsyncMock()
    session.execute.side_effect = [
        _result(existing_invite),  # _get_invite query
        _result(settings),  # WorkspaceSettings query
    ]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    start_time = datetime.now(timezone.utc)
    resend_res = await ws_ctrl.resend_invite(
        WORKSPACE_ID, invite_id, actor_id=INVITER_ID
    )

    assert resend_res["ok"] is True
    expected_expiry = start_time + timedelta(days=14)
    diff = abs((resend_res["expires_at"] - expected_expiry).total_seconds())
    assert diff < 5


@pytest.mark.asyncio
async def test_resend_invite_fallback_when_settings_missing(monkeypatch):
    """Resending invite with missing WorkspaceSettings falls back to 7 days expiry."""
    invite_id = str(uuid.uuid4())
    existing_invite = SimpleNamespace(
        id=uuid.UUID(invite_id),
        workspace_id=uuid.UUID(WORKSPACE_ID),
        email="resend_fallback@example.com",
        token="mock_invite_token_val",
        accepted_at=None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
    )

    session = AsyncMock()
    session.execute.side_effect = [
        _result(existing_invite),
        _result(None),  # Settings missing
    ]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    start_time = datetime.now(timezone.utc)
    resend_res = await ws_ctrl.resend_invite(
        WORKSPACE_ID, invite_id, actor_id=INVITER_ID
    )

    assert resend_res["ok"] is True
    expected_expiry = start_time + timedelta(days=7)
    diff = abs((resend_res["expires_at"] - expected_expiry).total_seconds())
    assert diff < 5


# =====================================================================
# 2. ACTIVITY LOG RETENTION FILTERING TESTS
# =====================================================================


@pytest.mark.asyncio
async def test_get_workspace_activity_filters_by_custom_retention_days(monkeypatch):
    """get_workspace_activity must filter logs based on WorkspaceSettings.activity_retention_days."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        activity_retention_days=10,
    )
    session = AsyncMock()

    res_settings = _result(settings)

    # 4 log entries at different ages
    now = datetime.now(timezone.utc)
    log_2d = (
        SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(WORKSPACE_ID),
            actor_id=uuid.UUID(INVITER_ID),
            event_type="event.2d",
            resource_type="test",
            resource_id=None,
            metadata_={},
            created_at=now - timedelta(days=2),
        ),
        "user2d@example.com",
    )
    log_5d = (
        SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(WORKSPACE_ID),
            actor_id=uuid.UUID(INVITER_ID),
            event_type="event.5d",
            resource_type="test",
            resource_id=None,
            metadata_={},
            created_at=now - timedelta(days=5),
        ),
        "user5d@example.com",
    )

    res_activity = Mock()
    # Mock return values as filtered by SQL query based on cutoff_date
    res_activity.all.return_value = [log_2d, log_5d]

    session.execute.side_effect = [res_settings, res_activity]
    _patch_session(monkeypatch, session, activity_ctrl)

    logs = await activity_ctrl.get_workspace_activity(WORKSPACE_ID, limit=50)

    # Verify cutoff date calculation passed to SQL execution statement
    call_args = session.execute.call_args_list
    assert len(call_args) == 2
    stmt = call_args[1].args[0]

    # Extract cutoff date from query parameters
    params = stmt.compile().params
    cutoff_param = next(v for v in params.values() if isinstance(v, datetime))

    expected_cutoff = now - timedelta(days=10)
    diff = abs((cutoff_param - expected_cutoff).total_seconds())
    assert diff < 5

    assert len(logs) == 2
    assert [log["event_type"] for log in logs] == ["event.2d", "event.5d"]


@pytest.mark.asyncio
async def test_get_workspace_activity_fallback_retention_when_settings_missing(
    monkeypatch,
):
    """When WorkspaceSettings is missing, activity_retention_days falls back to 30 days."""
    session = AsyncMock()

    res_settings = _result(None)
    res_activity = Mock()
    res_activity.all.return_value = []

    session.execute.side_effect = [res_settings, res_activity]
    _patch_session(monkeypatch, session, activity_ctrl)

    now = datetime.now(timezone.utc)
    await activity_ctrl.get_workspace_activity(WORKSPACE_ID, limit=50)

    call_args = session.execute.call_args_list
    stmt = call_args[1].args[0]
    params = stmt.compile().params
    cutoff_param = next(v for v in params.values() if isinstance(v, datetime))

    expected_cutoff = now - timedelta(days=30)
    diff = abs((cutoff_param - expected_cutoff).total_seconds())
    assert diff < 5


@pytest.mark.asyncio
async def test_iter_workspace_activity_respects_custom_retention_days(monkeypatch):
    """iter_workspace_activity generator must respect workspace activity retention cutoff."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        activity_retention_days=15,
    )
    session = AsyncMock()

    res_settings = _result(settings)
    now = datetime.now(timezone.utc)
    log_item = (
        SimpleNamespace(
            id=uuid.uuid4(),
            workspace_id=uuid.UUID(WORKSPACE_ID),
            actor_id=uuid.UUID(INVITER_ID),
            event_type="exported.event",
            resource_type="export",
            resource_id=None,
            metadata_={},
            created_at=now - timedelta(days=3),
        ),
        "exporter@example.com",
    )

    res_activity = Mock()
    res_activity.all.return_value = [log_item]

    session.execute.side_effect = [res_settings, res_activity]
    _patch_session(monkeypatch, session, activity_ctrl)

    retained_logs = []
    async for row in activity_ctrl.iter_workspace_activity(WORKSPACE_ID):
        retained_logs.append(row)

    assert len(retained_logs) == 1
    assert retained_logs[0]["event_type"] == "exported.event"


@pytest.mark.asyncio
async def test_get_workspace_activity_combines_event_type_filter_and_retention(
    monkeypatch,
):
    """get_workspace_activity applies both retention cutoff date and event_type filter."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        activity_retention_days=60,
    )
    session = AsyncMock()

    res_settings = _result(settings)
    res_activity = Mock()
    res_activity.all.return_value = []

    session.execute.side_effect = [res_settings, res_activity]
    _patch_session(monkeypatch, session, activity_ctrl)

    await activity_ctrl.get_workspace_activity(
        WORKSPACE_ID, limit=20, event_type="member.invite_sent"
    )

    stmt = session.execute.call_args_list[1].args[0]
    compiled_str = str(stmt)

    assert "workspace_activity_log.event_type =" in compiled_str
    assert "workspace_activity_log.created_at >=" in compiled_str


@pytest.mark.asyncio
async def test_update_workspace_settings_modifies_defaults(monkeypatch):
    """Updating settings changes default_invite_role, invite_expiry_days, and activity_retention_days."""
    existing = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        default_invite_role="member",
        invite_expiry_days=7,
        activity_retention_days=30,
        role_permissions={},
    )
    session = AsyncMock()
    session.execute.return_value = _result(existing)
    _patch_session(monkeypatch, session, ws_ctrl)

    update_payload = {
        "default_invite_role": "admin",
        "invite_expiry_days": 90,
        "activity_retention_days": 180,
    }

    updated = await ws_ctrl.update_workspace_settings(
        WORKSPACE_ID, update_payload, actor_id=INVITER_ID
    )

    assert updated["default_invite_role"] == "admin"
    assert updated["invite_expiry_days"] == 90
    assert updated["activity_retention_days"] == 180
    assert existing.default_invite_role == "admin"
    assert existing.invite_expiry_days == 90
    assert existing.activity_retention_days == 180
