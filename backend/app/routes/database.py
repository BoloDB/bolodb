from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from backend.app.dependencies import get_current_user, get_db, get_kb, get_cfg
from backend.app.models.api import ConnectReq
import backend.app.controllers.database as ctrl
import backend.app.mongodatabase as mdb

router = APIRouter()


@router.post("/api/connect")
async def connect(
    req: ConnectReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
):
    return await ctrl.connect(db, kb, cfg, req, user_id=user_token["user_id"])


@router.post("/api/connect-sample")
async def connect_sample(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
):
    return await ctrl.connect_sample(db, kb, cfg, user_id=user_token["user_id"])


@router.post("/api/disconnect")
async def disconnect(
    user_token=Depends(get_current_user), db=Depends(get_db), cfg=Depends(get_cfg)
):
    user_id = user_token["user_id"]
    return await ctrl.disconnect(user_id, db, cfg)


@router.get("/api/schema")
async def schema(
    refresh: bool = False, user_token=Depends(get_current_user), db=Depends(get_db)
):
    return await ctrl.get_schema(user_token["user_id"], db, refresh)


@router.post("/api/reconnect")
async def reconnect(
    request_body: dict,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
):
    db_id = request_body.get("db_id", "")
    if not db_id:
        raise HTTPException(400, "db_id is required")
    conn = await run_in_threadpool(
        mdb.get_recent_connection_by_db_id, user_token["user_id"], db_id
    )
    if not conn or not conn.get("db_url"):
        raise HTTPException(404, "Saved connection not found")
    req = ConnectReq(db_url=conn["db_url"])
    return await ctrl.connect(db, kb, cfg, req, user_id=user_token["user_id"])
