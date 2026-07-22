"""The question→answer pipeline (see docs/02-how-a-question-becomes-an-answer.md).

``run_query`` is the heart of the product: it takes a plain-English question
and returns SQL + results + a confidence signal. The steps, in order:

1. Look up user knowledge: glossary terms + previously verified similar answers.
2. Schema linking: pick only the relevant tables (backend/app/schema_link.py).
3. Generate→validate→execute→repair loop (backend/app/repair.py) with the
   the LLM provider (backend/app/llm.py) as the generator.
4. Score confidence from real signals and log the query.
"""

import asyncio
import logging
import re
import time
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool

from backend.app.llm import LLMError, explain_sql, generate_sql, shortlist_tables
from backend.app.repair import run_repair_loop, schema_validator
from backend.app.schema_link import (
    compact_schema,
    compute_confidence,
    expand_linked_tables,
    extract_table_names_from_prev_query,
    link_relevant_tables,
    model_budget,
)
from backend.app.semantic import filter_catalog
from backend.app.sqlvalidate import validate_sql
import backend.app.pgdatabase as mdb

log = logging.getLogger(__name__)

# Bounds for the self-repair loop: at most 3 generation attempts, and no new
# attempt starts after 60s so the user is never left staring at a spinner.
_MAX_ATTEMPTS = 3
_MAX_SECONDS = 60

# Two-stage linking kicks in above this many tables: a cheap names-only LLM
# pass shortlists candidate tables before local scoring. Below it, local
# scoring alone is accurate enough and the extra call isn't worth the latency.
_SHORTLIST_MIN_TABLES = 30


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


async def run_query(
    workspace_id, db, kb, cfg, providers, session_log, req_data, db_id=None
):
    """
    Generate, validate, and execute SQL for a user's question, with confidence scoring and repair attempts.

    Parameters:
        workspace_id: Identifier of the user whose database and knowledge base are used.
        db: Database connection and schema provider.
        kb: Knowledge base used for glossary, catalog, and verified-answer retrieval.
        cfg: Application configuration.
        providers: LLM provider registry.
        session_log: Query history logger.
        req_data: Request containing the question and optional conversation context.

    Returns:
        A response containing the generated SQL, execution results, confidence information, and repair metadata.

    Raises:
        HTTPException: If no database is connected or the question is empty.
    """
    if not db.connected(workspace_id, db_id=db_id):
        raise HTTPException(409, "No database connected")
    q = req_data.question.strip()
    if not q:
        raise HTTPException(400, "Empty question")
    context = req_data.context

    # Step 1 — user knowledge: confirmed term meanings + similar verified answers.
    db_id = db_id or db.get_db_id(workspace_id)
    glossary = await kb.get_glossary(workspace_id, db_id)
    catalog = await kb.get_catalog(workspace_id, db_id)
    retrieved = await kb.retrieve_similar(workspace_id, db_id, q, k=3)

    # Step 2 — schema linking: budget for the configured model, then pick tables.
    budget = model_budget()
    full_schema = db.get_schema(workspace_id, db_id=db_id)
    dialect = db.get_dialect(workspace_id, db_id=db_id)
    context_tables = (
        extract_table_names_from_prev_query(context[-1].sql, dialect)
        if context
        else set()
    )
    try:
        provider = providers.get(workspace_id)
    except LLMError as e:
        raise HTTPException(503, e.user_message)

    # Two-stage linking (docs/04-schema-linking.md): on big schemas, ask the
    # model which tables might matter from a names-only catalog, then feed the
    # picks into local scoring as a boost. Any failure falls back silently to
    # local-only linking — this stage can only ever add signal.
    shortlist = set()
    if len(full_schema) > _SHORTLIST_MIN_TABLES:
        try:
            shortlist = await shortlist_tables(provider, q, full_schema)
        except Exception:
            log.warning("table shortlist failed; using local scoring only")

    # `linked` is mutable on purpose: schema-retry (below) widens it when a
    # failed attempt shows the model needed a table we didn't send.
    linked = list(
        link_relevant_tables(
            q,
            full_schema,
            glossary,
            retrieved,
            budget["max_tables"],
            context_tables,
            catalog=catalog,
            boost_tables=shortlist,
        )
    )
    # Only the catalog entries for the linked tables go into the prompt.
    prompt_catalog = filter_catalog(catalog, linked)

    # Step 3 — generate→validate→execute→repair.

    async def _generate(feedback):
        # Rebuilt each attempt so schema-retry expansions reach the model.
        schema_text = compact_schema(full_schema, linked, budget["samples"])
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
            catalog=prompt_catalog,
        )

    async def _execute(sql):
        return await run_in_threadpool(db.execute, workspace_id, sql, db_id=db_id)

    def _on_failure(sql, errors):
        nonlocal linked
        added = expand_linked_tables(full_schema, linked, sql, dialect)
        if added:
            linked.extend(added)
            log.info("schema-retry: added %s to the linked tables", added)

    try:
        loop_result = await run_repair_loop(
            _generate,
            schema_validator(full_schema, dialect),
            execute=_execute,
            on_failure=_on_failure,
            max_iterations=_MAX_ATTEMPTS,
            max_seconds=_MAX_SECONDS,
        )
    except LLMError as e:
        log.warning("LLM error during run_query: %s", e.detail)
        out = _failure_payload(e.user_message, linked)
        out["query_id"] = session_log.log_query(db_id, q, out)
        return out
    except Exception:
        log.warning("SQL generation failed during run_query", exc_info=True)
        out = _failure_payload("Could not form a query - try rephrasing", linked)
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
        "tables_used": linked,
        # How many generation attempts the self-repair loop needed (1 = first
        # try worked). Useful for debugging and for the UI to show "auto-fixed".
        "attempts": len(attempts),
        "repaired": loop_result["ok"] and len(attempts) > 1,
    }
    if exec_result.get("error"):
        out["execution_error"] = exec_result["error"]
    out["query_id"] = session_log.log_query(db_id, q, out)
    return out


