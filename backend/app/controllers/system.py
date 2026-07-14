from backend.app import config as cfgmod


async def get_state(user_id, db, cfg, kb):
    config = cfgmod.public_config(cfg, user_id)
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


async def get_health(user_id, cfg, providers):
    ph = await providers.get(user_id).health_check()
    return {
        "status": "ok",
        "provider": {"name": cfg["provider"], **ph},
    }


async def update_config(user_id, cfg, providers, req_data):
    """Update AI settings. Gemini is the only provider, so the accepted fields
    are the model choice and the Gemini API key (set or clear)."""
    cfg["provider"] = "gemini"
    if req_data.model is not None and req_data.model in cfgmod.ALLOWED_MODELS:
        cfg["model"] = req_data.model
    if req_data.api_key:
        # Encrypted at the boundary and scoped to this user only: the config
        # dict (and therefore the config file) never holds the key in clear
        # text, and no other user's provider can ever pick it up. Decryption
        # happens only when the provider is built (create_provider in
        # backend/app/llm.py).
        cfgmod.set_api_key(cfg, user_id, req_data.api_key)
    elif req_data.clear_api_key:
        cfgmod.clear_api_key(cfg, user_id)

    cfgmod.save_config(cfg)
    providers.invalidate(user_id)
    h = await providers.get(user_id).health_check()
    return {"config": cfgmod.public_config(cfg, user_id), "health": h}
