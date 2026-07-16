import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from backend.app.dependencies import get_current_user
import backend.app.pgdatabase as db

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
async def get_history(
    limit: int = Query(default=100, ge=1, le=500),
    user_token=Depends(get_current_user),
):
    try:
        user_id = user_token["user_id"]
        history = await db.get_query_history(user_id, limit)
        return JSONResponse({"history": history})
    except Exception:
        log.exception("Failed to get query history")
        raise HTTPException(500, "Failed to load query history")


@router.get("/stats")
async def get_stats(user_token=Depends(get_current_user)):
    try:
        user_id = user_token["user_id"]
        stats = await db.get_query_stats(user_id)
        return JSONResponse(stats)
    except Exception:
        log.exception("Failed to get query stats")
        raise HTTPException(500, "Failed to load query statistics")


@router.delete("/{entry_id}")
async def delete_entry(entry_id: str, user_token=Depends(get_current_user)):
    try:
        user_id = user_token["user_id"]
        success = await db.delete_history_entry(user_id, entry_id)
        if not success:
            raise HTTPException(
                status_code=404, detail="Entry not found or unauthorized"
            )
        return JSONResponse({"message": "Deleted successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete history entry")
        raise HTTPException(500, "Failed to delete history entry")


@router.delete("")
async def clear_history(user_token=Depends(get_current_user)):
    try:
        user_id = user_token["user_id"]
        await db.clear_history(user_id)
        return JSONResponse({"message": "Cleared successfully"})
    except Exception:
        log.exception("Failed to clear history")
        raise HTTPException(500, "Failed to clear history")
