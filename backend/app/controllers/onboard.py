from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import asyncio
import logging
from backend.app.semantic import suggest_from_schema
from backend.app.llm import generate_starters
from backend.app.pgdatabase.models import VerifiedQA

log = logging.getLogger(__name__)


async def save(user_id, db, kb, req_data):
    """
    Persist onboarding results and initialize the semantic catalog when it is empty.

    Parameters:
        req_data: Onboarding glossary entries and verified starter questions to save.

    Returns:
        A dictionary containing `ok` set to `True` and the user's updated trust level.
    """
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    db_id = db.get_db_id(user_id)
    if req_data.glossary is not None:
        await kb.set_glossary(
            user_id, db_id, [g.model_dump() for g in req_data.glossary]
        )
    for s in req_data.starters:
        await kb.add_verified(
            user_id,
            db_id,
            s.question,
            s.sql,
            s.restatement,
        )
    # Seed the semantic catalog (issue #90) with the deterministic backbone —
    # join paths and value-map scaffolding derived straight from the schema —
    # so linking and the prompt benefit immediately. The user can enrich it
    # with AI suggestions and edits from Settings afterwards.
    if await kb.catalog_is_empty(user_id, db_id):
        await kb.set_catalog(
            user_id, db_id, suggest_from_schema(db.get_schema(user_id))
        )
    return {"ok": True, "trust": await kb.trust_level(user_id, db_id)}


async def generate_starters_async(user_id, db, kb, providers):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    try:
        db_id = db.get_db_id(user_id)
        schema_text = db.schema_as_text(user_id)
        dialect = db.get_dialect(user_id)

        starters = await generate_starters(providers.get(user_id), schema_text, dialect)

        async def _run_starter(s):
            res = await run_in_threadpool(db.execute, user_id, s.get("sql", ""))
            s["error"] = res.get("error")
            return s

        starters = list(await asyncio.gather(*[_run_starter(s) for s in starters]))
        # Filter out starters that failed to execute
        valid_starters = [s for s in starters if not s.get("error")]

        async with kb._session_factory() as session:
            for s in valid_starters:
                session.add(
                    VerifiedQA(
                        user_id=user_id,
                        db_id=db_id,
                        question=s["question"],
                        sql=s["sql"],
                        restatement=s["restatement"],
                    )
                )
            try:
                await session.commit()
            except Exception:
                await session.rollback()
                raise

        # Return the generated list of questions
        return {"starters": [s["question"] for s in valid_starters]}
    except Exception:
        log.exception("Failed to generate async starters")
        return {"starters": []}
