"""Settings responses must say what the defaults are, not just the outcome.

The permissions UI shows a *minimum role* per capability and marks the ones
still following the workspace default. It can only do that if the backend says
what the default is — otherwise the UI has to keep its own copy of the defaults,
which goes stale the moment the registry changes and then quietly shows a role
the server does not actually grant.
"""

from backend.app.controllers.workspaces import _permission_matrix
from backend.app.permissions import (
    DEFAULT_ROLE_PERMISSIONS,
    MEMBER_DEFAULT_PERMISSIONS,
    PERMISSIONS,
    resolve_role_permissions,
)

ROLE_RANK = ["member", "admin", "owner"]


def min_role(matrix, key):
    """The UI's reading of a matrix: lowest-ranked role granted this capability."""
    for role in ROLE_RANK:
        if matrix[role][key]:
            return role
    return "owner"


def test_default_matrix_covers_every_registered_permission():
    defaults = _permission_matrix(None)
    assert set(defaults) == {"owner", "admin", "member"}
    for role in defaults:
        assert set(defaults[role]) == set(PERMISSIONS), (
            f"{role} is missing capabilities the registry defines"
        )


def test_default_matrix_matches_the_registry_not_a_second_copy():
    defaults = _permission_matrix(None)
    for role in ("owner", "admin", "member"):
        assert defaults[role] == DEFAULT_ROLE_PERMISSIONS[role]


def test_defaults_are_already_rank_ordered():
    """No capability may reach a lower role without reaching the higher ones.

    The dropdown can only express "this role and above". A default that broke
    that ordering could not be displayed faithfully.
    """
    defaults = _permission_matrix(None)
    for key in PERMISSIONS:
        if defaults["member"][key]:
            assert defaults["admin"][key], f"{key}: members have it but admins don't"
        if defaults["admin"][key]:
            assert defaults["owner"][key], f"{key}: admins have it but owners don't"


def test_owners_keep_every_capability_even_when_overridden():
    revoked = {"owner": dict.fromkeys(PERMISSIONS, False), "admin": {}, "member": {}}
    matrix = _permission_matrix(revoked)
    assert all(matrix["owner"].values()), "owner access is not revocable"


def test_a_custom_matrix_differs_from_the_defaults_only_where_overridden():
    overrides = {"member": {"connections.manage": True}}
    resolved = _permission_matrix(overrides)
    defaults = _permission_matrix(None)

    changed = [k for k in PERMISSIONS if resolved["member"][k] != defaults["member"][k]]
    assert changed == ["connections.manage"]
    assert resolved["admin"] == defaults["admin"], "an override must not leak roles"


def test_minimum_role_round_trips_through_the_stored_format():
    """What the dropdown writes must read back as the same selection.

    The UI stores a minimum role by expanding it into per-role booleans; if that
    expansion and the reverse reading disagree, a saved choice comes back as a
    different one.
    """
    for chosen in ROLE_RANK:
        key = "connections.manage"
        overrides = {
            "admin": {key: chosen in ("admin", "member")},
            "member": {key: chosen == "member"},
        }
        assert min_role(_permission_matrix(overrides), key) == chosen


def test_member_defaults_are_read_only_capabilities_only():
    """Defaults should never hand members a capability that changes the workspace."""
    mutating = {
        k
        for k in PERMISSIONS
        if any(
            k.endswith(suffix)
            for suffix in (".manage", ".remove", ".invite", ".update_role", ".settings")
        )
    }
    assert not (MEMBER_DEFAULT_PERMISSIONS & mutating), (
        "members must not get workspace-changing capabilities by default"
    )
    assert resolve_role_permissions("member")["connections.manage"] is False
