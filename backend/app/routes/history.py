from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from backend.app.dependencies import get_current_user
import backend.app.mongodatabase as db
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history(user_token=Depends(get_current_user)):
    user_id = user_token["user_id"]
    history = await run_in_threadpool(db.get_query_history, user_id)
    return JSONResponse({"history": history})


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, user_token=Depends(get_current_user)):
    user_id = user_token["user_id"]
    success = await run_in_threadpool(db.delete_history_entry, user_id, entry_id)
    if not success:
        raise HTTPException(status_code=404, detail="Entry not found or unauthorized")
    return JSONResponse({"message": "Deleted successfully"})


@router.delete("")
async def clear_history(user_token=Depends(get_current_user)):
    user_id = user_token["user_id"]
    await run_in_threadpool(db.clear_history, user_id)
    return JSONResponse({"message": "Cleared successfully"})
