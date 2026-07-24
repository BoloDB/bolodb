"""Every entry point must stay on the database the request selected.

A workspace can hold several databases, and the caller picks one per request
with the `X-Db-Id` header. Each controller below used to check connectivity
against that selection but then read `db.get_db_id(workspace_id)` again for
knowledge and logging — which returns the workspace *default*. The result was a
query that ran against database B while being prompted with database A's
glossary, verified examples and catalog, and then logged against A.

These tests record every call the controllers make and assert the selected id
reaches each collaborator. They are deliberately strict about *which* id each
call carries: asserting only that "a db_id was passed" is what let the mismatch
survive in the first place.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.controllers import query as query_ctrl
from backend.app.models.api import QueryReq

WORKSPACE = "workspace-1"
SELECTED_DB = "secondary-db"
DEFAULT_DB = "default-db"


class RecordingDB:
    """A manager whose `get_db_id` always names the workspace default.

    That is the whole point: if a controller reaches for `get_db_id` instead of
    the id it was handed, the recorded calls show `default-db` and the test
    fails.
    """

    def __init__(self, connected=True):
        self.calls = []
        self._connected = connected

    def connected(self, workspace_id, db_id=None):
        self.calls.append(("connected", workspace_id, db_id))
        return self._connected

    def get_db_id(self, workspace_id, db_id=None):
        self.calls.append(("get_db_id", workspace_id, db_id))
        return DEFAULT_DB

    def get_schema(self, workspace_id, db_id=None, refresh=False):
        self.calls.append(("get_schema", workspace_id, db_id))
        return {
            "secondary_orders": {
                "columns": [{"name": "id", "type": "integer"}],
                "samples": [],
            }
        }

    def get_dialect(self, workspace_id, db_id=None):
        self.calls.append(("get_dialect", workspace_id, db_id))
        return "postgres"

    def execute(self, workspace_id, sql, db_id=None):
        self.calls.append(("execute", workspace_id, sql, db_id))
        return {"columns": ["id"], "rows": [[1]], "truncated": False}

    def db_ids_seen(self, name):
        """Every db_id this manager was asked about under `name`."""
        return [c[-1] for c in self.calls if c[0] == name]


class RecordingKB:
    def __init__(self):
        self.calls = []

    async def get_glossary(self, workspace_id, db_id):
        self.calls.append(("get_glossary", workspace_id, db_id))
        return []

    async def get_catalog(self, workspace_id, db_id):
        self.calls.append(("get_catalog", workspace_id, db_id))
        return {}

    async def retrieve_similar(self, workspace_id, db_id, q, k=3):
        self.calls.append(("retrieve_similar", workspace_id, db_id))
        return []

    async def add_verified(self, workspace_id, db_id, question, sql, restatement):
        self.calls.append(("add_verified", workspace_id, db_id))

    async def trust_level(self, workspace_id, db_id):
        self.calls.append(("trust_level", workspace_id, db_id))
        return {"level": "Supervised", "verified": 1, "db_id_seen": db_id}

    async def get_verified(self, workspace_id, db_id):
        self.calls.append(("get_verified", workspace_id, db_id))
        return [{"question": f"starter-from-{db_id}"}]

    def db_ids_seen(self, name=None):
        return [c[2] for c in self.calls if name is None or c[0] == name]


class RecordingSessionLog:
    def __init__(self):
        self.calls = []

    def log_query(self, db_id, question, out):
        self.calls.append(("log_query", db_id, question))
        return "query-123"

    def log_feedback(self, query_id, verdict, reason):
        self.calls.append(("log_feedback", query_id, verdict, reason))


class Providers:
    def get(self, workspace_id):
        return object()


@pytest.fixture(autouse=True)
def _no_stored_connection(monkeypatch):
    """Keep the reconnect path away from a real database in these tests.

    `_resolve_db_id` falls back to stored credentials when nothing is connected;
    that path has its own tests. Here the manager reports connected, so this
    only guards the disconnected case.
    """

    async def _none(*args, **kwargs):
        return None

    monkeypatch.setattr(query_ctrl.mdb, "get_recent_connection_by_db_id", _none)
    monkeypatch.setattr(query_ctrl.mdb, "get_latest_recent_connection", _none)


# ── verify ──────────────────────────────────────────────────────────


def test_verify_scopes_knowledge_to_selected_database():
    db, kb = RecordingDB(), RecordingKB()
    req = SimpleNamespace(
        question="How many users signed up?",
        sql="select count(*) from users",
        restatement="Count all users",
    )

    result = asyncio.run(query_ctrl.verify(WORKSPACE, db, kb, req, db_id=SELECTED_DB))

    assert db.calls[0] == ("connected", WORKSPACE, SELECTED_DB), (
        "connectivity must be checked against the selected database"
    )
    assert kb.calls[0] == ("add_verified", WORKSPACE, SELECTED_DB), (
        "the verified example belongs to the database it was verified against"
    )
    assert kb.calls[1] == ("trust_level", WORKSPACE, SELECTED_DB)
    assert result["trust"]["db_id_seen"] == SELECTED_DB
    assert DEFAULT_DB not in kb.db_ids_seen()


def test_verify_rejects_when_nothing_is_connected():
    db, kb = RecordingDB(connected=False), RecordingKB()
    req = SimpleNamespace(question="q", sql="select 1", restatement="r")

    with pytest.raises(HTTPException) as excinfo:
        asyncio.run(query_ctrl.verify(WORKSPACE, db, kb, req, db_id=SELECTED_DB))

    assert excinfo.value.status_code == 409
    assert kb.calls == [], "nothing should be written when there is no database"


# ── feedback ────────────────────────────────────────────────────────


def test_feedback_scopes_knowledge_and_starters_to_selected_database():
    db, kb, session_log = RecordingDB(), RecordingKB(), RecordingSessionLog()
    req = SimpleNamespace(
        query_id="query-123",
        verdict="correct",
        reason="answer matched",
        question="How many secondary customers?",
        sql="select count(*) from secondary_customers",
        restatement="Count secondary customers",
    )

    out = asyncio.run(
        query_ctrl.feedback(WORKSPACE, db, kb, session_log, req, db_id=SELECTED_DB)
    )

    assert kb.calls[0] == ("add_verified", WORKSPACE, SELECTED_DB)
    assert ("trust_level", WORKSPACE, SELECTED_DB) in kb.calls
    assert ("get_verified", WORKSPACE, SELECTED_DB) in kb.calls
    assert DEFAULT_DB not in kb.db_ids_seen()
    assert out["starters"] == [f"starter-from-{SELECTED_DB}"], (
        "starters must come from the database the user is actually on"
    )


def test_feedback_records_nothing_verified_when_answer_was_wrong():
    db, kb, session_log = RecordingDB(), RecordingKB(), RecordingSessionLog()
    req = SimpleNamespace(
        query_id="query-123",
        verdict="wrong",
        reason="bad join",
        question="q",
        sql="select 1",
        restatement="r",
    )

    out = asyncio.run(
        query_ctrl.feedback(WORKSPACE, db, kb, session_log, req, db_id=SELECTED_DB)
    )

    assert "add_verified" not in [c[0] for c in kb.calls]
    assert "starters" not in out
    assert session_log.calls[0][0] == "log_feedback"


# ── explain / execute ───────────────────────────────────────────────


def test_explain_reads_the_dialect_of_the_selected_database():
    db = RecordingDB()
    captured = {}

    async def fake_explain_sql(provider, sql, dialect):
        captured["dialect"] = dialect
        return {"explanation": "counts rows"}

    original = query_ctrl.explain_sql
    query_ctrl.explain_sql = fake_explain_sql
    try:
        asyncio.run(
            query_ctrl.explain(
                WORKSPACE,
                db,
                Providers(),
                SimpleNamespace(sql="select 1"),
                db_id=SELECTED_DB,
            )
        )
    finally:
        query_ctrl.explain_sql = original

    assert captured["dialect"] == "postgres"
    assert db.db_ids_seen("get_dialect") == [SELECTED_DB], (
        "the dialect must be read from the selected database, not the default"
    )


def test_execute_runs_against_the_selected_database():
    db = RecordingDB()

    asyncio.run(
        query_ctrl.execute(
            WORKSPACE, db, SimpleNamespace(sql="select 1"), db_id=SELECTED_DB
        )
    )

    executes = [c for c in db.calls if c[0] == "execute"]
    assert executes == [("execute", WORKSPACE, "select 1", SELECTED_DB)]


# ── the full pipeline, streaming and not ────────────────────────────


@pytest.fixture
def stubbed_pipeline(monkeypatch):
    """Replace the model and SQL machinery so only db_id routing is under test."""

    async def fake_generate_sql(*args, **kwargs):
        return {
            "sql": "SELECT id FROM secondary_orders",
            "restatement": "secondary orders",
            "chart": {"type": "table"},
        }

    async def fake_conversation_owned_by(workspace_id, user_id, conversation_id):
        return False

    async def fake_save_query(**kwargs):
        return None

    monkeypatch.setattr(query_ctrl, "generate_sql", fake_generate_sql)
    monkeypatch.setattr(
        query_ctrl,
        "validate_sql",
        lambda sql, schema, dialect: {"ok": True, "errors": []},
    )
    monkeypatch.setattr(
        query_ctrl, "link_relevant_tables", lambda *a, **k: ["secondary_orders"]
    )
    monkeypatch.setattr(
        query_ctrl,
        "compact_schema",
        lambda schema, tables, samples: "secondary_orders(id)",
    )
    monkeypatch.setattr(
        query_ctrl,
        "compute_confidence",
        lambda retrieved, exec_result: ("high", "r", True),
    )
    monkeypatch.setattr(query_ctrl, "filter_catalog", lambda catalog, tables: catalog)
    monkeypatch.setattr(
        query_ctrl.mdb, "conversation_owned_by", fake_conversation_owned_by
    )
    monkeypatch.setattr(query_ctrl.mdb, "save_query", fake_save_query)


def test_streaming_query_keeps_knowledge_schema_and_log_on_one_database(
    stubbed_pipeline,
):
    db, kb, session_log = RecordingDB(), RecordingKB(), RecordingSessionLog()
    req = QueryReq(question="Show secondary orders", context=[], conversation_id=None)

    async def collect():
        return [
            event
            async for event in query_ctrl.run_query_stream(
                WORKSPACE,
                db,
                kb,
                None,
                Providers(),
                session_log,
                req,
                db_id=SELECTED_DB,
                user_id="user-1",
            )
        ]

    events = asyncio.run(collect())

    assert kb.db_ids_seen() == [SELECTED_DB] * len(kb.calls), (
        f"knowledge was read from the wrong database: {kb.calls}"
    )
    assert db.db_ids_seen("get_schema") == [SELECTED_DB]
    assert [c[3] for c in db.calls if c[0] == "execute"] == [SELECTED_DB]
    assert session_log.calls == [("log_query", SELECTED_DB, "Show secondary orders")], (
        "the query must be logged against the database it ran on"
    )

    result = events[-1]
    assert result["kind"] == "result"
    assert result["data"]["query_id"] == "query-123"


def test_non_streaming_query_keeps_knowledge_schema_and_log_on_one_database(
    stubbed_pipeline, monkeypatch
):
    db, kb, session_log = RecordingDB(), RecordingKB(), RecordingSessionLog()

    async def fake_repair_loop(*args, **kwargs):
        return {
            "sql": "SELECT id FROM secondary_orders",
            "restatement": "secondary orders",
            "chart": {"type": "table"},
            "result": {"columns": ["id"], "rows": [[1]], "truncated": False},
            "attempts": [{"errors": []}],
            "ok": True,
        }

    monkeypatch.setattr(query_ctrl, "run_repair_loop", fake_repair_loop)
    req = QueryReq(question="Show secondary orders", context=[], conversation_id=None)

    out = asyncio.run(
        query_ctrl.run_query(
            WORKSPACE,
            db,
            kb,
            None,
            Providers(),
            session_log,
            req,
            db_id=SELECTED_DB,
            user_id="user-1",
        )
    )

    assert kb.db_ids_seen() == [SELECTED_DB] * len(kb.calls), (
        f"knowledge was read from the wrong database: {kb.calls}"
    )
    assert db.db_ids_seen("get_schema") == [SELECTED_DB]
    assert [c[1] for c in session_log.calls if c[0] == "log_query"] == [SELECTED_DB]
    assert out["query_id"] == "query-123"


def test_selection_falls_back_to_the_workspace_default_when_unspecified():
    """No `X-Db-Id` still has to resolve to a concrete id, once."""
    db, kb = RecordingDB(), RecordingKB()
    req = SimpleNamespace(question="q", sql="select 1", restatement="r")

    asyncio.run(query_ctrl.verify(WORKSPACE, db, kb, req, db_id=None))

    assert kb.calls[0] == ("add_verified", WORKSPACE, DEFAULT_DB)
    assert kb.calls[1] == ("trust_level", WORKSPACE, DEFAULT_DB)
