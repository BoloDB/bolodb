from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import asyncio
from backend.app.llm import generate_glossary, generate_starters


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
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    kb.set_glossary(db.get_db_id(user_id), [g.model_dump() for g in req_data.glossary])
    for s in req_data.starters:
        kb.add_verified(
            db.get_db_id(user_id),
            s.get("question", ""),
            s.get("sql", ""),
            s.get("restatement", ""),
        )
    return {"ok": True, "trust": kb.trust_level(db.get_db_id(user_id))}
