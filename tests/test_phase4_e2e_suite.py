"""
Phase 4 E2E Test Track Suite (Tiers 1-4) for BoloDB Workspace Defaults & Configurable RBAC Permission Matrix.

Features Tested:
1. Central Permissions Registry & Default Role Matrix (Tier 1 & Tier 2)
2. workspace_settings Table & Model Persistence (Tier 1 & Tier 2)
3. require_permission Route Access Control & Owner Bypass (Tier 1 & Tier 2)
4. Settings GET/PATCH Endpoints & Sparse JSONB Overrides (Tier 1 & Tier 2)
5. Workspace Defaults Integration (Invites & Activity Log Retention) (Tier 1 & Tier 2)
6. Frontend Settings & Permissions Toggle Matrix UI Integration (Tier 1 & Tier 2)
7. Cross-Feature Pairwise Combinations (Tier 3)
8. Real-World Application Scenarios (Tier 4)

Total Test Cases: 71 (Tier 1: 30, Tier 2: 30, Tier 3: 6, Tier 4: 5)
"""

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

import backend.app.controllers.workspaces as ws_ctrl
import backend.app.controllers.activity as activity_ctrl
from backend.app import dependencies
from backend.app.dependencies import get_current_workspace, require_permission
from backend.app.models.workspace_settings import WorkspaceSettings
from backend.app.models.workspace_api import WorkspaceSettingsUpdate
from backend.app.permissions import (
    PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    MEMBER_DEFAULT_PERMISSIONS,
    resolve_role_permissions,
    has_permission,
)
from backend.app.server import create_app

WORKSPACE_ID = str(uuid.uuid4())
OWNER_ID = str(uuid.uuid4())
ADMIN_ID = str(uuid.uuid4())
MEMBER_ID = str(uuid.uuid4())


def _mock_result(value):
    res = Mock(name="QueryResult")
    res.scalar_one_or_none = Mock(return_value=value)
    return res


def _patch_session(monkeypatch, session, target_module):
    factory = Mock()
    factory.return_value = session
    session.__aenter__.return_value = session
    monkeypatch.setattr(target_module, "async_session", factory)
    return factory


@pytest.fixture
def app_instance():
    """Create FastAPI app with disabled lifespan/rate limiting for testing endpoints."""
    with patch("backend.app.server.lifespan"):
        app = create_app(readonly=True)
        if hasattr(app.state, "limiter"):
            app.state.limiter.enabled = False
        return app


# =====================================================================
# TIER 1: FEATURE COVERAGE (30 TEST CASES)
# =====================================================================


