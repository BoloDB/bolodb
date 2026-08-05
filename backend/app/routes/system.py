from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import text
from backend.app.dependencies import (
    get_current_user,
    get_current_workspace,
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
    verified_workspace_id = None
    if x_workspace_id:
        workspace = await get_current_workspace(x_workspace_id, user_token)
        verified_workspace_id = workspace["workspace_id"]
    return await ctrl.get_state(user_id, verified_workspace_id, x_db_id, db, cfg, kb)


@router.post("/api/tour-complete")
async def tour_complete(
    user_token=Depends(get_current_user),
):
    """Mark the authenticated user's tour as completed."""
    user_id = user_token["user_id"]
    return await ctrl.set_tour_completed(user_id)


async def _postgres_status() -> str:
    try:
        from backend.app.pgdatabase import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        return f"disconnected:{e.__class__.__name__}"
    return "connected"


@router.get("/api/health")
async def health():
    """Readiness probe. Unauthenticated, and says only whether we can serve.

    503 when Postgres is unreachable, which is what the container healthcheck
    and any load balancer in front of this needs to see.
    """
    pg_status = await _postgres_status()
    result = await ctrl.get_health(pg_status)
    if pg_status != "connected":
        return JSONResponse(content=result, status_code=503)
    return JSONResponse(content=result)


def _require_admin(user_token=Depends(get_current_user)):
    """Gate on the global admin role, not merely on being signed in.

    Any signed-up stranger holds a valid session, so authentication alone barely
    narrows the audience for deployment configuration. This is operator data —
    which secrets are set, the CORS allowlist, the Supabase project — and the
    role that exists for operators is the one that should see it.
    """
    if user_token.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin role required")
    return user_token


@router.get("/api/health/diagnostics")
async def health_diagnostics(user_token=Depends(_require_admin)):
    """The operator view of the same thing — behind authentication.

    Everything here was previously served to anyone who asked: which secrets are
    configured, the Supabase project URL, the CORS allowlist, and an outbound
    request to Supabase per call. The first three map which auth paths are live
    for someone deciding where to push; the fourth let a stranger make this
    server talk to a third party on demand.
    """
    pg_status = await _postgres_status()
    result = await ctrl.get_diagnostics(pg_status)
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
