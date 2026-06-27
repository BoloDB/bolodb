from fastapi import APIRouter, Depends
from backend.app.dependencies import (
    get_current_user,
    get_db,
    get_cfg,
    get_kb,
    get_providers,
)
from backend.app.models.api import ConfigUpdate
import backend.app.controllers.system as ctrl

router = APIRouter()


@router.get("/api/state")
async def state(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    cfg=Depends(get_cfg),
    kb=Depends(get_kb),
):
    return await ctrl.get_state(db, cfg, kb)


@router.get("/api/ollama-check")
async def ollama_check(cfg=Depends(get_cfg)):
    return await ctrl.check_ollama(cfg)


@router.get("/api/health")
async def health(
    cfg=Depends(get_cfg), providers=Depends(get_providers), db=Depends(get_db)
):
    return await ctrl.get_health(cfg, providers, db)


@router.post("/api/config")
async def update_config(
    req: ConfigUpdate,
    user_token=Depends(get_current_user),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
):
    return await ctrl.update_config(cfg, providers, req)
