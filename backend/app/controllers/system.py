import os
import logging

from fastapi import HTTPException

from backend.app import config as cfgmod
import backend.app.controllers.database as dbctrl
from backend.app.secrets import (
    get_jwt_secret,
    get_supabase_url,
    get_supabase_anon_key,
)
import backend.app.pgdatabase as mdb

log = logging.getLogger(__name__)


async def get_state(user_id, workspace_id, db_id, db, cfg, kb):
    """
    Assemble the user's connection, configuration, onboarding, and knowledge state.

    Parameters:
        user_id: Identifier of the user whose state is requested.
        cfg: Application configuration used to build the public configuration view.

    Returns:
        A dictionary containing user configuration and status, with database and
        knowledge metadata when the user has a connected database.
    """
    config = cfgmod.public_config(cfg)
    config.pop("last_db_url", None)
    user = await mdb.get_user_by_id(user_id)
    # Restore the workspace's database from its stored credentials if this
    # process doesn't hold a live engine for it — otherwise a restart reads to
    # the user as their database having disconnected itself.
    actual_db_id = await dbctrl.ensure_connection(db, workspace_id, db_id)
    s = {
        "connected": bool(actual_db_id),
        "config": config,
        "openrouter_ready": bool(os.environ.get("OPENROUTER_API_KEY")),
        "tour_completed": user.get("tour_completed", False) if user else False,
    }
    if actual_db_id:
        try:
            conn = await mdb.get_recent_connection_by_db_id(workspace_id, actual_db_id)
        except RuntimeError:
            # Only the alias is needed here; an unreadable stored URL must not
            # take down the whole state response.
            log.warning("Could not read stored connection for db_id=%s", actual_db_id)
            conn = None
        s["database"] = {
            "url": db.get_info(workspace_id, actual_db_id)["url"],
            "dialect": db.get_dialect(workspace_id, actual_db_id),
            "db_id": actual_db_id,
            "tables": db.get_info(workspace_id, actual_db_id)["tables"],
            "has_knowledge": (await kb.count_verified(workspace_id, actual_db_id)) > 0,
            "alias_name": conn.get("alias_name") if conn else None,
        }
        s["trust"] = await kb.trust_level(workspace_id, actual_db_id)
        s["glossary"] = await kb.get_glossary(workspace_id, actual_db_id)
        s["starters"] = [
            v["question"]
            for v in (await kb.get_verified(workspace_id, actual_db_id))[:6]
        ]
    return s


async def get_health(pg_status="unknown"):
    """
    Build a health and diagnostics summary for PostgreSQL, environment configuration, and Supabase JWKS reachability.

    Parameters:
        pg_status (str): Current PostgreSQL connection status.

    Returns:
        dict: Health status, PostgreSQL status, environment checks, and Supabase JWKS reachability status.
    """
    env_checks = {
        "JWT_SECRET": bool(get_jwt_secret()) if os.getenv("JWT_SECRET") else False,
        "SUPABASE_URL": bool(get_supabase_url()),
        "SUPABASE_ANON_KEY": bool(get_supabase_anon_key()),
        "SUPABASE_JWT_SECRET": bool(os.getenv("SUPABASE_JWT_SECRET")),
        "DATABASE_URL": bool(os.getenv("DATABASE_URL")),
        "COOKIE_SECURE": os.getenv("COOKIE_SECURE", "false"),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "(not set, using defaults)"),
    }

    jwks_status = "unchecked"
    supabase_url = get_supabase_url()
    if supabase_url:
        try:
            import httpx

            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            resp = await httpx.AsyncClient(timeout=5).get(jwks_url)
            if resp.status_code == 200:
                jwks_status = "reachable"
            else:
                jwks_status = f"unexpected_status:{resp.status_code}"
        except Exception as e:
            jwks_status = f"unreachable:{e.__class__.__name__}"

    return {
        "status": "ok" if pg_status == "connected" else "degraded",
        "postgres": pg_status,
        "env": env_checks,
        "supabase_jwks": jwks_status,
    }


async def set_tour_completed(user_id):
    """Mark the user's tour as completed.

    Parameters:
        user_id: The identifier of the user whose tour is complete.

    Returns:
        dict: A confirmation payload indicating that the tour was completed.

    Raises:
        HTTPException: If the user was not found in the database.
    """
    ok = await mdb.update_user(user_id, tour_completed=True)
    if not ok:
        raise HTTPException(404, "User not found")
    return {"ok": True, "tour_completed": True}


async def update_config(user_id, cfg, providers, req_data):
    """
    Update the persisted configuration with the supported database URL setting.

    Parameters:
        req_data: Request data containing an optional ``last_db_url`` value.

    Returns:
        A dictionary containing the public configuration.
    """
    if req_data.last_db_url is not None:
        cfg["last_db_url"] = req_data.last_db_url
    cfgmod.save_config(cfg)
    return {"config": cfgmod.public_config(cfg)}
