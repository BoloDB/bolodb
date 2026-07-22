from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.app.dependencies import (
    get_current_user,
    get_db,
    get_cfg,
    get_kb,
    get_providers,
    get_current_db_id,
)
from backend.app.models.api import ConfigUpdate
from backend.app.secrets import get_supabase_url, get_supabase_anon_key
import backend.app.controllers.system as ctrl

router = APIRouter()


@router.get("/api/state")
async def state(
    user_token=Depends(get_current_user),
    x_workspace_id: str = Header(None),
    x_db_id: str = Depends(get_current_db_id),
    db=Depends(get_db),
    cfg=Depends(get_cfg),
    kb=Depends(get_kb),
):
    """
    Retrieve the application state for the authenticated user.

    Returns:
        The current application state.
    """
    user_id = user_token["user_id"]
    return await ctrl.get_state(user_id, x_workspace_id, x_db_id, db, cfg, kb)


@router.post("/api/tour-complete")
async def tour_complete(
    user_token=Depends(get_current_user),
):
    """Mark the authenticated user's tour as completed."""
    user_id = user_token["user_id"]
    return await ctrl.set_tour_completed(user_id)


@router.get("/api/health")
async def health():
    """
    Check PostgreSQL connectivity and provide application health information.

    Returns:
        JSONResponse: Health information with status code 503 when PostgreSQL is unavailable.
    """
    pg_status = "connected"
    try:
        from backend.app.pgdatabase import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        pg_status = f"disconnected:{e.__class__.__name__}"
    result = await ctrl.get_health(pg_status)
    if pg_status != "connected":
        return JSONResponse(content=result, status_code=503)
    return JSONResponse(content=result)


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
