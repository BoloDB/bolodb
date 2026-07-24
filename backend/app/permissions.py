"""
RBAC Permissions Registry and Resolution Utilities for BoloDB.

Defines 21 fine-grained capabilities categorized across 7 resources:
- members: members.view, members.invite, members.update_role, members.remove
- connections: connections.view, connections.manage, connections.view_schema
- catalog: catalog.view, catalog.manage
- dashboards: dashboards.view, dashboards.create, dashboards.manage
- queries: queries.execute, queries.explain, queries.save, queries.delete_saved
- activity: activity.view, activity.export
- workspace_management: workspace.view, workspace.update, workspace.settings
"""

from typing import Any, Dict, Optional, Union

PERMISSIONS: Dict[str, Dict[str, Any]] = {
    # Resource: members
    "members.view": {
        "key": "members.view",
        "name": "View Members",
        "category": "members",
        "description": "View workspace member list and member details",
        "default_roles": ["owner", "admin", "member"],
    },
    "members.invite": {
        "key": "members.invite",
        "name": "Invite Members",
        "category": "members",
        "description": "Invite new members to join the workspace",
        "default_roles": ["owner", "admin"],
    },
    "members.update_role": {
        "key": "members.update_role",
        "name": "Update Member Roles",
        "category": "members",
        "description": "Change roles of workspace members",
        "default_roles": ["owner", "admin"],
    },
    "members.remove": {
        "key": "members.remove",
        "name": "Remove Members",
        "category": "members",
        "description": "Remove members from the workspace",
        "default_roles": ["owner", "admin"],
    },
    # Resource: connections
    "connections.view": {
        "key": "connections.view",
        "name": "View Connections",
        "category": "connections",
        "description": "View configured database connections",
        "default_roles": ["owner", "admin", "member"],
    },
    "connections.manage": {
        "key": "connections.manage",
        "name": "Manage Connections",
        "category": "connections",
        "description": "Create, edit, or delete database connections",
        "default_roles": ["owner", "admin"],
    },
    "connections.view_schema": {
        "key": "connections.view_schema",
        "name": "View Connection Schema",
        "category": "connections",
        "description": "View schema and metadata for database connections",
        "default_roles": ["owner", "admin", "member"],
    },
    # Resource: catalog
    "catalog.view": {
        "key": "catalog.view",
        "name": "View Catalog",
        "category": "catalog",
        "description": "View data catalog, verified Q&A, and metrics",
        "default_roles": ["owner", "admin", "member"],
    },
    "catalog.manage": {
        "key": "catalog.manage",
        "name": "Manage Catalog",
        "category": "catalog",
        "description": "Create or update data catalog definitions",
        "default_roles": ["owner", "admin"],
    },
    # Resource: dashboards
    "dashboards.view": {
        "key": "dashboards.view",
        "name": "View Dashboards",
        "category": "dashboards",
        "description": "View dashboards and visualization panels",
        "default_roles": ["owner", "admin", "member"],
    },
    "dashboards.create": {
        "key": "dashboards.create",
        "name": "Create Dashboards",
        "category": "dashboards",
        "description": "Create new dashboards and panels",
        "default_roles": ["owner", "admin"],
    },
    "dashboards.manage": {
        "key": "dashboards.manage",
        "name": "Manage Dashboards",
        "category": "dashboards",
        "description": "Edit or delete existing dashboards",
        "default_roles": ["owner", "admin"],
    },
    # Resource: queries
    "queries.execute": {
        "key": "queries.execute",
        "name": "Execute Queries",
        "category": "queries",
        "description": "Execute natural language and SQL queries",
        "default_roles": ["owner", "admin", "member"],
    },
    "queries.explain": {
        "key": "queries.explain",
        "name": "Explain Queries",
        "category": "queries",
        "description": "Generate query explanations and execution plans",
        "default_roles": ["owner", "admin", "member"],
    },
    "queries.save": {
        "key": "queries.save",
        "name": "Save Queries",
        "category": "queries",
        "description": "Save queries for workspace access",
        "default_roles": ["owner", "admin", "member"],
    },
    "queries.delete_saved": {
        "key": "queries.delete_saved",
        "name": "Delete Saved Queries",
        "category": "queries",
        "description": "Delete saved queries",
        "default_roles": ["owner", "admin"],
    },
    # Resource: activity
    "activity.view": {
        "key": "activity.view",
        "name": "View Activity",
        "category": "activity",
        "description": "View workspace activity logs",
        "default_roles": ["owner", "admin"],
    },
    "activity.export": {
        "key": "activity.export",
        "name": "Export Activity",
        "category": "activity",
        "description": "Export workspace activity logs",
        "default_roles": ["owner", "admin"],
    },
    # Resource: workspace_management
    "workspace.view": {
        "key": "workspace.view",
        "name": "View Workspace",
        "category": "workspace_management",
        "description": "View workspace details and configuration",
        "default_roles": ["owner", "admin", "member"],
    },
    "workspace.update": {
        "key": "workspace.update",
        "name": "Update Workspace",
        "category": "workspace_management",
        "description": "Update workspace basic profile details",
        "default_roles": ["owner", "admin"],
    },
    "workspace.settings": {
        "key": "workspace.settings",
        "name": "Manage Workspace Settings",
        "category": "workspace_management",
        "description": "Manage workspace defaults and role permission matrix",
        "default_roles": ["owner", "admin"],
    },
}

