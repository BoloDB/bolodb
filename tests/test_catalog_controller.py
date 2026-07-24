"""Tests for the semantic-catalog controller and routes (backend/app/
controllers/catalog.py, backend/app/routes/catalog.py).

``get_catalog`` / ``save_catalog`` became async and now pass ``workspace_id``
through to the (user, db)-scoped KnowledgeService, and the routes had to
start awaiting them.
"""

import asyncio

import pytest
from fastapi import HTTPException

import backend.app.controllers.catalog as catalog_ctrl
import backend.app.routes.catalog as catalog_routes
from backend.app.models.api import CatalogPayload


class DummyDB:
    def __init__(self, connected=True):
        self._connected = connected
        self.db_id_calls = []

    def connected(self, workspace_id, db_id=None):
        return self._connected

    def get_db_id(self, workspace_id, db_id=None):
        self.db_id_calls.append((workspace_id, db_id))
        return db_id or f"db-{workspace_id}"


class DummyKB:
    def __init__(self, catalog=None):
        self._catalog = catalog or {"metrics": []}
        self.get_calls = []
        self.set_calls = []

    async def get_catalog(self, workspace_id, db_id):
        self.get_calls.append((workspace_id, db_id))
        return self._catalog

    async def set_catalog(self, workspace_id, db_id, catalog):
        self.set_calls.append((workspace_id, db_id, catalog))


# ── controllers/catalog.py ──────────────────────────────────────────


def test_get_catalog_raises_409_when_not_connected():
    db = DummyDB(connected=False)
    kb = DummyKB()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(catalog_ctrl.get_catalog("w1", db, kb))
    assert exc.value.status_code == 409


def test_get_catalog_passes_workspace_id_and_db_id_to_kb():
    db = DummyDB()
    kb = DummyKB(catalog={"metrics": [{"name": "revenue"}]})
    result = asyncio.run(catalog_ctrl.get_catalog("w1", db, kb))
    assert result == {"catalog": {"metrics": [{"name": "revenue"}]}}
    assert kb.get_calls == [("w1", "db-w1")]


def test_get_catalog_forwards_selected_db_id():
    """The active X-Db-Id must scope the catalog, not the workspace default."""
    db = DummyDB()
    kb = DummyKB(catalog={"metrics": []})
    asyncio.run(catalog_ctrl.get_catalog("w1", db, kb, db_id="db-selected"))
    assert kb.get_calls == [("w1", "db-selected")]


def test_save_catalog_raises_409_when_not_connected():
    db = DummyDB(connected=False)
    kb = DummyKB()
    payload = CatalogPayload()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(catalog_ctrl.save_catalog("w1", db, kb, payload))
    assert exc.value.status_code == 409


def test_save_catalog_persists_payload_with_workspace_id_and_returns_ok():
    db = DummyDB()
    kb = DummyKB()
    payload = CatalogPayload(metrics=[{"name": "revenue", "sql_expression": "SUM(x)"}])
    result = asyncio.run(catalog_ctrl.save_catalog("w1", db, kb, payload))
    assert result == {"ok": True}
    assert len(kb.set_calls) == 1
    workspace_id, db_id, catalog = kb.set_calls[0]
    assert workspace_id == "w1"
    assert db_id == "db-w1"
    assert catalog["metrics"][0]["name"] == "revenue"


# ── routes/catalog.py ────────────────────────────────────────────────


def test_get_catalog_route_awaits_controller_and_returns_value(monkeypatch):
    async def fake_get_catalog(workspace_id, db, kb, db_id=None):
        assert workspace_id == "w1"
        return {"catalog": {"metrics": []}}

    monkeypatch.setattr(catalog_routes.ctrl, "get_catalog", fake_get_catalog)
    result = asyncio.run(
        catalog_routes.get_catalog(
            workspace={"workspace_id": "w1"}, db="db", kb="kb", db_id=None
        )
    )
    assert result == {"catalog": {"metrics": []}}


def test_get_catalog_route_reraises_http_exception(monkeypatch):
    async def fake_get_catalog(workspace_id, db, kb, db_id=None):
        raise HTTPException(409, "No database connected")

    monkeypatch.setattr(catalog_routes.ctrl, "get_catalog", fake_get_catalog)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            catalog_routes.get_catalog(
                workspace={"workspace_id": "w1"}, db="db", kb="kb", db_id=None
            )
        )
    assert exc.value.status_code == 409


def test_get_catalog_route_wraps_generic_exception_as_500(monkeypatch):
    async def fake_get_catalog(workspace_id, db, kb, db_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(catalog_routes.ctrl, "get_catalog", fake_get_catalog)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            catalog_routes.get_catalog(
                workspace={"workspace_id": "w1"}, db="db", kb="kb", db_id=None
            )
        )
    assert exc.value.status_code == 500


def test_save_catalog_route_awaits_controller_and_returns_value(monkeypatch):
    async def fake_save_catalog(workspace_id, db, kb, payload, db_id=None):
        assert workspace_id == "w1"
        assert payload == "payload-obj"
        return {"ok": True}

    monkeypatch.setattr(catalog_routes.ctrl, "save_catalog", fake_save_catalog)
    result = asyncio.run(
        catalog_routes.save_catalog(
            payload="payload-obj",
            workspace={"workspace_id": "w1"},
            db="db",
            kb="kb",
            db_id=None,
        )
    )
    assert result == {"ok": True}


def test_save_catalog_route_wraps_generic_exception_as_500(monkeypatch):
    async def fake_save_catalog(workspace_id, db, kb, payload, db_id=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(catalog_routes.ctrl, "save_catalog", fake_save_catalog)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            catalog_routes.save_catalog(
                payload="payload-obj",
                workspace={"workspace_id": "w1"},
                db="db",
                kb="kb",
                db_id=None,
            )
        )
    assert exc.value.status_code == 500
