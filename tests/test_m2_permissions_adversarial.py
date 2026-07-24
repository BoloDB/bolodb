"""Adversarial test suite for BoloDB Phase 4 Milestone 2.

Focuses on:
1. Route permission enforcement for default role capabilities.
2. Custom matrix overrides (disabling/enabling capabilities per role like dashboards.create or queries.execute).
3. Verification that disabling a permission for Member or Admin results in HTTP 403.
4. Settings update authorization (Admin and Member get HTTP 403 on PATCH /api/workspaces/{id}/settings).
5. Owner non-editable bypass verification across routes.
6. Edge case & malformed input handling in permissions dependency.
"""

import uuid
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.server import create_app
from backend.app.dependencies import (
    get_current_user,
    get_current_workspace,
    require_permission,
)
from backend.app.models.workspace_settings import WorkspaceSettings

WORKSPACE_ID = str(uuid.uuid4())
OWNER_ID = str(uuid.uuid4())
ADMIN_ID = str(uuid.uuid4())
MEMBER_ID = str(uuid.uuid4())


def _mock_db_result(value):
    res = Mock(name="QueryResult")
    res.scalar_one_or_none = Mock(return_value=value)
    return res


@pytest.fixture
def app_instance():
    """Create a FastAPI app instance with rate limiting / lifespan dependencies disabled for test simplicity."""
    with patch("backend.app.server.lifespan"):
        app = create_app(readonly=True)
        # Clear rate limiters if any to prevent 429 during fast test loops
        app.state.limiter.enabled = False
        return app


# =====================================================================
# 1. ROUTE PERMISSION ENFORCEMENT & SETTINGS AUTHORIZATION (HTTP TESTS)
# =====================================================================


def test_update_settings_admin_returns_403(app_instance, monkeypatch):
    """Task 3: Verify that updating settings as Admin returns HTTP 403."""
    client = TestClient(app_instance)

    # Override get_current_workspace to simulate Admin role context
    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "admin",
        "user_id": ADMIN_ID,
    }

    payload = {"default_invite_role": "admin", "invite_expiry_days": 14}
    res = client.patch(f"/api/workspaces/{WORKSPACE_ID}/settings", json=payload)

    assert res.status_code == 403
    assert "Owner role required" in res.json()["detail"]
    app_instance.dependency_overrides.clear()


def test_update_settings_member_returns_403(app_instance, monkeypatch):
    """Task 3: Verify that updating settings as Member returns HTTP 403."""
    client = TestClient(app_instance)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "member",
        "user_id": MEMBER_ID,
    }

    payload = {"default_invite_role": "member", "invite_expiry_days": 30}
    res = client.patch(f"/api/workspaces/{WORKSPACE_ID}/settings", json=payload)

    assert res.status_code == 403
    assert "Owner role required" in res.json()["detail"]
    app_instance.dependency_overrides.clear()


def test_update_settings_owner_succeeds(app_instance, monkeypatch):
    """Verify that updating settings as Owner succeeds with HTTP 200."""
    client = TestClient(app_instance)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "owner",
        "user_id": OWNER_ID,
    }

    mock_update = AsyncMock(
        return_value={
            "workspace_id": WORKSPACE_ID,
            "default_invite_role": "admin",
            "invite_expiry_days": 14,
            "activity_retention_days": 60,
            "role_permissions": {},
            "resolved_matrix": {},
        }
    )
    monkeypatch.setattr(
        "backend.app.controllers.workspaces.update_workspace_settings", mock_update
    )

    payload = {"default_invite_role": "admin", "invite_expiry_days": 14}
    res = client.patch(f"/api/workspaces/{WORKSPACE_ID}/settings", json=payload)

    assert res.status_code == 200
    assert res.json()["default_invite_role"] == "admin"
    app_instance.dependency_overrides.clear()


