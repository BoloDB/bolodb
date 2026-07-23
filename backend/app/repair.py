"""Generate → validate → (execute) → repair loop for NL→SQL.

Most SQL the model gets wrong is wrong *mechanically* — a hallucinated column, a
dialect quirk, a bad join — and is self-correctable once the model is told what
broke. This module runs a bounded loop that generates a candidate, checks it with
the static validator (backend/app/sqlvalidate.py), optionally executes it, and on
any failure feeds the specific error back into the next generation attempt.

This loop is what answers real questions: ``run_query`` in
backend/app/controllers/query.py wires it up with the OpenRouter provider as the
generator and the live database as the executor. It stays decoupled — callers
inject plain callables (sync or async), which keeps the control flow pure and
unit-testable here.

Callables
---------
``generate(feedback: str) -> dict``  (sync or async)
    Produce a candidate. ``feedback`` is ``""`` on the first attempt and, on
    later attempts, a description of what was wrong with the previous SQL. The
    returned dict is expected to carry at least ``"sql"`` (and usually
    ``"restatement"``).
``validate(sql: str) -> dict``  (sync or async)
    Return ``{"ok": bool, "errors": [str]}``. Use :func:`schema_validator` to
    build one bound to a schema + dialect.
``execute(sql: str) -> dict``  (optional; sync or async)
    Run the SQL. A truthy ``"error"`` key means failure; anything else is treated
    as a successful result. Omit to run validation-only (no execution backstop).
``on_failure(sql: str, errors: [str])``  (optional; sync or async)
    Called after every failed attempt, before the next generation. This is the
    schema-retry hook: the caller can inspect what the failed SQL referenced
    and widen the schema shown to the model (see ``run_query`` in
    backend/app/controllers/query.py). Its return value is ignored.
"""

import inspect
import time

from backend.app.sqlvalidate import validate_sql


async def _call(fn, *args):
    """Invoke a callable that may be sync or async and return its result."""
    out = fn(*args)
    if inspect.isawaitable(out):
        out = await out
    return out


def schema_validator(schema, dialect=""):
    """Return a ``validate(sql)`` callable bound to ``schema`` + ``dialect``."""

    def _validate(sql):
        return validate_sql(sql, schema, dialect)

    return _validate


def _feedback(sql, errors):
    """Render prior SQL + its errors as a correction prompt for the next attempt."""
    lines = [
        "The previous SQL attempt was:",
        (sql or "").strip(),
        "",
        "Problems found:",
    ]
    lines += [f"- {e}" for e in errors]
    lines.append("Return a corrected SQL query that fixes these problems.")
    return "\n".join(lines)


async def run_repair_loop(
    generate,
    validate,
    execute=None,
    on_failure=None,
    max_iterations=3,
    max_seconds=None,
    clock=time.monotonic,
):
    """Run the generate→validate→(execute)→repair loop.

    Returns a dict::

        {
            "ok": bool,            # True if a candidate passed all checks
            "sql": str,            # the accepted SQL, or the last attempt on failure
            "restatement": str,
            "chart": dict | None,  # the generator's chart choice, if it made one
            "result": dict | None, # execute() output when ok and an executor was given
            "attempts": [ {"sql", "stage", "errors"?}, ... ],
        }

    ``stage`` is ``"ok"`` for the accepted attempt, or ``"validate"`` / ``"execute"``
    for the step that rejected it. The loop stops at ``max_iterations`` or, if
    ``max_seconds`` is set, once that wall-clock budget is exceeded (checked
    before each new attempt — the first attempt always runs).
    """
    attempts = []
    feedback = ""
    last = {}
    start = clock()

    for i in range(max(1, max_iterations)):
        if max_seconds is not None and i > 0 and (clock() - start) > max_seconds:
            break

        last = await _call(generate, feedback) or {}
        sql = (last.get("sql") or "").strip()

        verdict = await _call(validate, sql) or {}
        if not verdict.get("ok"):
            errs = verdict.get("errors", [])
            attempts.append({"sql": sql, "stage": "validate", "errors": errs})
            feedback = _feedback(sql, errs)
            if on_failure is not None:
                await _call(on_failure, sql, errs)
            continue

        if execute is not None:
            result = await _call(execute, sql) or {}
            if result.get("error"):
                errs = [result["error"]]
                attempts.append({"sql": sql, "stage": "execute", "errors": errs})
                feedback = _feedback(sql, errs)
                if on_failure is not None:
                    await _call(on_failure, sql, errs)
                continue
            attempts.append({"sql": sql, "stage": "ok"})
            return {
                "ok": True,
                "sql": sql,
                "restatement": last.get("restatement", ""),
                "assumptions": last.get("assumptions", []),
                "chart": last.get("chart"),
                "result": result,
                "attempts": attempts,
            }

        attempts.append({"sql": sql, "stage": "ok"})
        return {
            "ok": True,
            "sql": sql,
            "restatement": last.get("restatement", ""),
            "assumptions": last.get("assumptions", []),
            "chart": last.get("chart"),
            "result": None,
            "attempts": attempts,
        }

    return {
        "ok": False,
        "sql": (last.get("sql") or "").strip(),
        "restatement": last.get("restatement", ""),
        "assumptions": last.get("assumptions", []),
        "chart": last.get("chart"),
        "result": None,
        "attempts": attempts,
    }
