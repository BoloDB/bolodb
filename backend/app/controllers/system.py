import os
import logging

from backend.app import config as cfgmod
from backend.app.secrets import (
    get_jwt_secret,
    get_supabase_url,
    get_supabase_anon_key,
)

log = logging.getLogger(__name__)


async def get_state(user_id, db, cfg, kb):
    config = cfgmod.public_config(cfg, user_id)
    config.pop("last_db_url", None)
    s = {"connected": db.connected(user_id), "config": config}
    if db.connected(user_id):
        s["database"] = {
            "url": db.get_info(user_id)["url"],
            "dialect": db.get_dialect(user_id),
            "db_id": db.get_info(user_id)["db_id"],
            "tables": db.get_info(user_id)["tables"],
            "has_knowledge": kb.count_verified(db.get_db_id(user_id)) > 0,
        }
        s["trust"] = kb.trust_level(db.get_db_id(user_id))
        s["glossary"] = kb.get_glossary(db.get_db_id(user_id))
        s["starters"] = [
            v["question"] for v in kb.get_verified(db.get_db_id(user_id))[:6]
        ]
    return s


async def get_health(pg_status="unknown"):
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


async def update_config(user_id, cfg, providers, req_data):
    """Update AI settings. Gemini is the only provider, so the accepted fields
    are the model choice and the Gemini API key (set or clear)."""
    global_change = False
    cfg["provider"] = "gemini"
    if req_data.model is not None and req_data.model in cfgmod.ALLOWED_MODELS:
        cfg["model"] = req_data.model
        global_change = True
    if req_data.api_key:
        # Encrypted at the boundary and scoped to this user only: the config
        # dict (and therefore the config file) never holds the key in clear
        # text, and no other user's provider can ever pick it up. Decryption
        # happens only when the provider is built (create_provider in
        # backend/app/llm.py).
        cfgmod.set_api_key(cfg, user_id, req_data.api_key)
    elif req_data.clear_api_key:
        cfgmod.clear_api_key(cfg, user_id)

    if global_change:
        providers.reconfigure(cfg)
    else:
        providers.invalidate(user_id)

    cfgmod.save_config(cfg)
    try:
        h = await providers.get(user_id).health_check()
    except Exception:
        log.exception("Health check failed after config update")
        h = {"ok": False, "error": "Health check failed", "models": []}
    return {"config": cfgmod.public_config(cfg, user_id), "health": h}