async def explain(workspace_id, db, providers, req_data, db_id=None):
    """Translate a SQL query into plain English (trust feature)."""
    if not db.connected(workspace_id, db_id=db_id):
        raise HTTPException(409, "No database connected")
    sql = (req_data.sql or "").strip()
    if not sql:
        raise HTTPException(400, "Empty SQL")
    try:
        return await explain_sql(
            providers.get(workspace_id), sql, db.get_dialect(workspace_id)
        )
    except LLMError as e:
        raise HTTPException(502, e.user_message)


async def feedback(workspace_id, db, kb, session_log, req_data, db_id=None):
    """
    Record feedback for a query and update verified knowledge when the feedback is positive.

    Parameters:
        workspace_id: Identifier of the user submitting the feedback.
        db: Database connection manager used to identify the connected database.
        kb: Knowledge base used to store verified queries and retrieve trust information.
        session_log: Session logger used to record the feedback.
        req_data: Feedback data containing the query ID, verdict, reason, question, SQL, and restatement.

    Returns:
        A dictionary containing the operation status and trust level. Positive feedback also includes up to six verified question starters.

    Raises:
        HTTPException: If no database is connected for the user.
    """
    if not db.connected(workspace_id, db_id=db_id):
        raise HTTPException(409, "No database connected")
    session_log.log_feedback(req_data.query_id, req_data.verdict, req_data.reason)
    if req_data.verdict == "correct":
        await kb.add_verified(
            workspace_id,
            db.get_db_id(workspace_id),
            req_data.question,
            req_data.sql,
            req_data.restatement,
        )
    out = {
        "ok": True,
        "trust": await kb.trust_level(workspace_id, db.get_db_id(workspace_id)),
    }
    if req_data.verdict == "correct":
        out["starters"] = [
            v["question"]
            for v in (await kb.get_verified(workspace_id, db.get_db_id(workspace_id)))[
                :6
            ]
        ]
    return out


