from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from backend.app.dependencies import get_current_user
from starlette.concurrency import run_in_threadpool
import backend.app.controllers.conversations as ctrl

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


class CreateConversationReq(BaseModel):
    title: str = ""
    database_id: str | None = None


class RenameConversationReq(BaseModel):
    title: str


@router.get("")
async def list_conversations(user_token=Depends(get_current_user)):
    user_id = user_token["user_id"]
    convs = await run_in_threadpool(ctrl.list_conversations, user_id)
    return JSONResponse({"conversations": convs})


@router.post("")
async def create_conversation(
    req: CreateConversationReq,
    user_token=Depends(get_current_user),
):
    user_id = user_token["user_id"]
    conv = await run_in_threadpool(
        ctrl.create_conversation,
        user_id,
        title=req.title,
        database_id=req.database_id,
    )
    return JSONResponse(conv)


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_token=Depends(get_current_user),
):
    user_id = user_token["user_id"]
    conv = await run_in_threadpool(ctrl.get_conversation, user_id, conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return JSONResponse(conv)


@router.patch("/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    req: RenameConversationReq,
    user_token=Depends(get_current_user),
):
    user_id = user_token["user_id"]
    success = await run_in_threadpool(
        ctrl.rename_conversation, user_id, conversation_id, req.title
    )
    if not success:
        raise HTTPException(
            status_code=404, detail="Conversation not found or unauthorized"
        )
    return JSONResponse({"message": "Renamed successfully"})


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_token=Depends(get_current_user),
):
    user_id = user_token["user_id"]
    success = await run_in_threadpool(
        ctrl.delete_conversation, user_id, conversation_id
    )
    if not success:
        raise HTTPException(
            status_code=404, detail="Conversation not found or unauthorized"
        )
    return JSONResponse({"message": "Deleted successfully"})


@router.delete("")
async def clear_conversations(user_token=Depends(get_current_user)):
    user_id = user_token["user_id"]
    await run_in_threadpool(ctrl.clear_conversations, user_id)
    return JSONResponse({"message": "Cleared successfully"})