def test_member_disabled_dashboards_create_returns_403(app_instance, monkeypatch):
    """Task 2: Verify that default or disabled dashboards.create for Member returns HTTP 403."""
    client = TestClient(app_instance)

    # Mock DB session in require_permission to return standard default settings (role_permissions={})
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
    )
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(settings)

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "member",
        "user_id": MEMBER_ID,
    }
    app_instance.dependency_overrides[get_current_user] = lambda: {
        "user_id": MEMBER_ID,
        "sub": MEMBER_ID,
    }

    res = client.post("/api/dashboards", json={"name": "Forbidden Dashboard"})
    assert res.status_code == 403
    assert "Permission 'dashboards.create' required" in res.json()["detail"]
    app_instance.dependency_overrides.clear()


def test_member_disabled_queries_execute_via_override_returns_403(
    app_instance, monkeypatch
):
    """Task 2: Verify that disabling queries.execute for Member via custom matrix override returns HTTP 403."""
    client = TestClient(app_instance)

    # Custom matrix override disabling queries.execute for member
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"member": {"queries.execute": False}},
    )
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(settings)

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "member",
        "user_id": MEMBER_ID,
    }

    # 1. Check POST /api/query
    res_query = client.post("/api/query", json={"question": "SELECT 1"})
    assert res_query.status_code == 403
    assert "Permission 'queries.execute' required" in res_query.json()["detail"]

    # 2. Check POST /api/execute
    res_exec = client.post("/api/execute", json={"sql": "SELECT 1"})
    assert res_exec.status_code == 403
    assert "Permission 'queries.execute' required" in res_exec.json()["detail"]

    # 3. Check POST /api/feedback
    res_fb = client.post("/api/feedback", json={"query_id": "123", "rating": 5})
    assert res_fb.status_code == 403
    assert "Permission 'queries.execute' required" in res_fb.json()["detail"]

    app_instance.dependency_overrides.clear()


def test_admin_disabled_dashboards_create_via_override_returns_403(
    app_instance, monkeypatch
):
    """Task 1 & 2: Custom matrix override disabling dashboards.create for Admin returns HTTP 403."""
    client = TestClient(app_instance)

    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"admin": {"dashboards.create": False}},
    )
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(settings)

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "admin",
        "user_id": ADMIN_ID,
    }
    app_instance.dependency_overrides[get_current_user] = lambda: {
        "user_id": ADMIN_ID,
        "sub": ADMIN_ID,
    }

    res = client.post("/api/dashboards", json={"name": "Admin Denied Dashboard"})
    assert res.status_code == 403
    assert "Permission 'dashboards.create' required" in res.json()["detail"]

    app_instance.dependency_overrides.clear()


def test_member_granted_dashboards_create_via_override_succeeds(
    app_instance, monkeypatch
):
    """Task 1: Custom matrix override granting dashboards.create to Member allows access."""
    client = TestClient(app_instance)

    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"member": {"dashboards.create": True}},
    )
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(settings)

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "member",
        "user_id": MEMBER_ID,
    }
    app_instance.dependency_overrides[get_current_user] = lambda: {
        "user_id": MEMBER_ID,
        "sub": MEMBER_ID,
    }

    mock_create = AsyncMock(return_value={"id": "dash-1", "name": "Allowed Dashboard"})
    monkeypatch.setattr(
        "backend.app.controllers.dashboards.create_dashboard", mock_create
    )

    res = client.post("/api/dashboards", json={"name": "Allowed Dashboard"})
    assert res.status_code == 200
    assert res.json()["name"] == "Allowed Dashboard"

    app_instance.dependency_overrides.clear()


def test_owner_bypasses_custom_matrix_overrides_on_all_routes(
    app_instance, monkeypatch
):
    """Task 1: Owner role unconditionally bypasses custom matrix overrides trying to disable permissions."""
    client = TestClient(app_instance)

    # Database settings attempt to disable all permissions for Owner (which update_workspace_settings strips, but test DB value here)
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={
            "owner": {"dashboards.create": False, "queries.execute": False}
        },
    )
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(settings)

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "owner",
        "user_id": OWNER_ID,
    }
    app_instance.dependency_overrides[get_current_user] = lambda: {
        "user_id": OWNER_ID,
        "sub": OWNER_ID,
    }

    mock_create = AsyncMock(
        return_value={"id": "dash-owner", "name": "Owner Dashboard"}
    )
    monkeypatch.setattr(
        "backend.app.controllers.dashboards.create_dashboard", mock_create
    )

    res = client.post("/api/dashboards", json={"name": "Owner Dashboard"})
    assert res.status_code == 200
    assert res.json()["name"] == "Owner Dashboard"

    app_instance.dependency_overrides.clear()


