import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_current_workspace
from pydantic import BaseModel
import backend.app.pgdatabase as mdb


class ConnectionUpdate(BaseModel):
    alias_name: str | None


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


@router.patch("/api/connections/{connection_id}")
async def update_connection(
    connection_id: str, req: ConnectionUpdate, workspace=Depends(get_current_workspace)
):
    try:
        updated = await mdb.update_recent_connection_alias(
            workspace["workspace_id"], connection_id, req.alias_name
        )
        if not updated:
            raise HTTPException(404, "Connection not found")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update connection alias")
        raise HTTPException(500, "Failed to update connection")
