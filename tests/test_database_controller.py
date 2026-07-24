import asyncio
from types import SimpleNamespace

import backend.app.controllers.database as database_ctrl
import backend.app.routes.database as database_routes


class DummyKB:
    async def trust_level(self, workspace_id, db_id):
        """Return the trust level associated with a database.

        Parameters:
                workspace_id: The user requesting the trust level.
                db_id: The database identifier.

        Returns:
                str: The database trust level.
        """
        return f"trust:{db_id}"

    async def get_glossary(self, workspace_id, db_id):
        """Return glossary entries for a database.

        Parameters:
                workspace_id: The user requesting the glossary.
                db_id: The database identifier.

        Returns:
                A list containing the database identifier.
        """
        return [{"db_id": db_id}]

    async def count_verified(self, workspace_id, db_id):
        """Count the verified entries for a database.

        Parameters:
            workspace_id: Identifier of the user requesting the count.
            db_id: Identifier of the database.

        Returns:
            int: The number of verified entries.
        """
        return 1

    async def get_verified(self, workspace_id, db_id):
        """Return a verified starter question for the specified database.

        Parameters:
            db_id: Identifier of the database.

        Returns:
            A list containing the starter question for the database.
        """
        return [{"question": f"starter:{db_id}"}]

    async def seed_sample(self, workspace_id, db_id):
        return


def test_connect_uses_user_scoped_connect_and_result_metadata(monkeypatch):
    class DummyDB:
        def __init__(self):
            self.args = None

        def connect(self, workspace_id, url):
            self.args = (workspace_id, url)
            return {
                "ok": True,
                "dialect": "sqlite",
                "tables": 3,
                "db_id": "db-123",
                "url": "sqlite:///tmp.db",
            }

    saved = {}

    async def fake_save(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(database_ctrl.mdb, "save_recent_connection", fake_save)

    db = DummyDB()
    kb = DummyKB()
    cfg = {}
    req = SimpleNamespace(db_url="sqlite:///tmp.db")

    result = asyncio.run(database_ctrl.connect(db, kb, cfg, req, workspace_id="w1"))

    assert db.args == ("w1", "sqlite:///tmp.db")
    assert result["trust"] == "trust:db-123"
    assert saved["dialect"] == "sqlite"
    assert saved["db_id"] == "db-123"
    assert saved["table_count"] == 3


def test_connect_sample_uses_result_metadata_for_recent_connection(monkeypatch):
    class DummyDB:
        def connect(self, workspace_id, url):
            return {
                "ok": True,
                "dialect": "sqlite",
                "tables": 9,
                "db_id": "sample-db",
                "url": "sqlite:///sample.db",
            }

        def get_db_id(self, workspace_id):
            return "sample-db"

    saved = {}
    monkeypatch.setattr(
        database_ctrl, "ensure_sample_db", lambda: "sqlite:///sample.db"
    )

    async def fake_save(**kwargs):
        saved.update(kwargs)

    monkeypatch.setattr(database_ctrl.mdb, "save_recent_connection", fake_save)

    result = asyncio.run(
        database_ctrl.connect_sample(DummyDB(), DummyKB(), {}, workspace_id="w1")
    )

    assert result["is_sample"] is True
    assert saved["dialect"] == "sqlite"
    assert saved["db_id"] == "sample-db"
    assert saved["table_count"] == 9


def test_schema_route_passes_workspace_id_to_controller(monkeypatch):
    called = {}

    async def fake_get_schema(workspace_id, db, refresh, db_id=None):
        called["args"] = (workspace_id, db, refresh)
        return {"ok": True}

    monkeypatch.setattr(database_routes.ctrl, "get_schema", fake_get_schema)
    res = asyncio.run(
        database_routes.schema(
            refresh=True, workspace={"workspace_id": "w1"}, db="db-ref"
        )
    )

    assert res == {"ok": True}
    assert called["args"] == ("w1", "db-ref", True)
