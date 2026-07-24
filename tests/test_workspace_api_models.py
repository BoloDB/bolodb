"""Tests for the request models in backend/app/models/workspace_api.py.

Workspace-name limits and the bulk-invite cap are enforced here rather than
only in the browser, so a direct API call can't bypass them.
"""

import pytest
from pydantic import ValidationError

from backend.app.models.workspace_api import (
    MAX_BULK_INVITES,
    WORKSPACE_NAME_MAX,
    WorkspaceBulkInviteCreate,
    WorkspaceCreate,
    WorkspaceUpdate,
)


@pytest.mark.parametrize("name", ["Acme", "  Acme Analytics  ", "AB"])
def test_workspace_create_accepts_reasonable_names(name):
    assert WorkspaceCreate(name=name).name == name.strip()


@pytest.mark.parametrize("name", ["", "   ", "A", " A "])
def test_workspace_create_rejects_short_names(name):
    with pytest.raises(ValidationError):
        WorkspaceCreate(name=name)


def test_workspace_create_rejects_overlong_names():
    with pytest.raises(ValidationError):
        WorkspaceCreate(name="x" * (WORKSPACE_NAME_MAX + 1))


def test_workspace_create_accepts_a_name_at_the_limit():
    name = "x" * WORKSPACE_NAME_MAX
    assert WorkspaceCreate(name=name).name == name


def test_workspace_update_allows_omitting_the_name():
    # PATCH with no name is a no-op update, not a validation error.
    assert WorkspaceUpdate().name is None
    assert WorkspaceUpdate(name=None).name is None


def test_workspace_update_validates_a_supplied_name():
    assert WorkspaceUpdate(name="  Acme  ").name == "Acme"
    with pytest.raises(ValidationError):
        WorkspaceUpdate(name="A")


def test_bulk_invite_requires_at_least_one_address():
    with pytest.raises(ValidationError):
        WorkspaceBulkInviteCreate(emails=[])


def test_bulk_invite_caps_the_batch_size():
    ok = [f"user{i}@example.com" for i in range(MAX_BULK_INVITES)]
    assert len(WorkspaceBulkInviteCreate(emails=ok).emails) == MAX_BULK_INVITES
    with pytest.raises(ValidationError):
        WorkspaceBulkInviteCreate(emails=ok + ["one.too.many@example.com"])


def test_bulk_invite_accepts_malformed_addresses_for_per_row_reporting():
    """Validation is deliberately deferred: one bad address must not 422 the
    whole batch — the controller reports it as an ``invalid`` row instead."""
    req = WorkspaceBulkInviteCreate(emails=["good@example.com", "not-an-email"])
    assert req.emails == ["good@example.com", "not-an-email"]
    assert req.role == "member"


def test_bulk_invite_rejects_the_owner_role():
    with pytest.raises(ValidationError):
        WorkspaceBulkInviteCreate(emails=["a@b.com"], role="owner")