# =====================================================================
# 2. ADVERSARIAL & EDGE CASE DEPENDENCY TESTS
# =====================================================================


@pytest.mark.asyncio
async def test_require_permission_missing_settings_uses_default_matrix(monkeypatch):
    """When WorkspaceSettings row is missing from DB, require_permission uses default role permissions."""
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(None)  # No settings record

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    dep_create = require_permission("dashboards.create")
    dep_exec = require_permission("queries.execute")

    member_ctx = {"workspace_id": WORKSPACE_ID, "role": "member", "user_id": MEMBER_ID}
    admin_ctx = {"workspace_id": WORKSPACE_ID, "role": "admin", "user_id": ADMIN_ID}

    # Member lacks dashboards.create by default -> 403
    with pytest.raises(HTTPException) as exc1:
        await dep_create(workspace=member_ctx)
    assert exc1.value.status_code == 403

    # Member has queries.execute by default -> passes
    res_exec = await dep_exec(workspace=member_ctx)
    assert res_exec == member_ctx

    # Admin has dashboards.create by default -> passes
    res_admin = await dep_create(workspace=admin_ctx)
    assert res_admin == admin_ctx


@pytest.mark.asyncio
async def test_require_permission_invalid_or_malformed_overrides(monkeypatch):
    """Test require_permission behavior when role_permissions contains invalid types or malformed structures."""
    malformed_cases = [
        "not_a_dict",
        12345,
        [True, False],
        {"member": "invalid_inner_string"},
        {"member": {"queries.execute": "yes_string_not_bool"}},
    ]

    for malformed in malformed_cases:
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions=malformed
        )
        session = AsyncMock()
        session.execute.return_value = _mock_db_result(settings)

        factory = Mock(return_value=session)
        session.__aenter__.return_value = session
        monkeypatch.setattr("backend.app.dependencies.async_session", factory)

        dep_exec = require_permission("queries.execute")
        member_ctx = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }

        # Member should still fall back to default queries.execute=True
        res = await dep_exec(workspace=member_ctx)
        assert res == member_ctx, (
            f"Failed for malformed role_permissions case: {malformed}"
        )


@pytest.mark.asyncio
async def test_require_permission_nonexistent_capability_key(monkeypatch):
    """Non-existent permission capability keys always raise HTTP 403 for non-owner roles."""
    settings = WorkspaceSettings(
        workspace_id=uuid.UUID(WORKSPACE_ID),
        role_permissions={"admin": {"fake.key": True}},
    )
    session = AsyncMock()
    session.execute.return_value = _mock_db_result(settings)

    factory = Mock(return_value=session)
    session.__aenter__.return_value = session
    monkeypatch.setattr("backend.app.dependencies.async_session", factory)

    dep_fake = require_permission("fake.capability.key")
    admin_ctx = {"workspace_id": WORKSPACE_ID, "role": "admin", "user_id": ADMIN_ID}

    with pytest.raises(HTTPException) as exc:
        await dep_fake(workspace=admin_ctx)
    assert exc.value.status_code == 403
    assert "Permission 'fake.capability.key' required" in exc.value.detail


@pytest.mark.asyncio
async def test_delete_workspace_and_transfer_ownership_authorization(
    app_instance, monkeypatch
):
    """Verify delete workspace and transfer ownership endpoints require Owner role."""
    client = TestClient(app_instance)

    app_instance.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "admin",
        "user_id": ADMIN_ID,
    }

    # Delete workspace as Admin -> 403
    res_del = client.delete(f"/api/workspaces/{WORKSPACE_ID}")
    assert res_del.status_code == 403
    assert "Owner role required" in res_del.json()["detail"]

    # Transfer ownership as Admin -> 403
    res_xfer = client.post(
        f"/api/workspaces/{WORKSPACE_ID}/transfer-ownership",
        json={"user_id": MEMBER_ID},
    )
    assert res_xfer.status_code == 403
    assert "Owner role required" in res_xfer.json()["detail"]

    app_instance.dependency_overrides.clear()
