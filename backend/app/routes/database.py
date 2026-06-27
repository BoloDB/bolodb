from fastapi import APIRouter, Depends
from backend.app.dependencies import get_current_user, get_db, get_kb, get_cfg
from backend.app.models.api import ConnectReq
import backend.app.controllers.database as ctrl

router = APIRouter()

@router.post("/api/connect")
async def connect(
    req: ConnectReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg)
):
    return await ctrl.connect(db, kb, cfg, req)

@router.post("/api/connect-sample")
async def connect_sample(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg)
):
    return await ctrl.connect_sample(db, kb, cfg)

@router.post("/api/disconnect")
async def disconnect(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    cfg=Depends(get_cfg)
):
    return await ctrl.disconnect(db, cfg)

@router.get("/api/schema")
async def schema(
    refresh: bool = False,
    user_token=Depends(get_current_user),
    db=Depends(get_db)
):
    return await ctrl.get_schema(db, refresh)