async def verify(workspace_id, db, kb, req_data, db_id=None):
    """Mark a question and its SQL explanation as verified.

    Parameters:
        workspace_id: Identifier of the user verifying the query.
        db: Database connection used to determine the active database.
        kb: Knowledge base used to store the verified query and calculate trust.
        req_data: Request containing the question, SQL statement, and restatement.

    Returns:
        A dictionary indicating success and the user's updated trust level.

    Raises:
        HTTPException: If no database is connected for the user.
    """
    if not db.connected(workspace_id, db_id=db_id):
        raise HTTPException(409, "No database connected")
    await kb.add_verified(
        workspace_id,
        db.get_db_id(workspace_id),
        req_data.question,
        req_data.sql,
        req_data.restatement,
    )
    return {
        "ok": True,
        "trust": await kb.trust_level(workspace_id, db.get_db_id(workspace_id)),
    }


async def execute(workspace_id, db, req_data, db_id=None):
    """
    Execute the requested SQL statement against the user's connected database.

    Parameters:
        workspace_id: Identifier of the user whose database connection should be used.
        db: Database service used to execute the statement.
        req_data: Request containing the SQL statement.

    Returns:
        dict: The database execution result.

    Raises:
        HTTPException: If no database is connected or the SQL execution returns an error.
    """
    if not db.connected(workspace_id, db_id=db_id):
        raise HTTPException(409, "No database connected")
    res = await run_in_threadpool(db.execute, workspace_id, req_data.sql)
    if "error" in res:
        raise HTTPException(400, res["error"])
    return res


# ── Streaming helpers ──────────────────────────────────────────────


def _generate_hints(question, linked_tables, glossary, retrieved):
    hints = []
    if linked_tables:
        table_list = ", ".join(linked_tables[:4])
        hints.append(f"Scanning tables: {table_list}")
    if glossary:
        g = glossary[0]
        hints.append(f"Translating business term: '{g['term']}'")
        if len(glossary) > 1:
            hints.append(f"Cross-referencing {len(glossary)} glossary definitions")
    if retrieved:
        n = len(retrieved)
        hints.append(f"Reviewing {n} verified query pattern{'s' if n > 1 else ''}")
    ql = question.lower()
    if any(w in ql for w in ["total", "sum", "revenue", "sales"]):
        hints.append("Setting up aggregation with SUM")
    elif any(w in ql for w in ["average", "avg", "mean"]):
        hints.append("Setting up aggregation with AVG")
    elif any(w in ql for w in ["count", "how many", "number of"]):
        hints.append("Setting up COUNT aggregation")
    elif any(w in ql for w in ["top", "best", "highest", "most"]):
        hints.append("Planning ordering with LIMIT")
    elif any(w in ql for w in ["list", "show", "find", "get"]):
        hints.append("Preparing SELECT with filters")
    else:
        hints.append("Analyzing query structure")
    hints.append("Verifying column names against schema")
    hints.append("Building final SQL statement")
    return hints


def _extract_target_from_error(error):
    m = re.search(r"'([^']+)'", error)
    return m.group(1) if m else "query"


def _extract_suggestion(error, schema):
    m = re.search(r"Unknown column: '([^']+)'.*table '([^']+)'", error)
    if m and schema:
        bad_col = m.group(1).lower()
        tbl = m.group(2)
        info = schema.get(tbl) if isinstance(schema, dict) else None
        if info:
            cols = [c["name"] for c in info.get("columns", [])]
            similar = [c for c in cols if c.lower().startswith(bad_col[:3])]
            if similar:
                return f"Available in {tbl}: {', '.join(similar)}"
    return None


def _build_checks(verdict, schema=None):
    if verdict.get("ok"):
        return [
            {
                "target": "query",
                "status": "ok",
                "message": "All tables and columns exist",
            }
        ]
    checks = []
    for e in verdict.get("errors", []):
        checks.append(
            {
                "target": _extract_target_from_error(e),
                "status": "error",
                "message": e,
                "suggestion": _extract_suggestion(e, schema),
            }
        )
    return checks


# ── Streaming query controller ────────────────────────────────────


