import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from backend.app.dependencies import get_current_workspace
import backend.app.controllers.conversations as ctrl

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationReq(BaseModel):
    title: str = ""
    database_id: str | None = None


class RenameConversationReq(BaseModel):
    title: str


@router.get("")
async def list_conversations(workspace=Depends(get_current_workspace)):
    try:
        workspace_id = workspace["workspace_id"]
        convs = await ctrl.list_conversations(workspace_id)
        return JSONResponse({"conversations": convs})
    except Exception:
        log.exception("Failed to list conversations")
        raise HTTPException(500, "Failed to load conversations")


@router.post("")
async def create_conversation(
    req: CreateConversationReq,
    workspace=Depends(get_current_workspace),
):
    try:
        workspace_id = workspace["workspace_id"]
        conv = await ctrl.create_conversation(
            workspace_id,
            title=req.title,
            database_id=req.database_id,
        )
        return JSONResponse(conv)
    except Exception:
        log.exception("Failed to create conversation")
        raise HTTPException(500, "Failed to create conversation")


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    workspace=Depends(get_current_workspace),
):
    try:
        workspace_id = workspace["workspace_id"]
        conv = await ctrl.get_conversation(workspace_id, conversation_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return JSONResponse(conv)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get conversation")
        raise HTTPException(500, "Failed to load conversation")


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    req: RenameConversationReq,
    workspace=Depends(get_current_workspace),
):
    try:
        workspace_id = workspace["workspace_id"]
        success = await ctrl.rename_conversation(
            workspace_id, conversation_id, req.title
        )
        if not success:
            raise HTTPException(
                status_code=404, detail="Conversation not found or unauthorized"
            )
        return JSONResponse({"message": "Renamed successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to rename conversation")
        raise HTTPException(500, "Failed to rename conversation")


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    workspace=Depends(get_current_workspace),
):
    try:
        workspace_id = workspace["workspace_id"]
        success = await ctrl.delete_conversation(workspace_id, conversation_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Conversation not found or unauthorized"
            )
        return JSONResponse({"message": "Deleted successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete conversation")
        raise HTTPException(500, "Failed to delete conversation")


@router.delete("")
async def clear_conversations(workspace=Depends(get_current_workspace)):
    try:
        workspace_id = workspace["workspace_id"]
        await ctrl.clear_conversations(workspace_id)
        return JSONResponse({"message": "Cleared successfully"})
    except Exception:
        log.exception("Failed to clear conversations")
        raise HTTPException(500, "Failed to clear conversations")