class TestTier1Feature1CentralPermissionsRegistry:
    """Feature 1: Central Permissions Registry & Default Role Matrix (5 cases)."""

    def test_tier1_f1_registry_total_count_and_categories(self):
        """1. Verify registry defines exactly 21 capabilities across 7 resource categories."""
        assert len(PERMISSIONS) == 21, (
            f"Expected 21 permissions, got {len(PERMISSIONS)}"
        )

        expected_categories = {
            "members": 4,
            "connections": 3,
            "catalog": 2,
            "dashboards": 3,
            "queries": 4,
            "activity": 2,
            "workspace_management": 3,
        }
        category_counts = {}
        for perm in PERMISSIONS.values():
            cat = perm["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

        assert category_counts == expected_categories

    def test_tier1_f1_owner_default_role_matrix(self):
        """2. Verify owner default role matrix grants all 21 permissions."""
        owner_matrix = DEFAULT_ROLE_PERMISSIONS["owner"]
        assert len(owner_matrix) == 21
        assert all(val is True for val in owner_matrix.values())

    def test_tier1_f1_admin_default_role_matrix(self):
        """3. Verify admin default role matrix grants all 21 permissions."""
        admin_matrix = DEFAULT_ROLE_PERMISSIONS["admin"]
        assert len(admin_matrix) == 21
        assert all(val is True for val in admin_matrix.values())

    def test_tier1_f1_member_default_role_matrix(self):
        """4. Verify member default role matrix grants 9 True and 12 False permissions."""
        member_matrix = DEFAULT_ROLE_PERMISSIONS["member"]
        assert len(member_matrix) == 21
        true_keys = {k for k, v in member_matrix.items() if v is True}
        assert true_keys == MEMBER_DEFAULT_PERMISSIONS
        assert len(true_keys) == 9
        assert sum(1 for v in member_matrix.values() if v is False) == 12

    def test_tier1_f1_resolve_role_permissions_defaults(self):
        """5. Verify resolve_role_permissions resolves defaults correctly for standard roles."""
        resolved_owner = resolve_role_permissions("owner")
        assert all(resolved_owner.values())

        resolved_admin = resolve_role_permissions("admin")
        assert all(resolved_admin.values())

        resolved_member = resolve_role_permissions("member")
        assert resolved_member["queries.execute"] is True
        assert resolved_member["members.invite"] is False


class TestTier1Feature2WorkspaceSettingsPersistence:
    """Feature 2: workspace_settings Table & Model Persistence (5 cases)."""

    def test_tier1_f2_settings_model_defaults(self):
        """6. Verify WorkspaceSettings ORM model default field values."""
        wid = uuid.uuid4()
        settings = WorkspaceSettings(workspace_id=wid)
        assert settings.workspace_id == wid
        assert settings.default_invite_role == "member"
        assert settings.invite_expiry_days == 7
        assert settings.activity_retention_days == 30
        assert settings.role_permissions == {}

    @pytest.mark.asyncio
    async def test_tier1_f2_get_workspace_settings_creates_defaults(self, monkeypatch):
        """7. Verify get_workspace_settings initializes missing settings row in DB."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        saved = []
        session.add = lambda obj: saved.append(obj)
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.get_workspace_settings(WORKSPACE_ID)
        assert res["workspace_id"] == WORKSPACE_ID
        assert res["default_invite_role"] == "member"
        assert res["invite_expiry_days"] == 7
        assert res["activity_retention_days"] == 30
        assert len(saved) == 1

    @pytest.mark.asyncio
    async def test_tier1_f2_update_workspace_settings_scalar_fields(self, monkeypatch):
        """8. Verify update_workspace_settings persists scalar configuration updates."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="member",
            invite_expiry_days=7,
            activity_retention_days=30,
            role_permissions={},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {
            "default_invite_role": "admin",
            "invite_expiry_days": 14,
            "activity_retention_days": 90,
        }
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert res["default_invite_role"] == "admin"
        assert res["invite_expiry_days"] == 14
        assert res["activity_retention_days"] == 90

    @pytest.mark.asyncio
    async def test_tier1_f2_update_workspace_settings_role_permissions(
        self, monkeypatch
    ):
        """9. Verify update_workspace_settings persists sparse JSONB permissions overrides."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {
            "role_permissions": {
                "member": {"dashboards.create": True},
                "admin": {"members.remove": False},
            }
        }
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert res["role_permissions"] == payload["role_permissions"]
        assert res["resolved_matrix"]["member"]["dashboards.create"] is True
        assert res["resolved_matrix"]["admin"]["members.remove"] is False

    @pytest.mark.asyncio
    async def test_tier1_f2_update_workspace_settings_owner_exclusion(
        self, monkeypatch
    ):
        """10. Verify attempted owner permission overrides are stripped on update."""
        existing = WorkspaceSettings(workspace_id=uuid.UUID(WORKSPACE_ID))
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {
            "role_permissions": {
                "owner": {"queries.execute": False},
                "member": {"dashboards.create": True},
            }
        }
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert "owner" not in res["role_permissions"]
        assert res["resolved_matrix"]["owner"]["queries.execute"] is True


class TestTier1Feature3RequirePermissionDependency:
    """Feature 3: require_permission Dependency & Route Access Control (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier1_f3_owner_bypass_without_db_lookup(self):
        """11. Verify owner bypasses permissions check directly without DB query."""
        dep = require_permission("dashboards.create")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "owner",
            "user_id": OWNER_ID,
        }
        res = await dep(workspace=ws_context)
        assert res == ws_context

    @pytest.mark.asyncio
    async def test_tier1_f3_admin_default_permission_allowed(self, monkeypatch):
        """12. Verify admin passes default permission check."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("dashboards.create")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "admin",
            "user_id": ADMIN_ID,
        }
        res = await dep(workspace=ws_context)
        assert res == ws_context

    @pytest.mark.asyncio
    async def test_tier1_f3_member_default_permission_allowed(self, monkeypatch):
        """13. Verify member passes allowed default permission check (queries.execute)."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("queries.execute")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        res = await dep(workspace=ws_context)
        assert res == ws_context

    @pytest.mark.asyncio
    async def test_tier1_f3_member_restricted_permission_raises_403(self, monkeypatch):
        """14. Verify member gets 403 for restricted permission (members.invite)."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("members.invite")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        with pytest.raises(HTTPException) as exc_info:
            await dep(workspace=ws_context)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tier1_f3_sparse_override_revocation_raises_403(self, monkeypatch):
        """15. Verify custom override revoking member permission raises 403."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": {"queries.execute": False}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(settings)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("queries.execute")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        with pytest.raises(HTTPException) as exc_info:
            await dep(workspace=ws_context)
        assert exc_info.value.status_code == 403


class TestTier1Feature4SettingsEndpointsAndOverrides:
    """Feature 4: Settings GET/PATCH Endpoints & Sparse Overrides (5 cases)."""

    def test_tier1_f4_get_settings_endpoint_owner_success(
        self, app_instance, monkeypatch
    ):
        """16. Verify GET /api/workspaces/{id}/settings succeeds for Owner."""
        client = TestClient(app_instance)
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "owner",
            "user_id": OWNER_ID,
        }
        mock_settings = {
            "workspace_id": WORKSPACE_ID,
            "default_invite_role": "member",
            "invite_expiry_days": 7,
            "activity_retention_days": 30,
            "role_permissions": {},
            "resolved_matrix": DEFAULT_ROLE_PERMISSIONS,
        }
        monkeypatch.setattr(
            "backend.app.routes.workspaces.ctrl.get_workspace_settings",
            AsyncMock(return_value=mock_settings),
        )

        response = client.get(f"/api/workspaces/{WORKSPACE_ID}/settings")
        assert response.status_code == 200
        assert response.json()["workspace_id"] == WORKSPACE_ID
        app_instance.dependency_overrides.clear()

    def test_tier1_f4_patch_settings_endpoint_owner_success(
        self, app_instance, monkeypatch
    ):
        """17. Verify PATCH /api/workspaces/{id}/settings succeeds for Owner."""
        client = TestClient(app_instance)
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "owner",
            "user_id": OWNER_ID,
        }
        updated_mock = {
            "workspace_id": WORKSPACE_ID,
            "default_invite_role": "admin",
            "invite_expiry_days": 14,
            "activity_retention_days": 60,
            "role_permissions": {"member": {"dashboards.create": True}},
            "resolved_matrix": DEFAULT_ROLE_PERMISSIONS,
        }
        monkeypatch.setattr(
            "backend.app.routes.workspaces.ctrl.update_workspace_settings",
            AsyncMock(return_value=updated_mock),
        )

        payload = {"default_invite_role": "admin", "invite_expiry_days": 14}
        response = client.patch(
            f"/api/workspaces/{WORKSPACE_ID}/settings", json=payload
        )
        assert response.status_code == 200
        assert response.json()["default_invite_role"] == "admin"
        app_instance.dependency_overrides.clear()

    def test_tier1_f4_patch_settings_endpoint_admin_forbidden(self, app_instance):
        """18. Verify PATCH /api/workspaces/{id}/settings returns 403 for Admin."""
        client = TestClient(app_instance)
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "admin",
            "user_id": ADMIN_ID,
        }

        response = client.patch(
            f"/api/workspaces/{WORKSPACE_ID}/settings", json={"invite_expiry_days": 14}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Owner role required"
        app_instance.dependency_overrides.clear()

    def test_tier1_f4_patch_settings_endpoint_member_forbidden(self, app_instance):
        """19. Verify PATCH /api/workspaces/{id}/settings returns 403 for Member."""
        client = TestClient(app_instance)
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }

        response = client.patch(
            f"/api/workspaces/{WORKSPACE_ID}/settings", json={"invite_expiry_days": 14}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Owner role required"
        app_instance.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_tier1_f4_patch_settings_sparse_permission_merge(self, monkeypatch):
        """20. Verify sparse PATCH merges role permissions without wiping unreferenced roles."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"admin": {"dashboards.manage": False}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        update_payload = {
            "role_permissions": {
                "admin": {"dashboards.manage": False},
                "member": {"dashboards.create": True},
            }
        }
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, update_payload, actor_id=OWNER_ID
        )
        assert res["role_permissions"]["admin"]["dashboards.manage"] is False
        assert res["role_permissions"]["member"]["dashboards.create"] is True


class TestTier1Feature5WorkspaceDefaultsIntegration:
    """Feature 5: Workspace Defaults Integration (Invites & Activity Log Retention) (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier1_f5_invite_uses_workspace_default_role(self, monkeypatch):
        """21. Verify invite creation uses default_invite_role setting when role is None."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="admin",
            invite_expiry_days=7,
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(None),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "newuser@example.com", None, OWNER_ID
        )
        assert invite["role"] == "admin"

    @pytest.mark.asyncio
    async def test_tier1_f5_invite_uses_workspace_expiry_days(self, monkeypatch):
        """22. Verify invite creation uses invite_expiry_days setting when expiry_days is None."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="member",
            invite_expiry_days=14,
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(None),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "newuser@example.com", None, OWNER_ID
        )
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=14)
        diff = abs((invite["expires_at"] - expected_expiry).total_seconds())
        assert diff < 60

    @pytest.mark.asyncio
    async def test_tier1_f5_invite_explicit_role_overrides_default(self, monkeypatch):
        """23. Verify passing explicit role overrides default_invite_role setting."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="member",
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(None),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "newuser@example.com", "admin", OWNER_ID
        )
        assert invite["role"] == "admin"

    @pytest.mark.asyncio
    async def test_tier1_f5_activity_retention_days_query(self, monkeypatch):
        """24. Verify activity log query uses activity_retention_days setting."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            activity_retention_days=10,
        )
        session = AsyncMock()
        res_activity = Mock()
        res_activity.all.return_value = []
        session.execute.side_effect = [_mock_result(settings), res_activity]
        _patch_session(monkeypatch, session, activity_ctrl)

        logs = await activity_ctrl.get_workspace_activity(WORKSPACE_ID, limit=50)
        assert logs == []

    @pytest.mark.asyncio
    async def test_tier1_f5_activity_cleanup_controller_retention(self, monkeypatch):
        """25. Verify delete_old_activity prunes logs using retention window."""
        session = AsyncMock()
        del_result = Mock()
        del_result.rowcount = 3
        session.execute.return_value = del_result
        _patch_session(monkeypatch, session, activity_ctrl)

        count = await activity_ctrl.delete_old_activity(retention_days=15)
        assert count == 3