MEMBER_DEFAULT_PERMISSIONS: set[str] = {
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

DEFAULT_ROLE_PERMISSIONS: Dict[str, Dict[str, bool]] = {
    "owner": {perm_key: True for perm_key in PERMISSIONS},
    "admin": {perm_key: True for perm_key in PERMISSIONS},
    "member": {
        perm_key: (perm_key in MEMBER_DEFAULT_PERMISSIONS) for perm_key in PERMISSIONS
    },
}


def resolve_role_permissions(
    role: str, overrides: Optional[Dict[str, Any]] = None
) -> Dict[str, bool]:
    """
    Resolve the complete map of permission capabilities for a given role, applying
    sparse overrides if provided.

    The 'owner' role always has all permissions set to True (non-editable bypass).
    """
    if role == "owner":
        return {perm_key: True for perm_key in PERMISSIONS}

    base = dict(
        DEFAULT_ROLE_PERMISSIONS.get(
            role, {perm_key: False for perm_key in PERMISSIONS}
        )
    )

    if not overrides:
        return base

    # Extract role-specific overrides dictionary
    role_overrides = None
    if role in overrides and isinstance(overrides[role], dict):
        role_overrides = overrides[role]
    elif any(k in PERMISSIONS for k in overrides.keys()):
        role_overrides = overrides

    if isinstance(role_overrides, dict):
        for perm_key, enabled in role_overrides.items():
            if perm_key in PERMISSIONS and isinstance(enabled, bool):
                base[perm_key] = enabled

    return base


def has_permission(
    role: str,
    overrides: Optional[Union[Dict[str, Any], str]] = None,
    permission_key: Optional[str] = None,
) -> bool:
    """
    Check if a specific role possesses a fine-grained capability key.

    Supports dual invocation formats:
    - has_permission(role, overrides_dict, "queries.execute")
    - has_permission(role, "queries.execute")  [when no overrides provided]
    - has_permission(role, overrides=overrides_dict, permission_key="queries.execute")
    """
    if isinstance(overrides, str) and permission_key is None:
        permission_key = overrides
        overrides = None

    if not permission_key or permission_key not in PERMISSIONS:
        return False

    if role == "owner":
        return True

    resolved = resolve_role_permissions(
        role, overrides if isinstance(overrides, dict) else None
    )
    return resolved.get(permission_key, False)
