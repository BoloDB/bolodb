import logging

from fastapi import APIRouter, Depends, HTTPException
from backend.app.dependencies import (
    get_current_workspace,
    require_role,
    get_db,
    get_kb,
    get_cfg,
    get_current_db_id,
)
from backend.app.models.api import ConnectReq
import backend.app.controllers.database as ctrl
import backend.app.pgdatabase as mdb

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/databases")
async def list_databases(workspace=Depends(get_current_workspace)):
    return await mdb.get_recent_connections(workspace["workspace_id"], limit=50)


@router.post("/api/connect")
async def connect(
    req: ConnectReq,
    workspace=Depends(require_role("admin")),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
):
    return await ctrl.connect(
        db,
        kb,
        cfg,
        req,
        workspace_id=workspace["workspace_id"],
        user_id=workspace.get("user_id"),
    )


@router.post("/api/connect-sample")
async def connect_sample(
    workspace=Depends(require_role("admin")),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
):
    return await ctrl.connect_sample(
        db,
        kb,
        cfg,
        workspace_id=workspace["workspace_id"],
        user_id=workspace.get("user_id"),
    )


@router.post("/api/disconnect")
async def disconnect(
    workspace=Depends(require_role("admin")),
    db_id: str = Depends(get_current_db_id),
    db=Depends(get_db),
    cfg=Depends(get_cfg),
):
    return await ctrl.disconnect(
        workspace["workspace_id"],
        db,
        cfg,
        db_id=db_id,
        user_id=workspace.get("user_id"),
    )


@router.get("/api/schema")
async def schema(
    refresh: bool = False,
    workspace=Depends(get_current_workspace),
    db_id: str = Depends(get_current_db_id),
    db=Depends(get_db),
):
    return await ctrl.get_schema(workspace["workspace_id"], db, refresh, db_id=db_id)


@router.post("/api/reconnect")
async def reconnect(
    request_body: dict,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
):
    db_id = request_body.get("db_id", "")
    if not db_id:
        raise HTTPException(400, "db_id is required")
    try:
        conn = await mdb.get_recent_connection_by_db_id(
            workspace["workspace_id"], db_id
        )
    except RuntimeError:
        log.exception("Could not decrypt stored connection for db_id=%s", db_id)
        raise HTTPException(
            409,
            "Saved credentials could not be decrypted — please re-add this connection.",
        )
    if not conn or not conn.get("db_url"):
        raise HTTPException(404, "Saved connection not found")
    req = ConnectReq(db_url=conn["db_url"])
    return await ctrl.connect(
        db,
        kb,
        cfg,
        req,
        workspace_id=workspace["workspace_id"],
        user_id=workspace.get("user_id"),
    )
