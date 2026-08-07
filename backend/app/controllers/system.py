import os
import logging
import time

import httpx
from fastapi import HTTPException

from backend.app import config as cfgmod
import backend.app.controllers.database as dbctrl
from backend.app.secrets import (
    get_cookie_secure,
    get_jwt_secret,
    get_supabase_url,
    get_supabase_anon_key,
)
import backend.app.pgdatabase as mdb

log = logging.getLogger(__name__)


# ── JWKS reachability probe ─────────────────────────────────────────────
# /api/health is polled by the container healthcheck every 10-30s. Probing
# Supabase on each of those calls means a third-party network round trip on a
# fixed timer forever, and it made the endpoint take 1.8-3.2s. Worse, the old
# code built an httpx.AsyncClient per call and never closed it, so every probe
# leaked its connection pool.
#
# Reachability is not something that changes between two polls seconds apart,
# so cache the answer briefly and share one client. A liveness probe should be
# cheap; the diagnostic value survives a short TTL.
_JWKS_PROBE_TTL_SECONDS = 60.0
_jwks_probe_cache: tuple[str, str, float] | None = None  # (url, status, checked_at)
_jwks_http_client: httpx.AsyncClient | None = None


def _get_jwks_http_client() -> httpx.AsyncClient:
    global _jwks_http_client
    if _jwks_http_client is None or _jwks_http_client.is_closed:
        _jwks_http_client = httpx.AsyncClient(timeout=5)
    return _jwks_http_client


async def close_jwks_http_client() -> None:
    """Release the shared probe client on shutdown."""
    global _jwks_http_client, _jwks_probe_cache
    if _jwks_http_client is not None and not _jwks_http_client.is_closed:
        await _jwks_http_client.aclose()
    _jwks_http_client = None
    _jwks_probe_cache = None


async def _probe_jwks(supabase_url: str) -> str:
    """Report whether the Supabase JWKS endpoint answers, cached for a short TTL."""
    global _jwks_probe_cache

    now = time.monotonic()
    if _jwks_probe_cache is not None:
        cached_url, cached_status, checked_at = _jwks_probe_cache
        if cached_url == supabase_url and (now - checked_at) < _JWKS_PROBE_TTL_SECONDS:
            return cached_status

    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    try:
        resp = await _get_jwks_http_client().get(jwks_url)
        if resp.status_code == 200:
            status = "reachable"
        else:
            status = f"unexpected_status:{resp.status_code}"
    except Exception as e:
        status = f"unreachable:{e.__class__.__name__}"

    _jwks_probe_cache = (supabase_url, status, now)
    return status


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
        # The resolved value, not the raw env var. Reporting the string as
        # written would say "false" for an unset deployment that is in fact
        # issuing Secure cookies — the one place an operator looks to check
        # this should not be the one place that disagrees with the code.
        "COOKIE_SECURE": get_cookie_secure(),
        "CORS_ORIGINS": os.getenv("CORS_ORIGINS", "(not set, using defaults)"),
    }

    jwks_status = "unchecked"
    supabase_url = get_supabase_url()
    if supabase_url:
        jwks_status = await _probe_jwks(supabase_url)

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
