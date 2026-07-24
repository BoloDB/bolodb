"""Integration test suite for Workspace Settings API, require_permission dependency,
permission matrix overrides, invite defaults, and activity log retention.
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

import backend.app.controllers.workspaces as ws_ctrl
import backend.app.controllers.activity as activity_ctrl
from backend.app.dependencies import require_permission
from backend.app.models.workspace_settings import WorkspaceSettings

WORKSPACE_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
ADMIN_ID = str(uuid.uuid4())
MEMBER_ID = str(uuid.uuid4())


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


# ── 1. Settings Controller Tests ──


@pytest.mark.asyncio
async def test_get_workspace_settings_creates_defaults_if_missing(monkeypatch):
    session = AsyncMock()
    session.execute.return_value = _result(None)

    saved_settings = []

    def fake_add(obj):
        saved_settings.append(obj)

    session.add = fake_add
    _patch_session(monkeypatch, session, ws_ctrl)

    settings = await ws_ctrl.get_workspace_settings(WORKSPACE_ID)

    assert settings["workspace_id"] == WORKSPACE_ID
    assert settings["default_invite_role"] == "member"
    assert settings["invite_expiry_days"] == 7
    assert settings["activity_retention_days"] == 30
    assert settings["role_permissions"] == {}
    assert "resolved_matrix" in settings
    assert settings["resolved_matrix"]["owner"]["queries.execute"] is True
    assert settings["resolved_matrix"]["admin"]["dashboards.create"] is True
    assert settings["resolved_matrix"]["member"]["dashboards.create"] is False


@pytest.mark.asyncio
async def test_update_workspace_settings_excludes_owner_overrides(monkeypatch):
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
        "invite_expiry_days": 14,
        "activity_retention_days": 60,
        "role_permissions": {
            "owner": {"queries.execute": False},  # Must be excluded!
            "member": {"dashboards.create": True},
        },
    }

    updated = await ws_ctrl.update_workspace_settings(
        WORKSPACE_ID, update_payload, actor_id=USER_ID
    )

    assert updated["default_invite_role"] == "admin"
    assert updated["invite_expiry_days"] == 14
    assert updated["activity_retention_days"] == 60
    assert "owner" not in updated["role_permissions"]
    assert updated["role_permissions"] == {"member": {"dashboards.create": True}}
    # Owner matrix remains all True
    assert updated["resolved_matrix"]["owner"]["queries.execute"] is True
    # Member matrix gets overridden
    assert updated["resolved_matrix"]["member"]["dashboards.create"] is True


# ── 2. Invite Controller Integration Tests ──


@pytest.mark.asyncio
async def test_invite_user_uses_workspace_settings_defaults(monkeypatch):
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        default_invite_role="admin",
        invite_expiry_days=14,
    )
    session = AsyncMock()

    res_settings = _result(settings)
    res_user = _result(None)
    res_member = _result(None)
    res_invite = _result(None)

    session.execute.side_effect = [res_settings, res_user, res_member, res_invite]
    session.get.return_value = SimpleNamespace(name="Acme Corp")
    _patch_session(monkeypatch, session, ws_ctrl)

    invite = await ws_ctrl.invite_user(WORKSPACE_ID, "test@example.com", None, USER_ID)

    assert invite["role"] == "admin"
    expected_expiry = datetime.now(timezone.utc) + timedelta(days=14)
    diff = abs((invite["expires_at"] - expected_expiry).total_seconds())
    assert diff < 60


# ── 3. Activity Controller Integration Tests ──


@pytest.mark.asyncio
async def test_get_workspace_activity_uses_settings_retention_days(monkeypatch):
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        activity_retention_days=5,
    )
    session = AsyncMock()

    res_settings = _result(settings)

    old_log = SimpleNamespace(
        id=uuid.uuid4(),
        workspace_id=uuid.UUID(WORKSPACE_ID),
        actor_id=uuid.UUID(USER_ID),
        event_type="test.event",
        resource_type="test",
        resource_id=None,
        metadata_={},
        created_at=datetime.now(timezone.utc) - timedelta(days=2),
    )
    res_activity = Mock()
    res_activity.all.return_value = [(old_log, "user@example.com")]

    session.execute.side_effect = [res_settings, res_activity]
    _patch_session(monkeypatch, session, activity_ctrl)

    logs = await activity_ctrl.get_workspace_activity(WORKSPACE_ID, limit=50)

    assert len(logs) == 1
    assert logs[0]["event_type"] == "test.event"


# ── 4. Require Permission & Route Integration Tests ──


@pytest.mark.asyncio
async def test_require_permission_owner_bypasses(monkeypatch):
    dep = require_permission("dashboards.create")
    workspace_context = {
        "workspace_id": WORKSPACE_ID,
        "role": "owner",
        "user_id": USER_ID,
    }

    res = await dep(workspace=workspace_context)
    assert res == workspace_context


@pytest.mark.asyncio
async def test_require_permission_custom_override_denies(monkeypatch):
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"admin": {"dashboards.create": False}},
    )
    session = AsyncMock()
    session.execute.return_value = _result(settings)

    from backend.app import dependencies

    _patch_session(monkeypatch, session, dependencies)

    dep = require_permission("dashboards.create")
    workspace_context = {
        "workspace_id": WORKSPACE_ID,
        "role": "admin",
        "user_id": ADMIN_ID,
    }

    with pytest.raises(HTTPException) as exc_info:
        await dep(workspace=workspace_context)

    assert exc_info.value.status_code == 403
    assert "Permission 'dashboards.create' required" in exc_info.value.detail


@pytest.mark.asyncio
async def test_require_permission_custom_override_allows(monkeypatch):
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"member": {"dashboards.create": True}},
    )
    session = AsyncMock()
    session.execute.return_value = _result(settings)

    from backend.app import dependencies

    _patch_session(monkeypatch, session, dependencies)

    dep = require_permission("dashboards.create")
    workspace_context = {
        "workspace_id": WORKSPACE_ID,
        "role": "member",
        "user_id": MEMBER_ID,
    }

    res = await dep(workspace=workspace_context)
    assert res == workspace_context


@pytest.mark.asyncio
async def test_update_workspace_settings_deep_merges_roles_and_strips_owner(
    monkeypatch,
):
    existing = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"admin": {"members.invite": False}},
    )
    session = AsyncMock()
    session.execute.return_value = _result(existing)
    _patch_session(monkeypatch, session, ws_ctrl)

    # First update member role permissions; admin permissions must be preserved.
    res1 = await ws_ctrl.update_workspace_settings(
        WORKSPACE_ID,
        {
            "role_permissions": {
                "member": {"dashboards.create": True},
                "owner": {"foo": True},
            }
        },
        actor_id=USER_ID,
    )

    assert "owner" not in res1["role_permissions"]
    assert res1["role_permissions"]["admin"] == {"members.invite": False}
    assert res1["role_permissions"]["member"] == {"dashboards.create": True}

    # Second update admin role permissions; existing member permissions and admin keys are merged.
    res2 = await ws_ctrl.update_workspace_settings(
        WORKSPACE_ID,
        {"role_permissions": {"admin": {"queries.delete_saved": False}}},
        actor_id=USER_ID,
    )

    assert "owner" not in res2["role_permissions"]
    assert res2["role_permissions"]["admin"] == {
        "members.invite": False,
        "queries.delete_saved": False,
    }
    assert res2["role_permissions"]["member"] == {"dashboards.create": True}
