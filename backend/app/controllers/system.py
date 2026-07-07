from backend.app import config as cfgmod
import httpx as _httpx


async def get_state(user_id, db, cfg, kb):
    # s = {"connected": db.connected(user_id), "config": cfgmod.public_config(cfg)}
    config = cfgmod.public_config(cfg)
    config.pop("last_db_url", None)
    s = {"connected": db.connected(user_id), "config": config}
    if db.connected(user_id):
        s["database"] = {
            "url": db.get_info(user_id)["url"],
            "dialect": db.get_dialect(user_id),
            "db_id": db.get_db_id(user_id),
            "tables": db.get_info(user_id)["tables"],
            "has_knowledge": kb.count_verified(db.get_db_id(user_id)) > 0,
        }
        s["trust"] = kb.trust_level(db.get_db_id(user_id))
        s["glossary"] = kb.get_glossary(db.get_db_id(user_id))
        s["starters"] = [
            v["question"] for v in kb.get_verified(db.get_db_id(user_id))[:6]
        ]
    return s


async def check_ollama(cfg):
    url = cfg.get("ollama_url", "http://localhost:11434")
    try:
        async with _httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{url}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
            return {"ok": True, "models": models}
    except Exception:
        return {"ok": False, "error": "Failed to contact Ollama service", "url": url}


async def get_health(cfg, providers):
    ph = await providers.get().health_check()
    return {
        "status": "ok",
        "provider": {"name": cfg["provider"], **ph},
    }


async def update_config(cfg, providers, req_data):
    if req_data.provider:
        cfg["provider"] = req_data.provider
    if req_data.model is not None:
        cfg["model"] = req_data.model
    if req_data.ollama_url:
        cfg["ollama_url"] = req_data.ollama_url
    if req_data.api_key and req_data.provider in ("claude", "openai", "groq"):
        cfg["api_keys"][req_data.provider] = req_data.api_key
    elif req_data.clear_api_key and req_data.provider in ("claude", "openai", "groq"):
        cfg["api_keys"][req_data.provider] = ""

    cfgmod.save_config(cfg)
    providers.reconfigure(cfg)
    h = await providers.get().health_check()
    return {"config": cfgmod.public_config(cfg), "health": h}
