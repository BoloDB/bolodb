import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_current_workspace
import backend.app.pgdatabase as mdb

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/connections")
async def get_connections(workspace=Depends(get_current_workspace)):
    try:
        connections = await mdb.get_recent_connections(workspace["workspace_id"])
        for c in connections:
            c.pop("db_url", None)
        return {"connections": connections}
    except Exception:
        log.exception("Failed to get recent connections")
        raise HTTPException(500, "Failed to load recent connections")


@router.delete("/api/connections/{connection_id}")
async def delete_connection(
    connection_id: str, workspace=Depends(get_current_workspace)
):
    try:
        deleted = await mdb.delete_recent_connection(
            workspace["workspace_id"], connection_id
        )
        return {"ok": deleted}
    except Exception:
        log.exception("Failed to delete connection")
        raise HTTPException(500, "Failed to delete connection")
