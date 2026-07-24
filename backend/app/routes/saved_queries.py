import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from backend.app.dependencies import require_permission, get_current_user
import backend.app.controllers.dashboards as ctrl

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/saved-queries", tags=["saved_queries"])


class SaveQueryReq(BaseModel):
    name: str
    description: Optional[str] = None
    question: Optional[str] = None
    sql: Optional[str] = None
    columns: Optional[list] = None
    database_id: Optional[str] = None
    visualization_type: str = "table"
    viz_config: Optional[dict] = None
    last_result: Optional[list] = None


class UpdateSavedQueryReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    visualization_type: Optional[str] = None
    viz_config: Optional[dict] = None


@router.get("")
async def list_saved_queries(
    workspace=Depends(require_permission("queries.execute")),
):
    try:
        sqs = await ctrl.list_saved_queries(workspace["workspace_id"])
        return JSONResponse({"saved_queries": sqs})
    except Exception:
        log.exception("Failed to list saved queries")
        raise HTTPException(500, "Failed to load saved queries")


@router.post("")
async def create_saved_query(
    req: SaveQueryReq,
    workspace=Depends(require_permission("queries.save")),
    user=Depends(get_current_user),
):
    try:
        sq = await ctrl.create_saved_query(
            workspace["workspace_id"],
            user["user_id"],
            req.model_dump(exclude_unset=True),
        )
        return JSONResponse(sq)
    except Exception:
        log.exception("Failed to create saved query")
        raise HTTPException(500, "Failed to save query")


@router.get("/{query_id}")
async def get_saved_query(
    query_id: str, workspace=Depends(require_permission("queries.execute"))
):
    try:
        sq = await ctrl.get_saved_query(workspace["workspace_id"], query_id)
        if not sq:
            raise HTTPException(404, "Saved query not found")
        return JSONResponse(sq)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get saved query")
        raise HTTPException(500, "Failed to load saved query")


@router.patch("/{query_id}")
async def update_saved_query(
    query_id: str,
    req: UpdateSavedQueryReq,
    workspace=Depends(require_permission("queries.save")),
):
    try:
        success = await ctrl.update_saved_query(
            workspace["workspace_id"], query_id, req.model_dump(exclude_unset=True)
        )
        if not success:
            raise HTTPException(404, "Saved query not found")
        return JSONResponse({"message": "Updated successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update saved query")
        raise HTTPException(500, "Failed to update saved query")


@router.delete("/{query_id}")
async def delete_saved_query(
    query_id: str, workspace=Depends(require_permission("queries.delete_saved"))
):
    try:
        success = await ctrl.delete_saved_query(workspace["workspace_id"], query_id)
        if not success:
            raise HTTPException(404, "Saved query not found")
        return JSONResponse({"message": "Deleted successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete saved query")
        raise HTTPException(500, "Failed to delete saved query")
