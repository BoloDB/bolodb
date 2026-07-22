from fastapi import APIRouter, Depends
from backend.app.dependencies import get_current_user, require_role
from backend.app.models.workspace_api import (
    WorkspaceCreate,
    WorkspaceMemberRoleUpdate,
    WorkspaceInviteCreate,
)
import backend.app.controllers.workspaces as ctrl

router = APIRouter()


@router.get("/api/workspaces")
async def list_workspaces(user=Depends(get_current_user)):
    user_id = user.get("user_id", user.get("sub"))
    return await ctrl.list_workspaces(user_id)


@router.post("/api/workspaces")
async def create_workspace(req: WorkspaceCreate, user=Depends(get_current_user)):
    user_id = user.get("user_id", user.get("sub"))
    return await ctrl.create_workspace(user_id, req.name)


@router.get("/api/workspaces/{workspace_id}")
async def get_workspace(workspace_id: str, user=Depends(get_current_user)):
    user_id = user.get("user_id", user.get("sub"))
    return await ctrl.get_workspace(workspace_id, user_id)


@router.get("/api/workspaces/{workspace_id}/members")
async def list_members(workspace_id: str, workspace=Depends(require_role("member"))):
    return await ctrl.list_members(workspace["workspace_id"])


@router.post("/api/workspaces/{workspace_id}/members")
async def invite_user(
    workspace_id: str,
    req: WorkspaceInviteCreate,
    workspace=Depends(require_role("admin")),
):
    return await ctrl.invite_user(
        workspace["workspace_id"], req.email, req.role, workspace["user_id"]
    )


@router.put("/api/workspaces/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: str,
    user_id: str,
    req: WorkspaceMemberRoleUpdate,
    workspace=Depends(require_role("admin")),
):
    return await ctrl.update_member_role(workspace["workspace_id"], user_id, req.role)


@router.delete("/api/workspaces/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str, user_id: str, workspace=Depends(require_role("member"))
):
    # Members can remove themselves, admins can remove anyone
    if workspace["user_id"] != user_id and workspace["role"] not in ["admin", "owner"]:
        from fastapi import HTTPException

        raise HTTPException(403, "Insufficient permissions to remove other members")
    return await ctrl.remove_member(workspace["workspace_id"], user_id)


@router.get("/api/workspaces/invites/me")
async def get_invites(user=Depends(get_current_user)):
    email = user.get("email")
    if not email:
        return []
    return await ctrl.get_invites(email)


@router.post("/api/workspaces/invites/{token}/accept")
async def accept_invite(token: str, user=Depends(get_current_user)):
    user_id = user.get("user_id", user.get("sub"))
    email = user.get("email")
    if not email:
        from fastapi import HTTPException

        raise HTTPException(400, "User email not found in token")
    return await ctrl.accept_invite(token, user_id, email)
