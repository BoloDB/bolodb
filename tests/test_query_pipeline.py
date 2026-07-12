"""End-to-end tests for run_query's generate→validate→execute→repair wiring
(backend/app/controllers/query.py) using fake DB / knowledge base / provider."""

import asyncio
import json

from backend.app.controllers.query import run_query
from backend.app.llm import LLMError

SCHEMA = {
    "orders": {
        "columns": [
            {"name": "id", "primary_key": True},
            {"name": "total_amount"},
        ],
        "foreign_keys": [],
        "row_count": 10,
        "distinct_values": {},
        "sample_rows": [],
    }
}


class FakeDB:
    def __init__(self, exec_results=None):
        self.exec_results = list(exec_results or [])
        self.executed = []

    def connected(self, user_id):
        return True

    def get_db_id(self, user_id):
        return "db1"

    def get_schema(self, user_id):
        return SCHEMA

    def get_dialect(self, user_id):
        return "sqlite"

    def execute(self, user_id, sql):
        self.executed.append(sql)
        if self.exec_results:
            return self.exec_results.pop(0)
        return {"columns": ["n"], "rows": [{"n": 1}], "truncated": False}


class FakeKB:
    """Minimal knowledge base with an optional catalog for the query tests."""

    def __init__(self, catalog=None):
        self._catalog = catalog or {}

    def get_glossary(self, db_id):
        return []

    def get_catalog(self, db_id):
        return self._catalog

    def retrieve_similar(self, db_id, q, k=3):
        return []


class FakeProvider:
    """Returns queued JSON responses; records prompts it was sent."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, system, user, json_mode=False, schema=None, **kw):
        self.calls.append({"system": system, "user": user})
        if isinstance(self.responses[0], Exception):
            raise self.responses.pop(0)
        return self.responses.pop(0)


class FakeProviders:
    def __init__(self, provider):
        self._p = provider

    def get(self):
        return self._p


class FakeLog:
    def log_query(self, db_id, q, out):
        return "qid-1"


class Req:
    def __init__(self, question, context=None):
        self.question = question
        self.context = context or []


CFG = {"provider": "gemini", "model": "gemini-2.5-flash"}


def _sql_json(sql, restatement="r"):
    return json.dumps({"sql": sql, "restatement": restatement, "assumptions": []})


def _run(provider, db=None):
    return asyncio.run(
        run_query(
            "u1",
            db or FakeDB(),
            FakeKB(),
            CFG,
            FakeProviders(provider),
            FakeLog(),
            Req("how many orders?"),
        )
    )


def test_good_sql_first_try():
    provider = FakeProvider([_sql_json("SELECT COUNT(*) FROM orders")])
    out = _run(provider)
    assert out["sql"] == "SELECT COUNT(*) FROM orders"
    assert out["attempts"] == 1
    assert out["repaired"] is False
    assert out["rows"] == [{"n": 1}]
    assert "execution_error" not in out


def test_hallucinated_column_is_repaired_before_execution():
    db = FakeDB()
    provider = FakeProvider(
        [
            _sql_json("SELECT revenue FROM orders"),  # 'revenue' doesn't exist
            _sql_json("SELECT total_amount FROM orders"),  # repaired
        ]
    )
    out = _run(provider, db)
    assert out["sql"] == "SELECT total_amount FROM orders"
    assert out["attempts"] == 2
    assert out["repaired"] is True
    # the bad SQL never reached the database — the validator caught it
    assert db.executed == ["SELECT total_amount FROM orders"]
    # the repair prompt named the broken column
    assert "revenue" in provider.calls[1]["user"]


def test_execution_error_is_fed_back_and_repaired():
    # first candidate parses and validates fine but blows up at runtime
    db = FakeDB(
        exec_results=[
            {"error": "division by zero"},
            {"columns": ["n"], "rows": [{"n": 2}], "truncated": False},
        ]
    )
    provider = FakeProvider(
        [
            _sql_json("SELECT total_amount / 0 FROM orders"),
            _sql_json("SELECT id FROM orders"),
        ]
    )
    out = _run(provider, db)
    assert out["sql"] == "SELECT id FROM orders"
    assert out["repaired"] is True
    assert "division by zero" in provider.calls[1]["user"]
    assert out["rows"] == [{"n": 2}]


def test_all_attempts_fail_returns_low_confidence_with_error():
    provider = FakeProvider([_sql_json("SELECT ghost FROM orders")] * 3)
    out = _run(provider)
    assert out["attempts"] == 3
    assert out["confidence"] == "low"
    assert "ghost" in out["execution_error"]


def test_llm_error_surfaces_friendly_message():
    provider = FakeProvider(
        [LLMError("The Gemini API rejected the request — check the key.")]
    )
    out = _run(provider)
    assert out["confidence"] == "low"
    assert "Gemini" in out["execution_error"]
    assert out["query_id"] == "qid-1"
