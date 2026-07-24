import logging

from fastapi import APIRouter, Depends, HTTPException
from backend.app.dependencies import (
    require_permission,
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
async def list_databases(workspace=Depends(require_permission("connections.view"))):
    return await mdb.get_recent_connections(workspace["workspace_id"], limit=50)


@router.post("/api/connect")
async def connect(
    req: ConnectReq,
    workspace=Depends(require_permission("connections.manage")),
    _catalog_permission=Depends(require_permission("catalog.view")),
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
    workspace=Depends(require_permission("connections.manage")),
    _catalog_permission=Depends(require_permission("catalog.view")),
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
    workspace=Depends(require_permission("connections.manage")),
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
    workspace=Depends(require_permission("connections.view_schema")),
    db_id: str = Depends(get_current_db_id),
    db=Depends(get_db),
):
    return await ctrl.get_schema(workspace["workspace_id"], db, refresh, db_id=db_id)


@router.post("/api/reconnect")
async def reconnect(
    request_body: dict,
    # Switching to a database the workspace already has is a *use* action, not a
    # *manage* one: reconnect only ever targets a stored connection (looked up by
    # db_id below and 404'd otherwise, using the saved URL — never a caller
    # supplied one), so it can't add new databases. Gating it on connections.view
    # lets members pick between the workspace's databases from the switcher;
    # adding a brand-new connection still requires connections.manage via
    # /api/connect.
    workspace=Depends(require_permission("connections.view")),
    _catalog_permission=Depends(require_permission("catalog.view")),
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
    # Carry the stored alias through, so reconnecting doesn't leave the header
    # and the switcher labelling a named database by its host again.
    req = ConnectReq(db_url=conn["db_url"], alias_name=conn.get("alias_name"))
    return await ctrl.connect(
        db,
        kb,
        cfg,
        req,
        workspace_id=workspace["workspace_id"],
        user_id=workspace.get("user_id"),
    )