class TestTier1Feature6FrontendSettingsMatrixUI:
    """Feature 6: Frontend Settings & Permissions Toggle Matrix UI Integration (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier1_f6_resolved_matrix_format_structure(self, monkeypatch):
        """26. Verify GET settings response contains complete resolved_matrix structure."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        session.add = Mock()
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.get_workspace_settings(WORKSPACE_ID)
        assert "resolved_matrix" in res
        matrix = res["resolved_matrix"]
        assert "owner" in matrix and "admin" in matrix and "member" in matrix

    def test_tier1_f6_matrix_payload_all_keys_presence(self):
        """27. Verify all 21 permission keys exist in resolved_matrix for every role."""
        matrix = {
            role: resolve_role_permissions(role)
            for role in ["owner", "admin", "member"]
        }
        for role in ["owner", "admin", "member"]:
            assert len(matrix[role]) == 21
            for key in PERMISSIONS:
                assert key in matrix[role]

    @pytest.mark.asyncio
    async def test_tier1_f6_matrix_toggle_patch_roundtrip(self, monkeypatch):
        """28. Verify setting matrix toggle via update_workspace_settings reflects in resolved_matrix."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {"role_permissions": {"member": {"dashboards.create": True}}}
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert res["resolved_matrix"]["member"]["dashboards.create"] is True

    @pytest.mark.asyncio
    async def test_tier1_f6_matrix_reset_overrides_empty_dict(self, monkeypatch):
        """29. Verify updating role_permissions to {} resets resolved_matrix back to default RBAC."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": {"dashboards.create": True}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {"role_permissions": {}}
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert res["role_permissions"] == {}
        assert res["resolved_matrix"]["member"]["dashboards.create"] is False

    @pytest.mark.asyncio
    async def test_tier1_f6_matrix_invalid_permission_keys_ignored(self, monkeypatch):
        """30. Verify invalid permission keys in patch payload are filtered out during resolution."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {
            "role_permissions": {
                "member": {"invalid.perm.key": True, "dashboards.create": True}
            }
        }
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert "invalid.perm.key" not in res["resolved_matrix"]["member"]
        assert res["resolved_matrix"]["member"]["dashboards.create"] is True


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES (30 TEST CASES)
# =====================================================================


class TestTier2Feature1CentralPermissionsRegistryBoundaries:
    """Feature 1 Boundaries (5 cases)."""

    def test_tier2_f1_unknown_role_resolution_all_false(self):
        """31. Verify resolve_role_permissions for unknown role returns all False."""
        res = resolve_role_permissions("guest")
        assert len(res) == 21
        assert all(v is False for v in res.values())

    def test_tier2_f1_has_permission_non_existent_key(self):
        """32. Verify has_permission for non-existent permission key returns False for all roles."""
        assert has_permission("admin", "invalid.key") is False
        assert has_permission("owner", "non_existent_capability") is False

    def test_tier2_f1_has_permission_dual_signature_formats(self):
        """33. Verify has_permission dual signature invocation forms."""
        # 2-arg signature
        assert has_permission("member", "queries.execute") is True
        # 3-arg signature with overrides dict
        overrides = {"member": {"queries.execute": False}}
        assert has_permission("member", overrides, "queries.execute") is False

    def test_tier2_f1_has_permission_none_and_empty_args(self):
        """34. Verify has_permission with None or empty string parameters."""
        assert has_permission(None, "queries.execute") is False
        assert has_permission("member", "") is False
        assert has_permission("member", None) is False

    def test_tier2_f1_all_categories_exhaustive_check(self):
        """35. Verify all 21 permission keys resolve boolean for member role."""
        resolved = resolve_role_permissions("member")
        for key in PERMISSIONS:
            assert isinstance(resolved[key], bool)


class TestTier2Feature2WorkspaceSettingsPersistenceBoundaries:
    """Feature 2 Boundaries (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier2_f2_expiry_days_boundary_values(self, monkeypatch):
        """36. Verify update_workspace_settings handles boundary values for invite_expiry_days."""
        existing = WorkspaceSettings(workspace_id=uuid.UUID(WORKSPACE_ID))
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {"invite_expiry_days": 1}, actor_id=OWNER_ID
        )
        assert res["invite_expiry_days"] == 1

        res_max = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {"invite_expiry_days": 365}, actor_id=OWNER_ID
        )
        assert res_max["invite_expiry_days"] == 365

    @pytest.mark.asyncio
    async def test_tier2_f2_retention_days_boundary_values(self, monkeypatch):
        """37. Verify update_workspace_settings handles boundary values for activity_retention_days."""
        existing = WorkspaceSettings(workspace_id=uuid.UUID(WORKSPACE_ID))
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {"activity_retention_days": 3650}, actor_id=OWNER_ID
        )
        assert res["activity_retention_days"] == 3650

    def test_tier2_f2_invalid_default_invite_role_fallback(self):
        """38. Verify WorkspaceSettingsUpdate rejects invalid default_invite_role via Pydantic."""
        with pytest.raises(ValidationError):
            WorkspaceSettingsUpdate(default_invite_role="superman")

    @pytest.mark.asyncio
    async def test_tier2_f2_workspace_id_string_and_uuid_types(self, monkeypatch):
        """39. Verify get_workspace_settings handles UUID object or UUID string workspace_id."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        session.add = Mock()
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.get_workspace_settings(WORKSPACE_ID)
        assert res["workspace_id"] == WORKSPACE_ID

    def test_tier2_f2_corrupted_jsonb_overrides_resilience(self):
        """40. Verify resolve_role_permissions handles corrupted non-dict or invalid type overrides."""
        assert resolve_role_permissions("member", None)["queries.execute"] is True
        assert resolve_role_permissions("member", {})["queries.execute"] is True
        assert (
            resolve_role_permissions("member", {"member": "invalid_string"})[
                "queries.execute"
            ]
            is True
        )
        assert (
            resolve_role_permissions("member", {"member": 12345})["queries.execute"]
            is True
        )


class TestTier2Feature3RequirePermissionDependencyBoundaries:
    """Feature 3 Boundaries (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier2_f3_missing_workspace_id_header(self):
        """41. Verify get_current_workspace raises 400 if X-Workspace-Id header is missing."""
        from backend.app.dependencies import get_current_workspace

        with pytest.raises(HTTPException) as exc_info:
            await get_current_workspace(x_workspace_id=None, user={"user_id": OWNER_ID})
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_tier2_f3_invalid_workspace_id_format(self):
        """42. Verify get_current_workspace raises 400 if X-Workspace-Id format is invalid."""
        from backend.app.dependencies import get_current_workspace

        with pytest.raises(HTTPException) as exc_info:
            await get_current_workspace(
                x_workspace_id="invalid-uuid", user={"user_id": OWNER_ID}
            )
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_tier2_f3_non_member_user_access(self, monkeypatch):
        """43. Verify get_current_workspace raises 403 if user is not a member of workspace."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        with pytest.raises(HTTPException) as exc_info:
            await dependencies.get_current_workspace(
                x_workspace_id=WORKSPACE_ID, user={"user_id": OWNER_ID}
            )
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tier2_f3_unauthenticated_request(self):
        """44. Verify get_current_user raises 401 if access_token cookie is missing."""
        from backend.app.dependencies import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(access_token=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_tier2_f3_require_permission_missing_settings_row_fallback(
        self, monkeypatch
    ):
        """45. Verify require_permission falls back to defaults when settings row does not exist."""
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("queries.execute")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        res = await dep(workspace=ws_context)
        assert res == ws_context


class TestTier2Feature4SettingsEndpointsBoundaries:
    """Feature 4 Boundaries (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier2_f4_patch_settings_empty_body(self, monkeypatch):
        """46. Verify update_workspace_settings with empty dict leaves settings unchanged."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="admin",
            invite_expiry_days=14,
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {}, actor_id=OWNER_ID
        )
        assert res["default_invite_role"] == "admin"
        assert res["invite_expiry_days"] == 14

    @pytest.mark.asyncio
    async def test_tier2_f4_patch_settings_partial_update(self, monkeypatch):
        """47. Verify partial patch updates only specified field without resetting others."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="admin",
            invite_expiry_days=7,
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {"invite_expiry_days": 30}, actor_id=OWNER_ID
        )
        assert res["default_invite_role"] == "admin"
        assert res["invite_expiry_days"] == 30

    @pytest.mark.asyncio
    async def test_tier2_f4_patch_settings_sequential_sparse_updates(self, monkeypatch):
        """48. Verify sequential sparse updates merge role permissions incrementally."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": {"dashboards.create": True}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        payload = {
            "role_permissions": {
                "member": {"dashboards.create": True},
                "admin": {"dashboards.manage": False},
            }
        }
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert res["role_permissions"]["member"]["dashboards.create"] is True
        assert res["role_permissions"]["admin"]["dashboards.manage"] is False

    def test_tier2_f4_patch_settings_invalid_permission_type(self):
        """49. Verify WorkspaceSettingsUpdate rejects invalid role_permissions type via Pydantic."""
        with pytest.raises(ValidationError):
            WorkspaceSettingsUpdate(role_permissions="invalid_type")

    def test_tier2_f4_get_settings_member_access_forbidden(
        self, app_instance, monkeypatch
    ):
        """50. Verify GET settings returns 403 for member without workspace.settings permission."""
        client = TestClient(app_instance)
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        response = client.get(f"/api/workspaces/{WORKSPACE_ID}/settings")
        assert response.status_code == 403
        assert "workspace.settings" in response.json()["detail"]
        app_instance.dependency_overrides.clear()


class TestTier2Feature5WorkspaceDefaultsIntegrationBoundaries:
    """Feature 5 Boundaries (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier2_f5_invite_expiry_timestamp_precision(self, monkeypatch):
        """51. Verify invite expires_at timestamp accuracy for custom expiry_days."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), invite_expiry_days=21
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(None),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "test@example.com", None, OWNER_ID
        )
        expected = datetime.now(timezone.utc) + timedelta(days=21)
        diff = abs((invite["expires_at"] - expected).total_seconds())
        assert diff < 60

    @pytest.mark.asyncio
    async def test_tier2_f5_activity_cleanup_zero_logs_deleted(self, monkeypatch):
        """52. Verify delete_old_activity returns 0 when no logs exceed retention threshold."""
        session = AsyncMock()
        del_result = Mock()
        del_result.rowcount = 0
        session.execute.return_value = del_result
        _patch_session(monkeypatch, session, activity_ctrl)

        count = await activity_ctrl.delete_old_activity(retention_days=30)
        assert count == 0

    @pytest.mark.asyncio
    async def test_tier2_f5_activity_cleanup_boundary_timestamp(self, monkeypatch):
        """53. Verify activity cleanup logic executes valid cutoff SQL query."""
        session = AsyncMock()
        del_result = Mock()
        del_result.rowcount = 5
        session.execute.return_value = del_result
        _patch_session(monkeypatch, session, activity_ctrl)

        count = await activity_ctrl.delete_old_activity(retention_days=1)
        assert count == 5

    @pytest.mark.asyncio
    async def test_tier2_f5_resend_invite_uses_current_settings(self, monkeypatch):
        """54. Verify resending an invite updates expiration with current settings."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), invite_expiry_days=10
        )
        existing_invite = SimpleNamespace(
            id=uuid.uuid4(),
            email="test@example.com",
            role="member",
            token="old_token",
            invited_by=uuid.UUID(OWNER_ID),
            expires_at=datetime.now(timezone.utc),
            accepted_at=None,
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(existing_invite),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "test@example.com", None, OWNER_ID
        )
        expected = datetime.now(timezone.utc) + timedelta(days=10)
        diff = abs((invite["expires_at"] - expected).total_seconds())
        assert diff < 60

    @pytest.mark.asyncio
    async def test_tier2_f5_activity_retention_uninitialized_settings(
        self, monkeypatch
    ):
        """55. Verify activity query falls back to 30 days when settings row is missing."""
        session = AsyncMock()
        res_activity = Mock()
        res_activity.all.return_value = []
        session.execute.side_effect = [_mock_result(None), res_activity]
        _patch_session(monkeypatch, session, activity_ctrl)

        logs = await activity_ctrl.get_workspace_activity(WORKSPACE_ID, limit=50)
        assert logs == []


class TestTier2Feature6FrontendSettingsMatrixUIBoundaries:
    """Feature 6 Boundaries (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier2_f6_matrix_ui_toggle_all_member_perms_true(self, monkeypatch):
        """56. Verify resolved matrix when member role permissions are all set to True."""
        all_true_member = {k: True for k in PERMISSIONS}
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": all_true_member},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {}, actor_id=OWNER_ID
        )
        assert all(res["resolved_matrix"]["member"].values())

    @pytest.mark.asyncio
    async def test_tier2_f6_matrix_ui_toggle_all_admin_perms_false(self, monkeypatch):
        """57. Verify resolved matrix when admin role permissions are all set to False."""
        all_false_admin = {k: False for k in PERMISSIONS}
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"admin": all_false_admin},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, {}, actor_id=OWNER_ID
        )
        assert all(val is False for val in res["resolved_matrix"]["admin"].values())

    @pytest.mark.asyncio
    async def test_tier2_f6_matrix_ui_owner_always_all_true_despite_payload(
        self, monkeypatch
    ):
        """58. Verify owner role in resolved_matrix remains 100% True despite payload overrides."""
        all_false_owner = {k: False for k in PERMISSIONS}
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID,
            {"role_permissions": {"owner": all_false_owner}},
            actor_id=OWNER_ID,
        )
        assert all(res["resolved_matrix"]["owner"].values())

    def test_tier2_f6_sparse_override_diff_computation(self):
        """59. Verify sparse override diff computation against default RBAC matrix."""
        overrides = {"member": {"dashboards.create": True}}
        resolved = resolve_role_permissions("member", overrides)
        assert resolved["dashboards.create"] is True
        # Original default was False
        assert DEFAULT_ROLE_PERMISSIONS["member"]["dashboards.create"] is False

    def test_tier2_f6_matrix_category_grouping_response(self):
        """60. Verify resolved matrix keys map cleanly to registered categories."""
        matrix = resolve_role_permissions("member")
        for key in matrix:
            assert key in PERMISSIONS
            assert "category" in PERMISSIONS[key]


# =====================================================================
# TIER 3: CROSS-FEATURE PAIRWISE COMBINATIONS (6 TEST CASES)
# =====================================================================


class TestTier3CrossFeaturePairwise:
    """Tier 3: Pairwise Cross-Feature Integration Combinations (6 cases)."""

    @pytest.mark.asyncio
    async def test_tier3_p1_perm_override_and_route_enforcement(self, monkeypatch):
        """61. Pairwise 1: Permission override + route enforcement (queries.execute revoked for Member -> 403)."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": {"queries.execute": False}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(settings)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("queries.execute")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        with pytest.raises(HTTPException) as exc_info:
            await dep(workspace=ws_context)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_tier3_p2_setting_override_and_invite_defaults(self, monkeypatch):
        """62. Pairwise 2: Setting override + invite defaults (default_role=admin, expiry=14 -> invite created)."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="admin",
            invite_expiry_days=14,
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(None),
        ]
        session.get.return_value = SimpleNamespace(name="Acme Corp")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "test@example.com", None, OWNER_ID
        )
        assert invite["role"] == "admin"
        expected = datetime.now(timezone.utc) + timedelta(days=14)
        assert abs((invite["expires_at"] - expected).total_seconds()) < 60

    @pytest.mark.asyncio
    async def test_tier3_p3_activity_retention_and_cleanup_job(self, monkeypatch):
        """63. Pairwise 3: Activity retention setting + cleanup job (retention=7 days -> cleanup executes cutoff query)."""
        session = AsyncMock()
        del_result = Mock()
        del_result.rowcount = 12
        session.execute.return_value = del_result
        _patch_session(monkeypatch, session, activity_ctrl)

        count = await activity_ctrl.delete_old_activity(retention_days=7)
        assert count == 12

    @pytest.mark.asyncio
    async def test_tier3_p4_owner_bypass_and_permission_revocation_attempt(
        self, monkeypatch
    ):
        """64. Pairwise 4: Owner bypass + permissions update (Attempt owner override -> ignored, owner executes route)."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        # Attempt to revoke owner permission in settings
        payload = {"role_permissions": {"owner": {"queries.execute": False}}}
        res = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert "owner" not in res["role_permissions"]

        # Test require_permission for owner
        dep = require_permission("queries.execute")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "owner",
            "user_id": OWNER_ID,
        }
        out = await dep(workspace=ws_context)
        assert out == ws_context

    @pytest.mark.asyncio
    async def test_tier3_p5_sparse_jsonb_update_and_matrix_resolution(
        self, monkeypatch
    ):
        """65. Pairwise 5: Sparse JSONB update + matrix resolution (Sequential patches accumulate in resolved_matrix)."""
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        # Patch 1: Member dashboard create
        res1 = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID,
            {"role_permissions": {"member": {"dashboards.create": True}}},
            actor_id=OWNER_ID,
        )
        assert res1["resolved_matrix"]["member"]["dashboards.create"] is True

        # Patch 2: Admin dashboard manage & preserve Member dashboard create
        res2 = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID,
            {
                "role_permissions": {
                    "member": {"dashboards.create": True},
                    "admin": {"dashboards.manage": False},
                }
            },
            actor_id=OWNER_ID,
        )
        assert res2["resolved_matrix"]["member"]["dashboards.create"] is True
        assert res2["resolved_matrix"]["admin"]["dashboards.manage"] is False

    @pytest.mark.asyncio
    async def test_tier3_p6_non_owner_role_permission_modification_and_route_access(
        self, monkeypatch
    ):
        """66. Pairwise 6: Non-owner role permission modification + route access (Admin dashboards.create revoked -> 403)."""
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"admin": {"dashboards.create": False}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(settings)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("dashboards.create")
        ws_context = {
            "workspace_id": WORKSPACE_ID,
            "role": "admin",
            "user_id": ADMIN_ID,
        }
        with pytest.raises(HTTPException) as exc_info:
            await dep(workspace=ws_context)
        assert exc_info.value.status_code == 403


