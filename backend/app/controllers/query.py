"""The question→answer pipeline (see docs/02-how-a-question-becomes-an-answer.md).

``run_query`` is the heart of the product: it takes a plain-English question
and returns SQL + results + a confidence signal. The steps, in order:

1. Look up user knowledge: glossary terms + previously verified similar answers.
2. Schema linking: pick only the relevant tables (backend/app/schema_link.py).
3. Generate→validate→execute→repair loop (backend/app/repair.py) with the
   Gemini provider (backend/app/llm.py) as the generator.
4. Score confidence from real signals and log the query.
"""

import logging

from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.app.llm import LLMError, explain_sql, generate_sql
from backend.app.repair import run_repair_loop, schema_validator
from backend.app.schema_link import (
    compact_schema,
    compute_confidence,
    extract_table_names_from_prev_query,
    link_relevant_tables,
    model_budget,
)

log = logging.getLogger(__name__)

# Bounds for the self-repair loop: at most 3 generation attempts, and no new
# attempt starts after 60s so the user is never left staring at a spinner.
_MAX_ATTEMPTS = 3
_MAX_SECONDS = 60


def _failure_payload(message, tables=None):
    """Response shape for 'we could not produce a working query'. Mirrors the
    success payload's fields so the frontend never meets a missing key."""
    return {
        "answered": True,
        "sql": "",
        "restatement": "",
        "assumptions": [],
        "confidence": "low",
        "confidence_reason": message,
        "based_on_verified": False,
        "execution_error": message,
        "columns": [],
        "rows": [],
        "truncated": False,
        "tables_used": list(tables or []),
        "attempts": 0,
        "repaired": False,
    }


async def run_query(user_id, db, kb, cfg, providers, session_log, req_data):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    q = req_data.question.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    context = req_data.context

    # Step 1 — user knowledge: confirmed term meanings + similar verified answers.
    db_id = db.get_db_id(user_id)
    glossary = kb.get_glossary(db_id)
    retrieved = kb.retrieve_similar(db_id, q, k=3)

    # Step 2 — schema linking: budget for the configured model, then pick tables.
    budget = model_budget(cfg.get("model", ""))
    full_schema = db.get_schema(user_id)
    dialect = db.get_dialect(user_id)
    context_tables = (
        extract_table_names_from_prev_query(context[-1].sql, dialect)
        if context
        else set()
    )
    tables = link_relevant_tables(
        q, full_schema, glossary, retrieved, budget["max_tables"], context_tables
    )
    schema_text = compact_schema(full_schema, tables, budget["samples"])

    # Step 3 — generate→validate→execute→repair.
    provider = providers.get()

    async def _generate(feedback):
        return await generate_sql(
            provider,
            q,
            schema_text,
            dialect,
            glossary,
            retrieved,
            budget["max_examples"],
            context,
            feedback=feedback,
        )

    async def _execute(sql):
        return await run_in_threadpool(db.execute, user_id, sql)

    try:
        loop_result = await run_repair_loop(
            _generate,
            schema_validator(full_schema, dialect),
            execute=_execute,
            max_iterations=_MAX_ATTEMPTS,
            max_seconds=_MAX_SECONDS,
        )
    except LLMError as e:
        log.warning("LLM error during run_query: %s", e.detail)
        out = _failure_payload(e.user_message, tables)
        out["query_id"] = session_log.log_query(db_id, q, out)
        return out
    except Exception:
        log.warning("SQL generation failed during run_query", exc_info=True)
        out = _failure_payload("Could not form a query - try rephrasing", tables)
        out["query_id"] = session_log.log_query(db_id, q, out)
        return out

    attempts = loop_result["attempts"]
    if loop_result["ok"]:
        exec_result = loop_result["result"] or {}
    else:
        last_errors = (attempts[-1].get("errors") if attempts else None) or [
            "Could not form a working query - try rephrasing"
        ]
        exec_result = {"error": "; ".join(last_errors)}

    # Step 4 — confidence from real signals, then log and answer.
    confidence, reason, based = compute_confidence(retrieved, exec_result)
    out = {
        "answered": True,
        "sql": loop_result["sql"],
        "restatement": loop_result["restatement"],
        "assumptions": loop_result.get("assumptions", []),
        "confidence": confidence,
        "confidence_reason": reason,
        "based_on_verified": based,
        "columns": exec_result.get("columns", []),
        "rows": exec_result.get("rows", []),
        "truncated": exec_result.get("truncated", False),
        "tables_used": tables,
        # How many generation attempts the self-repair loop needed (1 = first
        # try worked). Useful for debugging and for the UI to show "auto-fixed".
        "attempts": len(attempts),
        "repaired": loop_result["ok"] and len(attempts) > 1,
    }
    if exec_result.get("error"):
        out["execution_error"] = exec_result["error"]
    out["query_id"] = session_log.log_query(db_id, q, out)
    return out


async def explain(user_id, db, providers, req_data):
    """Translate a SQL query into plain English (trust feature)."""
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    sql = (req_data.sql or "").strip()
    if not sql:
        raise HTTPException(400, "Empty SQL")
    try:
        return await explain_sql(providers.get(), sql, db.get_dialect(user_id))
    except LLMError as e:
        raise HTTPException(502, e.user_message)


async def feedback(user_id, db, kb, session_log, req_data):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    session_log.log_feedback(req_data.query_id, req_data.verdict, req_data.reason)
    if req_data.verdict == "correct":
        kb.add_verified(
            db.get_db_id(user_id), req_data.question, req_data.sql, req_data.restatement
        )
    out = {"ok": True, "trust": kb.trust_level(db.get_db_id(user_id))}
    if req_data.verdict == "correct":
        out["starters"] = [
            v["question"] for v in kb.get_verified(db.get_db_id(user_id))[:6]
        ]
    return out


async def verify(user_id, db, kb, req_data):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    kb.add_verified(
        db.get_db_id(user_id), req_data.question, req_data.sql, req_data.restatement
    )
    return {"ok": True, "trust": kb.trust_level(db.get_db_id(user_id))}


async def execute(user_id, db, req_data):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    res = await run_in_threadpool(db.execute, user_id, req_data.sql)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res
