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

    def get(self, user_id):
        return self._p


class FakeLog:
    def log_query(self, db_id, q, out):
        return "qid-1"


class Req:
    def __init__(self, question, context=None, conversation_id=None):
        self.question = question
        self.context = context or []
        self.conversation_id = conversation_id


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


# --- schema-retry: the repair loop widens the linked tables -----------------


def _wide_schema(n_big=24, small_table="archived_orders"):
    """24 big generic tables + one tiny table linking will drop (budget is 20)."""
    schema = {}
    for i in range(n_big):
        schema[f"t{i:02d}"] = {
            "columns": [{"name": "id", "primary_key": True}, {"name": "val"}],
            "foreign_keys": [],
            "row_count": 1000,
            "distinct_values": {},
            "sample_rows": [],
        }
    schema[small_table] = {
        "columns": [{"name": "id", "primary_key": True}, {"name": "total"}],
        "foreign_keys": [],
        "row_count": 1,
        "distinct_values": {},
        "sample_rows": [],
    }
    return schema


class WideFakeDB(FakeDB):
    def __init__(self, schema):
        super().__init__()
        self._schema = schema

    def get_schema(self, user_id):
        return self._schema


def test_schema_retry_adds_table_the_model_asked_for():
    # linking drops `archived_orders` (nothing matches; smallest table). The
    # model references it anyway with a bad column -> validation fails -> the
    # schema-retry hook must add it, and attempt 2 must see + use it.
    db = WideFakeDB(_wide_schema())
    provider = FakeProvider(
        [
            _sql_json("SELECT nope FROM archived_orders"),
            _sql_json("SELECT total FROM archived_orders"),
        ]
    )
    out = asyncio.run(
        run_query(
            "u1",
            db,
            FakeKB(),
            CFG,
            FakeProviders(provider),
            FakeLog(),
            Req("give me the thing"),
        )
    )
    assert out["sql"] == "SELECT total FROM archived_orders"
    assert out["attempts"] == 2
    assert "archived_orders" in out["tables_used"]
    # the widened schema reached the second generation prompt
    assert "archived_orders(" in provider.calls[1]["system"]
    assert "archived_orders(" not in provider.calls[0]["system"]


# --- two-stage linking: LLM shortlist on big schemas ------------------------


def _huge_schema(n=35):
    return {
        f"t{i:02d}": {
            "columns": [{"name": "id", "primary_key": True}, {"name": "val"}],
            "foreign_keys": [],
            "row_count": 1000 - i,  # t00 biggest ... t34 smallest
            "distinct_values": {},
            "sample_rows": [],
        }
        for i in range(n)
    }


def test_shortlist_pass_runs_on_big_schemas_and_boosts_picks():
    db = WideFakeDB(_huge_schema())
    provider = FakeProvider(
        [
            json.dumps({"tables": ["t34"]}),  # shortlist reply: smallest table
            _sql_json("SELECT val FROM t34"),
        ]
    )
    out = asyncio.run(
        run_query(
            "u1",
            db,
            FakeKB(),
            CFG,
            FakeProviders(provider),
            FakeLog(),
            Req("give me the thing"),
        )
    )
    # first provider call was the shortlist over a names-only catalog
    assert "Catalog" in provider.calls[0]["system"]
    assert "t34(" in provider.calls[0]["system"]
    # the boosted table beat the row-count fallback despite being smallest
    assert "t34" in out["tables_used"]
    assert out["sql"] == "SELECT val FROM t34"


def test_shortlist_failure_falls_back_to_local_linking():
    db = WideFakeDB(_huge_schema())
    provider = FakeProvider(
        [
            LLMError("busy"),  # shortlist call fails...
            _sql_json("SELECT val FROM t00"),  # ...generation still works
        ]
    )
    out = asyncio.run(
        run_query(
            "u1",
            db,
            FakeKB(),
            CFG,
            FakeProviders(provider),
            FakeLog(),
            Req("give me the thing"),
        )
    )
    assert out["sql"] == "SELECT val FROM t00"
    assert "execution_error" not in out


def test_no_shortlist_call_on_small_schemas():
    provider = FakeProvider([_sql_json("SELECT COUNT(*) FROM orders")])
    out = _run(provider)  # 1-table schema -> straight to generation
    assert len(provider.calls) == 1
    assert "Catalog" not in provider.calls[0]["system"]
    assert out["sql"]
