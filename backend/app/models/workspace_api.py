from pydantic import BaseModel, EmailStr


class WorkspaceCreate(BaseModel):
    name: str


class WorkspaceMemberRoleUpdate(BaseModel):
    role: str


class WorkspaceInviteCreate(BaseModel):
    email: EmailStr
    role: str = "member"
