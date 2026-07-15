from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.app.dependencies import (
    get_current_user,
    get_db,
    get_cfg,
    get_kb,
    get_providers,
)
from backend.app.models.api import ConfigUpdate
from backend.app.secrets import get_supabase_url, get_supabase_anon_key
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
async def health():
    pg_status = "connected"
    try:
        from backend.app.pgdatabase import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        pg_status = "disconnected"
    return await ctrl.get_health(pg_status)


@router.get("/api/config/public")
async def public_config():
    return JSONResponse(
        {
            "supabase_url": get_supabase_url(),
            "supabase_anon_key": get_supabase_anon_key(),
        }
    )


@router.post("/api/config")
async def update_config(
    req: ConfigUpdate,
    user_token=Depends(get_current_user),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
):
    return await ctrl.update_config(user_token["user_id"], cfg, providers, req)
