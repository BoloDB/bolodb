"""Tests for run_query_stream (backend/app/controllers/query.py) — the SSE
streaming variant of the question→answer pipeline. Reuses the fake DB /
knowledge base / provider from test_query_pipeline.

Regression guard: run_query_stream once called model_budget() with two
positional arguments while it only accepts one, so every streamed query blew
up with a TypeError that surfaced to users as "An internal error occurred".
"""

import asyncio
import json

from backend.app.controllers.query import run_query_stream
import backend.app.controllers.query as query_ctrl
from tests.test_query_pipeline import (
    FakeDB,
    FakeKB,
    FakeProvider,
    FakeProviders,
    FakeLog,
    Req,
    CFG,
)


def _sql_json(sql, restatement="r"):
    return json.dumps({"sql": sql, "restatement": restatement, "assumptions": []})


def _collect(provider, db=None, monkeypatch_saves=None):
    async def _run():
        events = []
        async for ev in run_query_stream(
            "u1",
            db or FakeDB(),
            FakeKB(),
            CFG,
            FakeProviders(provider),
            FakeLog(),
            Req("show orders"),
        ):
            events.append(ev)
        return events

    return asyncio.run(_run())


def test_stream_happy_path_emits_result(monkeypatch):
    saved = []
    monkeypatch.setattr(
        query_ctrl.mdb, "save_query", lambda **kw: saved.append(kw), raising=True
    )
    provider = FakeProvider([_sql_json("SELECT id FROM orders")])
    events = _collect(provider)

    kinds = [e["kind"] for e in events]
    assert "error" not in kinds, f"unexpected error event(s): {events}"
    assert kinds[0] == "schema_linked"
    assert kinds[-1] == "result"
    for expected in ("sql", "validation", "execution", "confidence"):
        assert expected in kinds

    data = next(e for e in events if e["kind"] == "result")["data"]
    assert data["sql"] == "SELECT id FROM orders"
    assert data["answered"] is True

    # streamed queries must persist to history like the non-streaming route
    assert len(saved) == 1
    assert saved[0]["question"] == "show orders"
    assert saved[0]["confidence"] in ("High", "Medium", "Low")


def test_stream_repairs_invalid_sql(monkeypatch):
    monkeypatch.setattr(query_ctrl.mdb, "save_query", lambda **kw: None, raising=True)
    provider = FakeProvider(
        [
            _sql_json("SELECT revenue FROM orders"),  # invalid column
            _sql_json("SELECT total_amount FROM orders"),  # repaired
        ]
    )
    events = _collect(provider)
    kinds = [e["kind"] for e in events]
    assert "repair" in kinds
    assert kinds[-1] == "result"
    data = next(e for e in events if e["kind"] == "result")["data"]
    assert data["sql"] == "SELECT total_amount FROM orders"


def test_stream_repairs_execution_failure(monkeypatch):
    """A query that validates but fails at execution must feed back into the
    repair loop, matching the non-streaming run_query behaviour."""
    monkeypatch.setattr(query_ctrl.mdb, "save_query", lambda **kw: None, raising=True)
    # both SQLs validate fine; the first fails at execution, the second works
    db = FakeDB(
        exec_results=[
            {"error": "no such column: totl"},
            {"columns": ["n"], "rows": [{"n": 1}], "truncated": False},
        ]
    )
    provider = FakeProvider(
        [
            _sql_json("SELECT id FROM orders"),
            _sql_json("SELECT total_amount FROM orders"),
        ]
    )
    events = _collect(provider, db=db)
    kinds = [e["kind"] for e in events]
    assert "repair" in kinds  # execution failure triggered a repair
    assert kinds[-1] == "result"
    data = next(e for e in events if e["kind"] == "result")["data"]
    assert data["sql"] == "SELECT total_amount FROM orders"
    assert "execution_error" not in data
    assert data["rows"] == [{"n": 1}]
