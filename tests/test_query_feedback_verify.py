"""Tests for backend/app/controllers/query.py's ``feedback`` and ``verify``
functions — both now scope every knowledge-base call to (workspace_id, db_id) via
the async KnowledgeService.
"""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import backend.app.controllers.query as query_ctrl


class DummyDB:
    def __init__(self, connected=True, db_id="db-1"):
        self._connected = connected
        self._db_id = db_id

    def connected(self, workspace_id):
        return self._connected

    def get_db_id(self, workspace_id):
        return self._db_id


class DummyKB:
    def __init__(self, trust="trust-value", verified=None):
        self.add_verified_calls = []
        self.trust_level_calls = []
        self.get_verified_calls = []
        self._trust = trust
        self._verified = verified if verified is not None else []

    async def add_verified(self, workspace_id, db_id, question, sql, restatement=""):
        self.add_verified_calls.append(
            (workspace_id, db_id, question, sql, restatement)
        )

    async def trust_level(self, workspace_id, db_id):
        self.trust_level_calls.append((workspace_id, db_id))
        return self._trust

    async def get_verified(self, workspace_id, db_id):
        self.get_verified_calls.append((workspace_id, db_id))
        return self._verified


class DummySessionLog:
    def __init__(self):
        self.feedback_calls = []

    def log_feedback(self, query_id, verdict, reason):
        self.feedback_calls.append((query_id, verdict, reason))


def _feedback_req(verdict="correct", **overrides):
    defaults = dict(
        query_id="q-1",
        verdict=verdict,
        reason="",
        question="How many orders?",
        sql="SELECT 1",
        restatement="One",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _verify_req(**overrides):
    defaults = dict(question="How many orders?", sql="SELECT 1", restatement="One")
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def test_feedback_raises_409_when_not_connected():
    db = DummyDB(connected=False)
    kb = DummyKB()
    session_log = DummySessionLog()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            query_ctrl.feedback(
                "w1", db, kb, session_log, _feedback_req(verdict="correct")
            )
        )
    assert exc_info.value.status_code == 409


def test_feedback_logs_feedback_with_request_fields():
    db = DummyDB()
    kb = DummyKB()
    session_log = DummySessionLog()
    req = _feedback_req(verdict="incorrect", reason="wrong table")

    asyncio.run(query_ctrl.feedback("w1", db, kb, session_log, req))

    assert session_log.feedback_calls == [("q-1", "incorrect", "wrong table")]


def test_feedback_correct_verdict_adds_verified_scoped_to_user_and_db():
    db = DummyDB(db_id="db-42")
    kb = DummyKB()
    session_log = DummySessionLog()
    req = _feedback_req(verdict="correct")

    asyncio.run(query_ctrl.feedback("w1", db, kb, session_log, req))

    assert kb.add_verified_calls == [
        ("w1", "db-42", "How many orders?", "SELECT 1", "One")
    ]


def test_feedback_incorrect_verdict_does_not_add_verified():
    db = DummyDB()
    kb = DummyKB()
    session_log = DummySessionLog()
    req = _feedback_req(verdict="incorrect")

    asyncio.run(query_ctrl.feedback("w1", db, kb, session_log, req))

    assert kb.add_verified_calls == []


def test_feedback_returns_trust_level_scoped_to_user_and_db():
    db = DummyDB(db_id="db-42")
    kb = DummyKB(trust="trust:db-42")
    session_log = DummySessionLog()
    req = _feedback_req(verdict="incorrect")

    result = asyncio.run(query_ctrl.feedback("w1", db, kb, session_log, req))

    assert result["ok"] is True
    assert result["trust"] == "trust:db-42"
    assert kb.trust_level_calls == [("w1", "db-42")]


def test_feedback_correct_verdict_includes_starters_from_verified():
    db = DummyDB(db_id="db-42")
    verified = [{"question": f"q{i}"} for i in range(8)]
    kb = DummyKB(verified=verified)
    session_log = DummySessionLog()
    req = _feedback_req(verdict="correct")

    result = asyncio.run(query_ctrl.feedback("w1", db, kb, session_log, req))

    # Starters are capped at the first 6 verified questions.
    assert result["starters"] == [f"q{i}" for i in range(6)]
    assert kb.get_verified_calls == [("w1", "db-42")]


def test_feedback_incorrect_verdict_has_no_starters_key():
    db = DummyDB()
    kb = DummyKB(verified=[{"question": "q0"}])
    session_log = DummySessionLog()
    req = _feedback_req(verdict="incorrect")

    result = asyncio.run(query_ctrl.feedback("w1", db, kb, session_log, req))

    assert "starters" not in result
    assert kb.get_verified_calls == []


def test_verify_raises_409_when_not_connected():
    db = DummyDB(connected=False)
    kb = DummyKB()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(query_ctrl.verify("w1", db, kb, _verify_req()))
    assert exc_info.value.status_code == 409


def test_verify_adds_verified_scoped_to_user_and_db():
    db = DummyDB(db_id="db-7")
    kb = DummyKB()
    req = _verify_req(question="Top products?", sql="SELECT 2", restatement="Top")

    asyncio.run(query_ctrl.verify("w1", db, kb, req))

    assert kb.add_verified_calls == [("w1", "db-7", "Top products?", "SELECT 2", "Top")]


def test_verify_returns_ok_and_trust_level_scoped_to_user_and_db():
    db = DummyDB(db_id="db-7")
    kb = DummyKB(trust="trust:db-7")
    req = _verify_req()

    result = asyncio.run(query_ctrl.verify("w1", db, kb, req))

    assert result == {"ok": True, "trust": "trust:db-7"}
    assert kb.trust_level_calls == [("w1", "db-7")]
