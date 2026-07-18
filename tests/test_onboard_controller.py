"""Tests for the onboarding controller's ``save`` step (backend/app/
controllers/onboard.py), which now routes every knowledge-base call through
the (user, db)-scoped KnowledgeService — every ``kb.*`` call must carry
``user_id`` as the first argument and be awaited."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import backend.app.controllers.onboard as onboard_ctrl


class DummyDB:
    def __init__(self, connected=True, schema=None):
        self._connected = connected
        self._schema = schema or {}

    def connected(self, user_id):
        return self._connected

    def get_db_id(self, user_id):
        return f"db-{user_id}"

    def get_schema(self, user_id):
        return self._schema


class DummyKB:
    def __init__(self, catalog_empty=True):
        self._catalog_empty = catalog_empty
        self.glossary_calls = []
        self.verified_calls = []
        self.catalog_calls = []
        self.set_catalog_calls = []

    async def set_glossary(self, user_id, db_id, terms):
        self.glossary_calls.append((user_id, db_id, terms))

    async def add_verified(self, user_id, db_id, question, sql, restatement):
        self.verified_calls.append((user_id, db_id, question, sql, restatement))

    async def catalog_is_empty(self, user_id, db_id):
        self.catalog_calls.append((user_id, db_id))
        return self._catalog_empty

    async def set_catalog(self, user_id, db_id, catalog):
        self.set_catalog_calls.append((user_id, db_id, catalog))

    async def trust_level(self, user_id, db_id):
        return {"level": "Supervised", "verified": 0, "pct": 8, "note": ""}


def _req(glossary=None, starters=None):
    glossary_items = [
        SimpleNamespace(model_dump=lambda t=t: t) for t in (glossary or [])
    ]
    starter_items = [
        SimpleNamespace(
            question=s["question"], sql=s["sql"], restatement=s.get("restatement", "")
        )
        for s in (starters or [])
    ]
    return SimpleNamespace(glossary=glossary_items, starters=starter_items)


def test_save_raises_409_when_not_connected():
    db = DummyDB(connected=False)
    kb = DummyKB()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(onboard_ctrl.save("u1", db, kb, _req()))
    assert exc.value.status_code == 409


def test_save_sets_glossary_with_user_id_and_db_id():
    db = DummyDB()
    kb = DummyKB()
    req = _req(
        glossary=[{"term": "Revenue", "maps_to": "orders.total", "sql_hint": ""}]
    )
    asyncio.run(onboard_ctrl.save("u1", db, kb, req))
    assert len(kb.glossary_calls) == 1
    user_id, db_id, terms = kb.glossary_calls[0]
    assert user_id == "u1"
    assert db_id == "db-u1"
    assert terms == [{"term": "Revenue", "maps_to": "orders.total", "sql_hint": ""}]


def test_save_adds_each_starter_as_verified_with_user_id():
    db = DummyDB()
    kb = DummyKB()
    req = _req(
        starters=[
            {
                "question": "How many orders?",
                "sql": "SELECT COUNT(*) FROM orders",
                "restatement": "count",
            },
            {
                "question": "Total revenue?",
                "sql": "SELECT SUM(x) FROM orders",
                "restatement": "sum",
            },
        ]
    )
    asyncio.run(onboard_ctrl.save("u1", db, kb, req))
    assert len(kb.verified_calls) == 2
    assert kb.verified_calls[0] == (
        "u1",
        "db-u1",
        "How many orders?",
        "SELECT COUNT(*) FROM orders",
        "count",
    )
    assert kb.verified_calls[1] == (
        "u1",
        "db-u1",
        "Total revenue?",
        "SELECT SUM(x) FROM orders",
        "sum",
    )


def test_save_seeds_catalog_backbone_when_catalog_empty(monkeypatch):
    db = DummyDB(schema={"orders": {"columns": [], "foreign_keys": []}})
    kb = DummyKB(catalog_empty=True)
    monkeypatch.setattr(
        onboard_ctrl, "suggest_from_schema", lambda schema: {"joins": ["fake-join"]}
    )
    asyncio.run(onboard_ctrl.save("u1", db, kb, _req()))
    assert kb.catalog_calls == [("u1", "db-u1")]
    assert len(kb.set_catalog_calls) == 1
    user_id, db_id, catalog = kb.set_catalog_calls[0]
    assert user_id == "u1"
    assert db_id == "db-u1"
    assert catalog == {"joins": ["fake-join"]}


def test_save_does_not_reseed_catalog_when_not_empty():
    db = DummyDB()
    kb = DummyKB(catalog_empty=False)
    asyncio.run(onboard_ctrl.save("u1", db, kb, _req()))
    assert kb.catalog_calls == [("u1", "db-u1")]
    assert kb.set_catalog_calls == []


def test_save_returns_trust_level_scoped_to_user_and_db():
    db = DummyDB()

    class TrustKB(DummyKB):
        async def trust_level(self, user_id, db_id):
            return {"level": "Trusted", "verified": 9, "pct": 100, "note": "n"}

    kb = TrustKB()
    result = asyncio.run(onboard_ctrl.save("u1", db, kb, _req()))
    assert result == {
        "ok": True,
        "trust": {"level": "Trusted", "verified": 9, "pct": 100, "note": "n"},
    }
