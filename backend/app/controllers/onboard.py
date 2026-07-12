from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import asyncio
from backend.app.llm import generate_glossary, generate_starters
from backend.app.semantic import suggest_from_schema


async def get_glossary(user_id, db, providers):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    try:
        terms = await generate_glossary(providers.get(), db.schema_as_text(user_id))
        return {"glossary": terms}
    except Exception as e:
        raise HTTPException(502, f"LLM error: {e}")


async def get_starters(user_id, db, providers):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    try:
        starters = await generate_starters(
            providers.get(), db.schema_as_text(user_id), db.get_dialect(user_id)
        )

        async def _run_starter(s):
            res = await run_in_threadpool(db.execute, user_id, s.get("sql", ""))
            s["columns"] = res.get("columns", [])
            s["rows"] = res.get("rows", [])[:5]
            s["error"] = res.get("error")
            return s

        starters = list(await asyncio.gather(*[_run_starter(s) for s in starters]))
        return {"starters": starters}
    except Exception as e:
        raise HTTPException(502, f"LLM error: {e}")


async def save(user_id, db, kb, req_data):
    """Persist onboarding results (glossary + verified starters) and seed the
    semantic catalog's deterministic backbone when none exists yet."""
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    db_id = db.get_db_id(user_id)
    kb.set_glossary(db_id, [g.model_dump() for g in req_data.glossary])
    for s in req_data.starters:
        kb.add_verified(
            db_id,
            s.get("question", ""),
            s.get("sql", ""),
            s.get("restatement", ""),
        )
    # Seed the semantic catalog (issue #90) with the deterministic backbone —
    # join paths and value-map scaffolding derived straight from the schema —
    # so linking and the prompt benefit immediately. The user can enrich it
    # with AI suggestions and edits from Settings afterwards.
    if kb.catalog_is_empty(db_id):
        kb.set_catalog(db_id, suggest_from_schema(db.get_schema(user_id)))
    return {"ok": True, "trust": kb.trust_level(db_id)}
