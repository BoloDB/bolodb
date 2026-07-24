from typing import Any, Literal, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, field_validator

RoleLiteral = Literal["admin", "member"]

# Kept in sync with the client-side validator in `frontend/src/lib/validation.ts`
# so the two agree on what counts as a usable workspace name.
WORKSPACE_NAME_MIN = 2
WORKSPACE_NAME_MAX = 60

# Upper bound on a single bulk-invite request, so one paste of a huge CSV can't
# turn into an unbounded run of invite emails.
MAX_BULK_INVITES = 100


def _validate_workspace_name(value: str) -> str:
    trimmed = (value or "").strip()
    if len(trimmed) < WORKSPACE_NAME_MIN:
        raise ValueError(
            f"Workspace name must be at least {WORKSPACE_NAME_MIN} characters"
        )
    if len(trimmed) > WORKSPACE_NAME_MAX:
        raise ValueError(
            f"Workspace name must be at most {WORKSPACE_NAME_MAX} characters"
        )
    return trimmed


class WorkspaceCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str) -> str:
        return _validate_workspace_name(v)


class WorkspaceMemberRoleUpdate(BaseModel):
    role: RoleLiteral


class WorkspaceInviteCreate(BaseModel):
    email: EmailStr
    role: RoleLiteral = "member"


class WorkspaceBulkInviteCreate(BaseModel):
    # Plain strings, not EmailStr: a single malformed address should come back
    # as one `invalid` row rather than 422-ing the whole batch.
    emails: list[str] = Field(min_length=1, max_length=MAX_BULK_INVITES)
    role: RoleLiteral = "member"


class WorkspaceOwnershipTransfer(BaseModel):
    user_id: str


class WorkspaceUpdate(BaseModel):
    name: str | None = None

    @field_validator("name")
    @classmethod
    def check_name(cls, v: str | None) -> str | None:
        return None if v is None else _validate_workspace_name(v)


class ActivityLogResponse(BaseModel):
    id: str
    workspace_id: str
    actor_id: Optional[str] = None
    actor_email: Optional[str] = None
    event_type: str
    resource_type: str
    resource_id: Optional[str] = None
    metadata_: dict[str, Any]
    created_at: datetime


class WorkspaceSettingsUpdate(BaseModel):
    default_invite_role: Optional[RoleLiteral] = None
    invite_expiry_days: Optional[int] = Field(None, ge=1, le=365)
    activity_retention_days: Optional[int] = Field(None, ge=1, le=365)
    role_permissions: Optional[dict[str, Any]] = None


class WorkspaceSettingsResponse(BaseModel):
    workspace_id: str
    default_invite_role: str
    invite_expiry_days: int
    activity_retention_days: int
    role_permissions: dict[str, Any]
    resolved_matrix: dict[str, dict[str, bool]]
