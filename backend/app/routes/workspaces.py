import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from backend.app.dependencies import (
    get_current_user,
    get_current_workspace,
    require_permission,
)
from backend.app.pgdatabase import get_user_by_id
from backend.app.models.workspace_api import (
    WorkspaceBulkInviteCreate,
    WorkspaceCreate,
    WorkspaceMemberRoleUpdate,
    WorkspaceInviteCreate,
    WorkspaceOwnershipTransfer,
    WorkspaceUpdate,
    WorkspaceSettingsUpdate,
)
import backend.app.controllers.workspaces as ctrl
import backend.app.controllers.activity as activity_ctrl

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


@router.get("/api/workspaces/{workspace_id}/settings")
async def get_workspace_settings(
    workspace_id: str,
    workspace=Depends(require_permission("workspace.settings")),
):
    return await ctrl.get_workspace_settings(workspace["workspace_id"])


@router.patch("/api/workspaces/{workspace_id}/settings")
async def update_workspace_settings(
    workspace_id: str,
    req: WorkspaceSettingsUpdate,
    workspace=Depends(get_current_workspace),
):
    if workspace["role"] != "owner":
        raise HTTPException(403, "Owner role required")
    return await ctrl.update_workspace_settings(
        workspace["workspace_id"],
        req.model_dump(exclude_unset=True),
        actor_id=workspace["user_id"],
    )


@router.patch("/api/workspaces/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    req: WorkspaceUpdate,
    workspace=Depends(require_permission("workspace.update")),
):
    return await ctrl.update_workspace(
        workspace["workspace_id"], req.name, actor_id=workspace["user_id"]
    )


@router.delete("/api/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    workspace=Depends(get_current_workspace),
):
    if workspace["role"] != "owner":
        raise HTTPException(403, "Owner role required")
    return await ctrl.delete_workspace(
        workspace["workspace_id"], actor_id=workspace["user_id"]
    )


@router.post("/api/workspaces/{workspace_id}/leave")
async def leave_workspace(
    workspace_id: str,
    workspace=Depends(get_current_workspace),
):
    return await ctrl.leave_workspace(workspace["workspace_id"], workspace["user_id"])


@router.get("/api/workspaces/{workspace_id}/members")
async def list_members(
    workspace_id: str, workspace=Depends(require_permission("members.view"))
):
    return await ctrl.list_members(workspace["workspace_id"])


@router.post("/api/workspaces/{workspace_id}/members")
async def invite_user(
    workspace_id: str,
    req: WorkspaceInviteCreate,
    workspace=Depends(require_permission("members.invite")),
):
    return await ctrl.invite_user(
        workspace["workspace_id"], req.email, req.role, workspace["user_id"]
    )


@router.post("/api/workspaces/{workspace_id}/members/bulk")
async def bulk_invite_users(
    workspace_id: str,
    req: WorkspaceBulkInviteCreate,
    workspace=Depends(require_permission("members.invite")),
):
    return await ctrl.bulk_invite(
        workspace["workspace_id"], req.emails, req.role, workspace["user_id"]
    )


@router.post("/api/workspaces/{workspace_id}/transfer-ownership")
async def transfer_ownership(
    workspace_id: str,
    req: WorkspaceOwnershipTransfer,
    workspace=Depends(get_current_workspace),
):
    if workspace["role"] != "owner":
        raise HTTPException(403, "Owner role required")
    return await ctrl.transfer_ownership(
        workspace["workspace_id"], workspace["user_id"], req.user_id
    )


@router.put("/api/workspaces/{workspace_id}/members/{user_id}")
async def update_member_role(
    workspace_id: str,
    user_id: str,
    req: WorkspaceMemberRoleUpdate,
    workspace=Depends(require_permission("members.update_role")),
):
    return await ctrl.update_member_role(
        workspace["workspace_id"],
        user_id,
        req.role,
        actor_id=workspace["user_id"],
        actor_role=workspace["role"],
    )


@router.delete("/api/workspaces/{workspace_id}/members/{user_id}")
async def remove_member(
    workspace_id: str,
    user_id: str,
    workspace=Depends(require_permission("members.remove")),
):
    return await ctrl.remove_member(
        workspace["workspace_id"],
        user_id,
        actor_id=workspace["user_id"],
        actor_role=workspace["role"],
    )


@router.get("/api/workspaces/{workspace_id}/invites")
async def list_pending_invites(
    workspace_id: str, workspace=Depends(require_permission("members.invite"))
):
    return await ctrl.list_pending_invites(workspace["workspace_id"])


@router.delete("/api/workspaces/{workspace_id}/invites/{invite_id}")
async def rescind_invite(
    workspace_id: str,
    invite_id: str,
    workspace=Depends(require_permission("members.invite")),
):
    return await ctrl.rescind_invite(
        workspace["workspace_id"], invite_id, actor_id=workspace["user_id"]
    )


@router.post("/api/workspaces/{workspace_id}/invites/{invite_id}/resend")
async def resend_invite(
    workspace_id: str,
    invite_id: str,
    workspace=Depends(require_permission("members.invite")),
):
    return await ctrl.resend_invite(
        workspace["workspace_id"], invite_id, actor_id=workspace["user_id"]
    )


@router.get("/api/workspaces/invites/me")
async def get_invites(user=Depends(get_current_user)):
    user_id = user.get("user_id", user.get("sub"))
    user_details = await get_user_by_id(user_id)
    email = user_details.get("email") if user_details else None
    if not email:
        return []
    return await ctrl.get_invites(email)


@router.post("/api/workspaces/invites/{token}/accept")
async def accept_invite(token: str, user=Depends(get_current_user)):
    user_id = user.get("user_id", user.get("sub"))
    user_details = await get_user_by_id(user_id)
    email = user_details.get("email") if user_details else None
    if not email:
        raise HTTPException(400, "User email not found")
    return await ctrl.accept_invite(token, user_id, email)


@router.get("/api/workspaces/{workspace_id}/activity")
async def get_activity_log(
    workspace_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    event_type: str = Query(None),
    workspace=Depends(require_permission("activity.view")),
):
    return await activity_ctrl.get_workspace_activity(
        workspace["workspace_id"], limit, offset, event_type
    )


@router.get("/api/workspaces/{workspace_id}/activity/export")
async def export_activity_log(
    workspace_id: str,
    event_type: str = Query(None),
    workspace=Depends(require_permission("activity.export")),
):
    async def rows():
        buf = io.StringIO()
        writer = csv.writer(buf)

        def flush():
            buf.seek(0)
            chunk = buf.read()
            buf.seek(0)
            buf.truncate(0)
            return chunk

        writer.writerow(
            [
                "timestamp",
                "actor_email",
                "event_type",
                "resource_type",
                "resource_id",
                "details",
            ]
        )
        yield flush()

        async for a in activity_ctrl.iter_workspace_activity(
            workspace["workspace_id"], event_type
        ):
            created = a.get("created_at")
            writer.writerow(
                [
                    created.isoformat() if created else "",
                    a.get("actor_email") or "",
                    a.get("event_type") or "",
                    a.get("resource_type") or "",
                    a.get("resource_id") or "",
                    json.dumps(a.get("metadata_") or {}, default=str),
                ]
            )
            yield flush()

    filename = f"activity-{workspace_id}.csv"
    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