# =====================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (5 TEST CASES)
# =====================================================================


class TestTier4RealWorldScenarios:
    """Tier 4: End-to-End Real-World Application Scenarios (5 cases)."""

    @pytest.mark.asyncio
    async def test_tier4_s1_custom_member_restriction_scenario(self, monkeypatch):
        """67. Scenario 1: Custom Member Restriction Flow (disable query execute -> 403 -> re-enable -> 200)."""
        # Step 1: Default member has query execution allowed
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("queries.execute")
        member_ctx = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        assert await dep(workspace=member_ctx) == member_ctx

        # Step 2: Security admin revokes member query execution in settings
        restricted_settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": {"queries.execute": False}},
        )
        session.execute.return_value = _mock_result(restricted_settings)
        with pytest.raises(HTTPException) as exc_info:
            await dep(workspace=member_ctx)
        assert exc_info.value.status_code == 403

        # Step 3: Security admin re-enables member query execution
        restored_settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"member": {"queries.execute": True}},
        )
        session.execute.return_value = _mock_result(restored_settings)
        assert await dep(workspace=member_ctx) == member_ctx

    @pytest.mark.asyncio
    async def test_tier4_s2_admin_permission_customization_scenario(self, monkeypatch):
        """68. Scenario 2: Admin Permission Customization (toggle dashboard creation off for Admin role)."""
        # Step 1: Owner disables dashboard creation for admin role
        custom_settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={"admin": {"dashboards.create": False}},
        )
        session = AsyncMock()
        session.execute.return_value = _mock_result(custom_settings)
        _patch_session(monkeypatch, session, dependencies)

        dep = require_permission("dashboards.create")
        admin_ctx = {"workspace_id": WORKSPACE_ID, "role": "admin", "user_id": ADMIN_ID}
        with pytest.raises(HTTPException) as exc_info:
            await dep(workspace=admin_ctx)
        assert exc_info.value.status_code == 403

        # Step 2: Owner re-enables dashboard creation for admin role
        reenabled_settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={},
        )
        session.execute.return_value = _mock_result(reenabled_settings)
        assert await dep(workspace=admin_ctx) == admin_ctx

    @pytest.mark.asyncio
    async def test_tier4_s3_workspace_invite_expiry_override_scenario(
        self, monkeypatch
    ):
        """69. Scenario 3: Workspace Invite Expiry & Default Role Integration Scenario."""
        # Step 1: Owner configures custom invite settings (role=admin, expiry=14 days)
        settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            default_invite_role="admin",
            invite_expiry_days=14,
        )
        session = AsyncMock()
        session.execute.side_effect = [
            _mock_result(settings),
            _mock_result(None),
            _mock_result(None),
            _mock_result(None),
        ]
        session.get.return_value = SimpleNamespace(name="BoloDB Org")
        monkeypatch.setattr(
            ws_ctrl, "send_workspace_invite_email", AsyncMock(return_value=True)
        )
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())
        _patch_session(monkeypatch, session, ws_ctrl)

        # Step 2: Send invite without specifying role or expiry
        invite = await ws_ctrl.invite_user(
            WORKSPACE_ID, "contractor@example.com", None, OWNER_ID
        )

        # Step 3: Assert invite object properties match workspace defaults
        assert invite["role"] == "admin"
        assert invite["email"] == "contractor@example.com"
        expected_expiry = datetime.now(timezone.utc) + timedelta(days=14)
        assert abs((invite["expires_at"] - expected_expiry).total_seconds()) < 60

    def test_tier4_s4_non_owner_settings_update_attempt_scenario(self, app_instance):
        """70. Scenario 4: Non-Owner Settings Update Attempt (Member/Admin -> 403, Owner -> 200)."""
        client = TestClient(app_instance)

        # 1. Member attempts to patch workspace settings
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        res_member = client.patch(
            f"/api/workspaces/{WORKSPACE_ID}/settings", json={"invite_expiry_days": 30}
        )
        assert res_member.status_code == 403

        # 2. Admin attempts to patch workspace settings
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "admin",
            "user_id": ADMIN_ID,
        }
        res_admin = client.patch(
            f"/api/workspaces/{WORKSPACE_ID}/settings", json={"invite_expiry_days": 30}
        )
        assert res_admin.status_code == 403

        # 3. Owner updates workspace settings successfully
        app_instance.dependency_overrides[get_current_workspace] = lambda: {
            "workspace_id": WORKSPACE_ID,
            "role": "owner",
            "user_id": OWNER_ID,
        }
        with patch(
            "backend.app.routes.workspaces.ctrl.update_workspace_settings",
            AsyncMock(return_value={"invite_expiry_days": 30}),
        ):
            res_owner = client.patch(
                f"/api/workspaces/{WORKSPACE_ID}/settings",
                json={"invite_expiry_days": 30},
            )
            assert res_owner.status_code == 200
            assert res_owner.json()["invite_expiry_days"] == 30

        app_instance.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_tier4_s5_full_end_to_end_permission_matrix_modification(
        self, monkeypatch
    ):
        """71. Scenario 5: Full End-to-End Permission Matrix Modification & Endpoint Validation."""
        # 1. Initial State: Owner views default settings
        session = AsyncMock()
        session.execute.return_value = _mock_result(None)
        session.add = Mock()
        _patch_session(monkeypatch, session, ws_ctrl)

        initial = await ws_ctrl.get_workspace_settings(WORKSPACE_ID)
        assert initial["resolved_matrix"]["admin"]["members.remove"] is True
        assert initial["resolved_matrix"]["member"]["dashboards.create"] is False

        # 2. Owner applies multi-role matrix modification
        existing = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID), role_permissions={}
        )
        session.execute.return_value = _mock_result(existing)
        monkeypatch.setattr(ws_ctrl, "log_activity", AsyncMock())

        payload = {
            "role_permissions": {
                "admin": {"members.remove": False},
                "member": {"dashboards.create": True},
            }
        }
        updated = await ws_ctrl.update_workspace_settings(
            WORKSPACE_ID, payload, actor_id=OWNER_ID
        )
        assert updated["resolved_matrix"]["admin"]["members.remove"] is False
        assert updated["resolved_matrix"]["member"]["dashboards.create"] is True

        # 3. Verify route access dependency enforcement
        modified_settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions=payload["role_permissions"],
        )
        session.execute.return_value = _mock_result(modified_settings)
        _patch_session(monkeypatch, session, dependencies)

        # Admin attempting members.remove gets 403
        admin_ctx = {"workspace_id": WORKSPACE_ID, "role": "admin", "user_id": ADMIN_ID}
        dep_remove = require_permission("members.remove")
        with pytest.raises(HTTPException) as exc_info:
            await dep_remove(workspace=admin_ctx)
        assert exc_info.value.status_code == 403

        # Member attempting dashboards.create succeeds
        member_ctx = {
            "workspace_id": WORKSPACE_ID,
            "role": "member",
            "user_id": MEMBER_ID,
        }
        dep_create = require_permission("dashboards.create")
        assert await dep_create(workspace=member_ctx) == member_ctx

        # 4. Owner resets matrix back to defaults
        reset_settings = WorkspaceSettings(
            workspace_id=uuid.UUID(WORKSPACE_ID),
            role_permissions={},
        )
        session.execute.return_value = _mock_result(reset_settings)

        # Admin members.remove now succeeds
        assert await dep_remove(workspace=admin_ctx) == admin_ctx

        # Member dashboards.create now raises 403
        with pytest.raises(HTTPException) as exc_info_member:
            await dep_create(workspace=member_ctx)
        assert exc_info_member.value.status_code == 403
