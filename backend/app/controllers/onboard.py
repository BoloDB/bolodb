from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
import asyncio
import logging
from backend.app.semantic import suggest_from_schema
from backend.app.llm import generate_starters
from backend.app.pgdatabase.models import VerifiedQA
from sqlalchemy.dialects.postgresql import insert

log = logging.getLogger(__name__)


async def save(workspace_id, db, kb, req_data):
    """
    Persist onboarding results and initialize the semantic catalog when it is empty.

    Parameters:
        req_data: Onboarding glossary entries and verified starter questions to save.

    Returns:
        A dictionary containing `ok` set to `True` and the user's updated trust level.
    """
    if not db.connected(workspace_id):
        raise HTTPException(409, "No database connected")
    db_id = db.get_db_id(workspace_id)
    if req_data.glossary is not None:
        await kb.set_glossary(
            workspace_id, db_id, [g.model_dump() for g in req_data.glossary]
        )
    for s in req_data.starters:
        await kb.add_verified(
            workspace_id,
            db_id,
            s.question,
            s.sql,
            s.restatement,
        )
    # Seed the semantic catalog (issue #90) with the deterministic backbone —
    # join paths and value-map scaffolding derived straight from the schema —
    # so linking and the prompt benefit immediately. The user can enrich it
    # with AI suggestions and edits from Settings afterwards.
    if await kb.catalog_is_empty(workspace_id, db_id):
        await kb.set_catalog(
            workspace_id, db_id, suggest_from_schema(db.get_schema(workspace_id))
        )
    return {"ok": True, "trust": await kb.trust_level(workspace_id, db_id)}


async def generate_starters_async(workspace_id, db, kb, providers):
    if not db.connected(workspace_id):
        raise HTTPException(409, "No database connected")
    try:
        db_id = db.get_db_id(workspace_id)
        schema_text = db.schema_as_text(workspace_id)
        dialect = db.get_dialect(workspace_id)

        starters = await generate_starters(
            providers.get(workspace_id), schema_text, dialect
        )

        async def _run_starter(s):
            res = await run_in_threadpool(db.execute, workspace_id, s.get("sql", ""))
            s["error"] = res.get("error")
            return s

        starters = list(await asyncio.gather(*[_run_starter(s) for s in starters]))
        # Filter out starters that failed to execute
        valid_starters = [s for s in starters if not s.get("error")]

        seen_q = set()
        deduped = []
        for s in valid_starters:
            if s["question"] not in seen_q:
                seen_q.add(s["question"])
                deduped.append(s)

        if deduped:
            async with kb._session_factory() as session:
                stmt = (
                    insert(VerifiedQA)
                    .values(
                        [
                            {
                                "workspace_id": workspace_id,
                                "db_id": db_id,
                                "question": s["question"],
                                "sql": s["sql"],
                                "restatement": s["restatement"],
                            }
                            for s in deduped
                        ]
                    )
                    .on_conflict_do_nothing(
                        index_elements=["workspace_id", "db_id", "question"]
                    )
                )
                await session.execute(stmt)
                await session.commit()

        # Return the generated list of questions
        return {
            "starters": [s["question"] for s in deduped]
            or [s["question"] for s in valid_starters]
        }
    except Exception:
        log.exception("Failed to generate async starters")
        return {"starters": []}
