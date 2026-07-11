from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from backend.app.dependencies import (
    get_current_user,
    get_db,
    get_cfg,
    get_kb,
    get_providers,
)
from backend.app.models.api import ConfigUpdate
from backend.app.secrets import get_google_client_id
import backend.app.controllers.system as ctrl

router = APIRouter()


@router.get("/api/state")
async def state(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    cfg=Depends(get_cfg),
    kb=Depends(get_kb),
):
    user_id = user_token["user_id"]
    return await ctrl.get_state(user_id, db, cfg, kb)


@router.get("/api/health")
async def health(
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
):
    return await ctrl.get_health(cfg, providers)


@router.get("/api/config/public")
async def public_config():
    return JSONResponse(
        {
            "google_client_id": get_google_client_id(),
        }
    )


@router.post("/api/config")
async def update_config(
    req: ConfigUpdate,
    user_token=Depends(get_current_user),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
):
    return await ctrl.update_config(cfg, providers, req)
