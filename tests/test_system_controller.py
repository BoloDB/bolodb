"""Tests for the system controller and route (backend/app/controllers/system.py,
backend/app/routes/system.py).

Covers ``get_state`` now reading ``tour_completed`` off the PostgreSQL user
record and stripping ``last_db_url`` from the public config, the new
``set_tour_completed`` controller function, and the ``kb.*`` calls that were
updated to pass ``user_id`` and be awaited.
"""

import asyncio

import backend.app.controllers.system as system_ctrl
import backend.app.routes.system as system_routes


class DummyDB:
    def __init__(self, connected=True, info=None, dialect="sqlite"):
        self._connected = connected
        self._info = info or {"url": "sqlite:///t.db", "db_id": "db1", "tables": 3}
        self._dialect = dialect

    def connected(self, workspace_id, db_id=None):
        return self._connected

    def get_db_id(self, workspace_id, db_id=None):
        return self._info["db_id"]

    def get_info(self, workspace_id, db_id=None):
        return self._info

    def get_dialect(self, workspace_id, db_id=None):
        return self._dialect


class DummyKB:
    def __init__(self, count=0):
        self._count = count
        self.calls = []

    async def count_verified(self, workspace_id, db_id):
        self.calls.append(("count_verified", workspace_id, db_id))
        return self._count

    async def trust_level(self, workspace_id, db_id):
        self.calls.append(("trust_level", workspace_id, db_id))
        return {"level": "Supervised", "verified": self._count, "pct": 8, "note": ""}

    async def get_glossary(self, workspace_id, db_id):
        self.calls.append(("get_glossary", workspace_id, db_id))
        return [{"term": "Revenue"}]

    async def get_verified(self, workspace_id, db_id):
        self.calls.append(("get_verified", workspace_id, db_id))
        return [{"question": f"q-{i}"} for i in range(8)]


# ── controllers/system.py: get_state ────────────────────────────────


def test_get_state_not_connected_includes_tour_completed_from_user(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return {"tour_completed": True}

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_get_user_by_id)
    db = DummyDB(connected=False)
    kb = DummyKB()
    state = asyncio.run(
        system_ctrl.get_state("u1", "w1", "db1", db, {"last_db_url": "x"}, kb)
    )
    assert state["connected"] is False
    assert state["tour_completed"] is True
    assert "database" not in state


def test_get_state_defaults_tour_completed_false_when_user_missing(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return None

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_get_user_by_id)
    db = DummyDB(connected=False)
    kb = DummyKB()
    state = asyncio.run(system_ctrl.get_state("u1", "w1", "db1", db, {}, kb))
    assert state["tour_completed"] is False


def test_get_state_strips_last_db_url_from_public_config(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return {"tour_completed": False}

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_get_user_by_id)
    db = DummyDB(connected=False)
    kb = DummyKB()
    state = asyncio.run(
        system_ctrl.get_state(
            "u1", "w1", "db1", db, {"last_db_url": "sqlite:///secret.db"}, kb
        )
    )
    assert "last_db_url" not in state["config"]


def test_get_state_connected_scopes_kb_calls_to_user_and_db(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return {"tour_completed": False}

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_get_user_by_id)
    db = DummyDB(connected=True, info={"url": "u", "db_id": "db-1", "tables": 5})
    kb = DummyKB(count=8)

    state = asyncio.run(system_ctrl.get_state("u1", "w1", "db-1", db, {}, kb))

    assert state["database"]["has_knowledge"] is True
    assert state["trust"]["level"] == "Supervised"
    assert state["glossary"] == [{"term": "Revenue"}]
    assert len(state["starters"]) == 6  # capped at 6
    for call in kb.calls:
        assert call[1] == "w1"
        assert call[2] == "db-1"


def test_get_state_has_knowledge_false_when_no_verified(monkeypatch):
    async def fake_get_user_by_id(user_id):
        return {"tour_completed": False}

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_get_user_by_id)
    db = DummyDB(connected=True)
    kb = DummyKB(count=0)
    state = asyncio.run(system_ctrl.get_state("u1", "w1", "db1", db, {}, kb))
    assert state["database"]["has_knowledge"] is False


# ── controllers/system.py: set_tour_completed ───────────────────────


def test_set_tour_completed_updates_user_and_returns_ok(monkeypatch):
    calls = []

    async def fake_update_user(user_id, **fields):
        calls.append((user_id, fields))
        return True

    monkeypatch.setattr(system_ctrl.mdb, "update_user", fake_update_user)
    result = asyncio.run(system_ctrl.set_tour_completed("u1"))
    assert result == {"ok": True, "tour_completed": True}
    assert calls == [("u1", {"tour_completed": True})]


# ── routes/system.py: /api/tour-complete ────────────────────────────


def test_tour_complete_route_passes_user_id_to_controller(monkeypatch):
    called = {}

    async def fake_set_tour_completed(user_id):
        called["user_id"] = user_id
        return {"ok": True, "tour_completed": True}

    monkeypatch.setattr(
        system_routes.ctrl, "set_tour_completed", fake_set_tour_completed
    )
    result = asyncio.run(system_routes.tour_complete(user_token={"user_id": "u1"}))
    assert result == {"ok": True, "tour_completed": True}
    assert called["user_id"] == "u1"


def test_state_route_passes_all_dependencies_to_controller(monkeypatch):
    called = {}

    async def fake_get_current_workspace(x_workspace_id, user_token):
        called["auth_workspace"] = (x_workspace_id, user_token)
        return {"workspace_id": "verified-w1", "role": "member", "user_id": "u1"}

    async def fake_get_state(user_id, workspace_id, db_id, db, cfg, kb):
        called["args"] = (user_id, workspace_id, db_id, db, cfg, kb)
        return {"connected": False}

    monkeypatch.setattr(
        system_routes, "get_current_workspace", fake_get_current_workspace
    )
    monkeypatch.setattr(system_routes.ctrl, "get_state", fake_get_state)
    result = asyncio.run(
        system_routes.state(
            user_token={"user_id": "u1"},
            x_workspace_id="w1",
            x_db_id="db1",
            db="db-ref",
            cfg="cfg-ref",
            kb="kb-ref",
        )
    )
    assert result == {"connected": False}
    assert called["auth_workspace"] == ("w1", {"user_id": "u1"})
    assert called["args"] == ("u1", "verified-w1", "db1", "db-ref", "cfg-ref", "kb-ref")