async def run_query_stream(
    workspace_id, db, kb, cfg, providers, session_log, req_data, db_id=None
):
    """
    Stream the SQL generation, validation, execution, confidence, and result events for a question.

    Parameters:
        workspace_id: Identifier of the requesting user.
        db: Database connection and schema provider.
        kb: Knowledge base used for glossary, catalog, and verified-answer retrieval.
        cfg: Application configuration.
        providers: Collection of user-specific language model providers.
        session_log: Service used to record the completed query.
        req_data: Request containing the question and optional conversation context.

    Yields:
        dict: Progress, error, or final-result event. The final result includes generated SQL,
            execution data, confidence information, and the recorded query identifier.
    """
    if not db.connected(workspace_id, db_id=db_id):
        yield {"kind": "error", "message": "No database connected"}
        return
    q = req_data.question.strip()
    if not q:
        yield {"kind": "error", "message": "Empty question"}
        return
    context = req_data.context
    query_start = time.monotonic()

    dbid = db.get_db_id(workspace_id)
    glossary = await kb.get_glossary(workspace_id, dbid)
    catalog = await kb.get_catalog(workspace_id, dbid)
    retrieved = await kb.retrieve_similar(workspace_id, dbid, q, k=3)
    budget = model_budget()
    full_schema = db.get_schema(workspace_id, db_id=db_id)
    context_tables = (
        extract_table_names_from_prev_query(
            context[-1].sql, db.get_dialect(workspace_id)
        )
        if context
        else set()
    )
    tables = link_relevant_tables(
        q,
        full_schema,
        glossary,
        retrieved,
        budget["max_tables"],
        context_tables,
        catalog=catalog,
    )
    schema_text = compact_schema(full_schema, tables, budget["samples"])
    # Only the catalog entries for the linked tables go into the prompt.
    prompt_catalog = filter_catalog(catalog, tables)
    try:
        provider_obj = providers.get(workspace_id)
    except LLMError as e:
        # Surface the configuration problem (e.g. missing API key) instead of
        # letting it escape the generator and get masked as an internal error.
        yield {"kind": "error", "message": e.user_message}
        return

    yield {
        "kind": "schema_linked",
        "tables": list(full_schema.keys()),
        "linked": tables,
        "glossary": glossary,
        "verified_count": len(retrieved),
    }

    hints = _generate_hints(q, tables, glossary, retrieved)
    max_iterations = _MAX_ATTEMPTS
    feedback = ""
    last_restatement = ""
    exec_result = None
    exec_elapsed = 0

    for attempt in range(1, max_iterations + 1):
        llm_coro = generate_sql(
            provider_obj,
            q,
            schema_text,
            db.get_dialect(workspace_id),
            glossary,
            retrieved,
            budget["max_examples"],
            context,
            feedback=feedback,
            catalog=prompt_catalog,
        )
        llm_task = asyncio.create_task(llm_coro)
        try:
            hint_idx = 0
            while True:
                if time.monotonic() - query_start > _MAX_SECONDS:
                    raise TimeoutError("SQL generation exceeded maximum time limit")
                done, _ = await asyncio.wait([llm_task], timeout=2.5)
                if done:
                    gen_result = llm_task.result()
                    break
                yield {
                    "kind": "hint",
                    "message": hints[hint_idx % len(hints)],
                    "elapsed": round(time.monotonic() - query_start, 1),
                }
                hint_idx += 1
        except asyncio.CancelledError:
            raise
        except LLMError as e:
            log.warning("SQL generation failed during streaming: %s", e, exc_info=True)
            yield {"kind": "error", "message": e.user_message}
            return
        except Exception as e:
            log.warning("SQL generation failed during streaming: %s", e, exc_info=True)
            yield {"kind": "error", "message": "Query generation failed"}
            return
        finally:
            if not llm_task.done():
                llm_task.cancel()

        sql = (gen_result.get("sql") or "").strip()
        restatement = (gen_result.get("restatement") or "").strip()
        last_restatement = restatement

        if not sql:
            yield {"kind": "error", "message": "Model returned empty SQL"}
            return

        yield {"kind": "sql", "attempt": attempt, "sql": sql}

        verdict = validate_sql(sql, full_schema, db.get_dialect(workspace_id))
        checks = _build_checks(verdict, full_schema)
        passed = verdict.get("ok", False)

        yield {
            "kind": "validation",
            "attempt": attempt,
            "checks": checks,
            "passed": passed,
        }

        if not passed:
            if attempt < max_iterations:
                errors = verdict.get("errors", [])
                error_msg = errors[0] if errors else "Validation failed"
                yield {
                    "kind": "repair",
                    "attempt": attempt,
                    "total": max_iterations,
                    "error": error_msg,
                    "suggestion": _extract_suggestion(error_msg, full_schema)
                    or "Retrying with corrections",
                    "old_sql": sql,
                }
                fb_lines = [
                    "The previous SQL attempt was:",
                    sql,
                    "",
                    "Problems found:",
                ]
                fb_lines += [f"- {e}" for e in errors]
                fb_lines.append(
                    "Return a corrected SQL query that fixes these problems."
                )
                feedback = "\n".join(fb_lines)
            continue

        # Validation passed — run it. A runtime failure feeds back into the
        # repair loop just like a validation error (parity with run_query), so
        # a query that only breaks at execution still gets another attempt.
        exec_start = time.monotonic()
        try:
            exec_result = await run_in_threadpool(db.execute, workspace_id, sql)
        except Exception:
            log.warning("Query execution failed during streaming", exc_info=True)
            exec_result = {"error": "The query could not be run against the database."}
        exec_elapsed = round(time.monotonic() - exec_start, 3)

        if not exec_result.get("error"):
            break

        if attempt < max_iterations:
            err = exec_result["error"]
            yield {
                "kind": "repair",
                "attempt": attempt,
                "total": max_iterations,
                "error": err,
                "suggestion": "Retrying with corrections",
                "old_sql": sql,
            }
            feedback = "\n".join(
                [
                    "The previous SQL attempt was:",
                    sql,
                    "",
                    "It failed to execute with this error:",
                    f"- {err}",
                    "Return a corrected SQL query that fixes this problem.",
                ]
            )
            continue
        # Out of attempts — fall through and surface the execution error.
        break

    if exec_result is None:
        yield {
            "kind": "error",
            "message": f"Could not generate valid SQL after {max_iterations} attempts",
        }
        return

    yield {
        "kind": "execution",
        "rows": len(exec_result.get("rows", [])),
        "elapsed": exec_elapsed,
        "truncated": exec_result.get("truncated", False),
    }

    confidence, reason, based = compute_confidence(retrieved, exec_result)

    yield {
        "kind": "confidence",
        "level": confidence,
        "reason": reason,
        "based_on_verified": based,
    }

    out = {
        "answered": True,
        "sql": sql,
        "restatement": last_restatement,
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
    out["query_id"] = session_log.log_query(db.get_db_id(workspace_id), q, out)

    # Persist to query history so the dashboard and history reflect streamed
    # queries too (the /api/query/stream route can't save after the response
    # has started streaming, so we do it here — mirrors the non-streaming route).
    # Only link the turn to a conversation the caller actually owns
    conversation_id = req_data.conversation_id
    if conversation_id and not await mdb.conversation_owned_by(
        workspace_id, conversation_id
    ):
        conversation_id = None

    if out.get("sql") and not out.get("execution_error"):
        conf_str = (
            "High"
            if confidence == "high"
            else "Medium"
            if confidence == "medium"
            else "Low"
        )
        try:
            await mdb.save_query(
                workspace_id=workspace_id,
                question=q,
                sql=out["sql"],
                result=out.get("rows", []),
                confidence=conf_str,
                conversation_id=conversation_id,
                restatement=out.get("restatement", ""),
            )
            if conversation_id:
                await mdb.touch_conversation(conversation_id)
        except Exception:
            log.warning("Failed to persist streamed query history", exc_info=True)

    yield {"kind": "result", "data": out}
