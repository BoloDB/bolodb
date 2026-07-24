import uuid
import pytest
from backend.app.permissions import (
    PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    resolve_role_permissions,
    has_permission,
)
from backend.app.models.workspace_settings import WorkspaceSettings
from backend.app.models import WorkspaceSettings as ImportedWorkspaceSettings


def test_permissions_registry_structure():
    """Verify PERMISSIONS dictionary contains 21 capabilities across 7 resources."""
    assert len(PERMISSIONS) == 21, f"Expected 21 permissions, got {len(PERMISSIONS)}"

    expected_categories = {
        "members",
        "connections",
        "catalog",
        "dashboards",
        "queries",
        "activity",
        "workspace_management",
    }
    categories_found = {perm["category"] for perm in PERMISSIONS.values()}
    assert categories_found == expected_categories

    # Verify per-category count
    category_counts = {}
    for perm in PERMISSIONS.values():
        cat = perm["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    assert category_counts["members"] == 4
    assert category_counts["connections"] == 3
    assert category_counts["catalog"] == 2
    assert category_counts["dashboards"] == 3
    assert category_counts["queries"] == 4
    assert category_counts["activity"] == 2
    assert category_counts["workspace_management"] == 3

    # Check structure of each entry
    for key, spec in PERMISSIONS.items():
        assert spec["key"] == key
        assert "name" in spec and isinstance(spec["name"], str)
        assert "category" in spec and isinstance(spec["category"], str)
        assert "description" in spec and isinstance(spec["description"], str)
        assert "default_roles" in spec and isinstance(spec["default_roles"], list)


def test_default_role_permissions():
    """Verify default permission maps for owner, admin, and member."""
    # Owner: all 21 True
    owner_perms = DEFAULT_ROLE_PERMISSIONS["owner"]
    assert len(owner_perms) == 21
    assert all(val is True for val in owner_perms.values())

    # Admin: all 21 True
    admin_perms = DEFAULT_ROLE_PERMISSIONS["admin"]
    assert len(admin_perms) == 21
    assert all(val is True for val in admin_perms.values())

    # Member: exactly 9 True, 12 False
    member_perms = DEFAULT_ROLE_PERMISSIONS["member"]
    assert len(member_perms) == 21

    expected_true_member_keys = {
        "members.view",
        "connections.view",
        "connections.view_schema",
        "catalog.view",
        "dashboards.view",
        "queries.execute",
        "queries.explain",
        "queries.save",
        "workspace.view",
    }

    actual_true_member_keys = {key for key, val in member_perms.items() if val is True}
    assert actual_true_member_keys == expected_true_member_keys
    assert len(actual_true_member_keys) == 9

    false_member_keys = {key for key, val in member_perms.items() if val is False}
    assert len(false_member_keys) == 12


def test_resolve_role_permissions_defaults():
    """Test resolve_role_permissions without overrides."""
    resolved_owner = resolve_role_permissions("owner")
    assert all(resolved_owner.values())

    resolved_admin = resolve_role_permissions("admin")
    assert all(resolved_admin.values())

    resolved_member = resolve_role_permissions("member")
    assert resolved_member["queries.execute"] is True
    assert resolved_member["members.invite"] is False

    resolved_unknown = resolve_role_permissions("guest")
    assert all(val is False for val in resolved_unknown.values())


def test_resolve_role_permissions_with_overrides():
    """Test sparse overrides for roles."""
    # Direct dictionary override
    overrides = {"members.invite": True, "queries.execute": False}
    resolved = resolve_role_permissions("member", overrides)
    assert resolved["members.invite"] is True
    assert resolved["queries.execute"] is False
    assert resolved["catalog.view"] is True  # unchanged default

    # Nested role-keyed override
    role_keyed_overrides = {"member": {"members.invite": True, "catalog.manage": True}}
    resolved_nested = resolve_role_permissions("member", role_keyed_overrides)
    assert resolved_nested["members.invite"] is True
    assert resolved_nested["catalog.manage"] is True
    assert resolved_nested["members.remove"] is False


def test_owner_permission_bypass():
    """Owner permissions are non-editable and always remain True."""
    overrides = {"queries.execute": False, "workspace.update": False}
    resolved = resolve_role_permissions("owner", overrides)
    assert all(val is True for val in resolved.values())

    assert has_permission("owner", overrides, "queries.execute") is True
    assert has_permission("owner", "queries.execute") is True


def test_has_permission_utility():
    """Test has_permission helper with positional and keyword arguments."""
    # Single permission check (no overrides)
    assert has_permission("member", "queries.execute") is True
    assert has_permission("member", "members.invite") is False
    assert has_permission("admin", "members.invite") is True

    # With overrides passed as dict
    overrides = {"members.invite": True}
    assert (
        has_permission("member", overrides=overrides, permission_key="members.invite")
        is True
    )
    assert has_permission("member", overrides, "members.invite") is True

    # Non-existent permission key
    assert has_permission("member", "nonexistent.capability") is False
    assert has_permission("owner", "nonexistent.capability") is False


def test_workspace_settings_model():
    """Verify WorkspaceSettings model schema and defaults."""
    assert WorkspaceSettings.__tablename__ == "workspace_settings"
    assert ImportedWorkspaceSettings is WorkspaceSettings

    dummy_id = uuid.uuid4()
    settings = WorkspaceSettings(workspace_id=dummy_id)

    assert settings.workspace_id == dummy_id
    assert settings.default_invite_role == "member"
    assert settings.invite_expiry_days == 7
    assert settings.activity_retention_days == 30
    assert settings.role_permissions == {}


def test_unknown_role_edge_cases():
    """Test resolution behavior when unknown or invalid role strings are passed."""
    # Unknown role names without overrides resolve to all-False boolean map
    for unknown_role in [
        "guest",
        "operator",
        "auditor",
        "",
        "ADMIN",
        " owner ",
        "MEMBER",
    ]:
        resolved = resolve_role_permissions(unknown_role)
        assert len(resolved) == 21
        assert all(val is False for val in resolved.values()), (
            f"Role '{unknown_role}' did not resolve to all-False"
        )
        assert has_permission(unknown_role, "queries.execute") is False
        assert has_permission(unknown_role, "catalog.view") is False

    # Flat overrides passed for unknown role grant specified capabilities
    resolved_flat = resolve_role_permissions(
        "guest", {"catalog.view": True, "queries.execute": True}
    )
    assert resolved_flat["catalog.view"] is True
    assert resolved_flat["queries.execute"] is True
    assert resolved_flat["members.invite"] is False

    # Role-keyed nested overrides matching unknown role grant specified capabilities
    resolved_nested_match = resolve_role_permissions(
        "guest", {"guest": {"catalog.view": True}}
    )
    assert resolved_nested_match["catalog.view"] is True
    assert resolved_nested_match["members.invite"] is False

    # Role-keyed nested overrides not matching unknown role yield all-False
    resolved_nested_mismatch = resolve_role_permissions(
        "guest", {"admin": {"catalog.view": False}}
    )
    assert all(val is False for val in resolved_nested_mismatch.values())


def test_unknown_permission_key_edge_cases():
    """Test behavior when unknown or non-existent permission keys are queried."""
    unknown_keys = [
        "unknown.key",
        "members.delete_all",
        "catalog.admin",
        "DATABASE.DROP",
        "",
        "   ",
        "queries.execute.sub",
    ]

    for role in ["owner", "admin", "member", "guest"]:
        for key in unknown_keys:
            # has_permission must return False for unknown permission keys across all roles
            assert has_permission(role, key) is False, (
                f"has_permission('{role}', '{key}') returned True, expected False"
            )
            assert has_permission(role, {"catalog.view": True}, key) is False
            assert (
                has_permission(
                    role, overrides={"catalog.view": True}, permission_key=key
                )
                is False
            )

    # Check non-string permission keys
    assert has_permission("member", None) is False
    assert has_permission("owner", None) is False
    assert has_permission("member", 12345) is False


def test_overrides_formats_empty_invalid_nested():
    """Test empty, invalid, flat vs nested role override dictionaries."""
    # 1. Empty dict and None overrides
    assert resolve_role_permissions("admin", {}) == DEFAULT_ROLE_PERMISSIONS["admin"]
    assert (
        resolve_role_permissions("member", None) == DEFAULT_ROLE_PERMISSIONS["member"]
    )

    # 2. Flat overrides vs Role-nested overrides comparison
    flat_override = {"catalog.manage": False}
    resolved_flat = resolve_role_permissions("admin", flat_override)
    assert resolved_flat["catalog.manage"] is False
    assert resolved_flat["catalog.view"] is True

    nested_override = {"admin": {"catalog.manage": False}}
    resolved_nested = resolve_role_permissions("admin", nested_override)
    assert resolved_nested["catalog.manage"] is False
    assert resolved_nested["catalog.view"] is True

    # 3. Multi-role nested overrides dict
    multi_role_overrides = {
        "admin": {"catalog.manage": False},
        "member": {"queries.execute": False, "members.invite": True},
    }
    resolved_admin = resolve_role_permissions("admin", multi_role_overrides)
    assert resolved_admin["catalog.manage"] is False
    assert resolved_admin["queries.execute"] is True  # preserved admin default

    resolved_member = resolve_role_permissions("member", multi_role_overrides)
    assert resolved_member["queries.execute"] is False  # overridden to False
    assert resolved_member["members.invite"] is True  # overridden to True
    assert resolved_member["catalog.manage"] is False  # preserved member default

    # 4. Mismatched nested role override (overrides present for 'member', queried for 'admin')
    mismatched_overrides = {"member": {"catalog.manage": False}}
    resolved_mismatched = resolve_role_permissions("admin", mismatched_overrides)
    assert resolved_mismatched["catalog.manage"] is True  # admin default untouched

    # 5. Non-boolean override values (strings, integers, None) are ignored
    invalid_val_overrides = {
        "catalog.manage": "false",  # string 'false' should not count as boolean False
        "members.invite": 1,  # int 1 should not count as boolean True for override
        "queries.execute": 0,  # int 0 should not count as boolean False
        "dashboards.view": None,  # None should not override
    }
    resolved_invalid_vals = resolve_role_permissions("member", invalid_val_overrides)
    assert resolved_invalid_vals["catalog.manage"] is False  # member default preserved
    assert resolved_invalid_vals["members.invite"] is False  # member default preserved
    assert resolved_invalid_vals["queries.execute"] is True  # member default preserved
    assert resolved_invalid_vals["dashboards.view"] is True  # member default preserved

    # 6. Unknown permission keys in overrides dictionary are ignored
    overrides_with_unknown = {
        "fake.permission": True,
        "members.invite": True,
    }
    resolved_unknown_in_dict = resolve_role_permissions(
        "member", overrides_with_unknown
    )
    assert "fake.permission" not in resolved_unknown_in_dict
    assert resolved_unknown_in_dict["members.invite"] is True


def test_owner_bypass_immutability_thorough():
    """Verify Owner role permissions cannot be overridden under any scenario."""
    # Flat overrides set all permissions to False
    all_false_flat = {perm_key: False for perm_key in PERMISSIONS}
    resolved_owner_flat = resolve_role_permissions("owner", all_false_flat)
    assert len(resolved_owner_flat) == 21
    assert all(val is True for val in resolved_owner_flat.values())

    # Nested role overrides set all permissions to False
    all_false_nested = {"owner": {perm_key: False for perm_key in PERMISSIONS}}
    resolved_owner_nested = resolve_role_permissions("owner", all_false_nested)
    assert len(resolved_owner_nested) == 21
    assert all(val is True for val in resolved_owner_nested.values())

    # Check has_permission for owner with overrides
    for perm_key in PERMISSIONS:
        assert has_permission("owner", all_false_flat, perm_key) is True
        assert has_permission("owner", all_false_nested, perm_key) is True
        assert has_permission("owner", perm_key) is True


def test_non_dict_overrides_handling():
    """Test behavior when non-dict objects are passed as overrides parameter."""
    # 1. Dual invocation format with has_permission (string passed as 2nd arg without 3rd arg)
    assert has_permission("member", "queries.execute") is True
    assert has_permission("member", "members.invite") is False

    # 2. Non-dict overrides in has_permission with permission_key specified
    assert has_permission("member", 12345, "queries.execute") is True
    assert has_permission("member", ["catalog.view"], "queries.execute") is True

    # 3. Direct call to resolve_role_permissions with non-dict truthy overrides
    # Empirical observation: resolve_role_permissions raises AttributeError or TypeError when passed non-dict truthy overrides
    with pytest.raises(AttributeError):
        resolve_role_permissions("member", "non_dict_string_override")

    with pytest.raises(TypeError):
        resolve_role_permissions("member", 12345)

    with pytest.raises(AttributeError):
        resolve_role_permissions("member", ["catalog.view", True])
