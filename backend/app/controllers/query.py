import logging
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from backend.app.schema_link import (
    model_budget,
    link_relevant_tables,
    compact_schema,
    compute_confidence,
)
from backend.app.llm import generate_sql

log = logging.getLogger(__name__)


async def run_query(db, kb, cfg, providers, session_log, req_data):
    if not db.connected:
        raise HTTPException(409, "No database connected")
    q = req_data.question.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    context = req_data.context
    glossary = kb.get_glossary(db.db_id)
    retrieved = kb.retrieve_similar(db.db_id, q, k=3)
    budget = model_budget(cfg.get("provider", "ollama"), cfg.get("model", ""))
    full_schema = db.get_schema()
    tables = link_relevant_tables(
        q, full_schema, glossary, retrieved, budget["max_tables"]
    )
    schema_text = compact_schema(full_schema, tables, budget["samples"])
    try:
        gen = await generate_sql(
            providers.get(),
            q,
            schema_text,
            db.dialect,
            glossary,
            retrieved,
            budget["max_examples"],
            context,
        )
    except Exception:
        log.warning("SQL generation failed during run_query", exc_info=True)
        out = {
            "answered": True,
            "sql": "",
            "restatement": "",
            "confidence": "low",
            "confidence_reason": "Could not form a query - try rephrasing",
            "based_on_verified": False,
            "execution_error": "Could not form a query - try rephrasing",
            "columns": [],
            "rows": [],
        }
        out["query_id"] = session_log.log_query(db.db_id, q, out)
        return out
    sql = gen.get("sql", "")
    restatement = gen.get("restatement", "")
    exec_result = await run_in_threadpool(db.execute, sql)
    confidence, reason, based = compute_confidence(retrieved, exec_result)
    out = {
        "answered": True,
        "sql": sql,
        "restatement": restatement,
        "confidence": confidence,
        "confidence_reason": reason,
        "based_on_verified": based,
        "columns": exec_result.get("columns", []),
        "rows": exec_result.get("rows", []),
        "truncated": exec_result.get("truncated", False),
        "tables_used": tables,
    }
    if "error" in exec_result:
        out["execution_error"] = exec_result["error"]
    out["query_id"] = session_log.log_query(db.db_id, q, out)
    return out


async def feedback(db, kb, session_log, req_data):
    if not db.connected:
        raise HTTPException(409, "No database connected")
    session_log.log_feedback(req_data.query_id, req_data.verdict, req_data.reason)
    if req_data.verdict == "correct":
        kb.add_verified(db.db_id, req_data.question, req_data.sql, req_data.restatement)
    out = {"ok": True, "trust": kb.trust_level(db.db_id)}
    if req_data.verdict == "correct":
        out["starters"] = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
    return out


async def verify(db, kb, req_data):
    if not db.connected:
        raise HTTPException(409, "No database connected")
    kb.add_verified(db.db_id, req_data.question, req_data.sql, req_data.restatement)
    return {"ok": True, "trust": kb.trust_level(db.db_id)}


async def execute(db, req_data):
    if not db.connected:
        raise HTTPException(409, "No database connected")
    res = await run_in_threadpool(db.execute, req_data.sql)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res
