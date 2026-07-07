import asyncio
from types import SimpleNamespace

import backend.app.controllers.database as database_ctrl
import backend.app.routes.database as database_routes


class DummyKB:
    def trust_level(self, db_id):
        return f"trust:{db_id}"

    def get_glossary(self, db_id):
        return [{"db_id": db_id}]

    def count_verified(self, db_id):
        return 1

    def get_verified(self, db_id):
        return [{"question": f"starter:{db_id}"}]


def test_connect_uses_user_scoped_connect_and_result_metadata(monkeypatch):
    class DummyDB:
        def __init__(self):
            self.args = None

        def connect(self, user_id, url):
            self.args = (user_id, url)
            return {
                "ok": True,
                "dialect": "sqlite",
                "tables": 3,
                "db_id": "db-123",
                "url": "sqlite:///tmp.db",
            }

    saved = {}
    monkeypatch.setattr(database_ctrl.cfgmod, "save_config", lambda cfg: None)
    monkeypatch.setattr(
        database_ctrl.mdb,
        "save_recent_connection",
        lambda **kwargs: saved.update(kwargs),
    )

    db = DummyDB()
    kb = DummyKB()
    cfg = {}
    req = SimpleNamespace(db_url="sqlite:///tmp.db")

    result = asyncio.run(database_ctrl.connect(db, kb, cfg, req, user_id="u1"))

    assert db.args == ("u1", "sqlite:///tmp.db")
    assert result["trust"] == "trust:db-123"
    assert saved["dialect"] == "sqlite"
    assert saved["db_id"] == "db-123"
    assert saved["table_count"] == 3


def test_connect_sample_uses_result_metadata_for_recent_connection(monkeypatch):
    class DummyDB:
        def connect(self, user_id, url):
            return {
                "ok": True,
                "dialect": "sqlite",
                "tables": 9,
                "db_id": "sample-db",
                "url": "sqlite:///sample.db",
            }

        def get_db_id(self, user_id):
            return "sample-db"

    saved = {}
    monkeypatch.setattr(
        database_ctrl, "ensure_sample_db", lambda: "sqlite:///sample.db"
    )
    monkeypatch.setattr(
        database_ctrl.mdb,
        "save_recent_connection",
        lambda **kwargs: saved.update(kwargs),
    )

    result = asyncio.run(
        database_ctrl.connect_sample(DummyDB(), DummyKB(), {}, user_id="u1")
    )

    assert result["is_sample"] is True
    assert saved["dialect"] == "sqlite"
    assert saved["db_id"] == "sample-db"
    assert saved["table_count"] == 9


def test_schema_route_passes_user_id_to_controller(monkeypatch):
    called = {}

    async def fake_get_schema(user_id, db, refresh):
        called["args"] = (user_id, db, refresh)
        return {"ok": True}

    monkeypatch.setattr(database_routes.ctrl, "get_schema", fake_get_schema)
    res = asyncio.run(
        database_routes.schema(refresh=True, user_token={"user_id": "u1"}, db="db-ref")
    )

    assert res == {"ok": True}
    assert called["args"] == ("u1", "db-ref", True)
