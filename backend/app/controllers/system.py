from backend.app import config as cfgmod
from backend.app.database import sanitize_url
import httpx as _httpx


async def get_state(db, cfg, kb):
    s = {"connected": db.connected, "config": cfgmod.public_config(cfg)}
    if db.connected:
        s["database"] = {
            "url": sanitize_url(db.url) if db.url else None,
            "dialect": db.dialect,
            "db_id": db.db_id,
            "tables": db._table_count,
            "has_knowledge": kb.count_verified(db.db_id) > 0,
        }
        s["trust"] = kb.trust_level(db.db_id)
        s["glossary"] = kb.get_glossary(db.db_id)
        s["starters"] = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
    return s


async def check_ollama(cfg):
    url = cfg.get("ollama_url", "http://localhost:11434")
    try:
        async with _httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{url}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "models": models}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)}", "url": url}


async def get_health(cfg, providers, db):
    ph = await providers.get().health_check()
    return {"provider": {"name": cfg["provider"], **ph}, "connected": db.connected}


async def update_config(cfg, providers, req_data):
    if req_data.provider:
        cfg["provider"] = req_data.provider
    if req_data.model is not None:
        cfg["model"] = req_data.model
    if req_data.ollama_url:
        cfg["ollama_url"] = req_data.ollama_url
    if req_data.api_key and req_data.provider in ("claude", "openai", "groq"):
        cfg["api_keys"][req_data.provider] = req_data.api_key

    cfgmod.save_config(cfg)
    providers.reconfigure(cfg)
    h = await providers.get().health_check()
    return {"config": cfgmod.public_config(cfg), "health": h}
