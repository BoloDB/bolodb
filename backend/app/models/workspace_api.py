from typing import Literal
from pydantic import BaseModel, EmailStr

RoleLiteral = Literal["admin", "member"]


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceMemberRoleUpdate(BaseModel):
    role: RoleLiteral


class WorkspaceInviteCreate(BaseModel):
    email: EmailStr
    role: RoleLiteral = "member"


class WorkspaceUpdate(BaseModel):
    name: str | None = None
