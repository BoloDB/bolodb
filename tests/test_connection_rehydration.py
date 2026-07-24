"""A workspace's database must survive the process that connected it.

Live engines are held in memory. Before this, a restart, a redeploy, or a
request served by a different worker left none — and every screen read that as
the user having disconnected, bouncing them to the connect screen with their
database apparently gone. The credentials are already stored against the
workspace, so the connection is re-established from them instead.

These tests drive `ensure_connection` directly and then check the behaviour
`/api/state` depends on, since that endpoint is what decides whether the app
shows a database at all.
"""

import asyncio

import pytest

from backend.app.controllers import database as db_ctrl
from backend.app.controllers import system as system_ctrl

WORKSPACE = "workspace-1"
DB_ID = "abc123def456"
OTHER_DB_ID = "999888777666"
STORED_URL = "postgresql://reader:secret@db.example.com:5432/analytics"


class RestartedDB:
    """A manager that has lost its connections, as after a process restart."""

    def __init__(self, connected_ids=(), connect_ok=True):
        self.connected_ids = set(connected_ids)
        self.connect_ok = connect_ok
        self.connect_calls = []

    def connected(self, workspace_id, db_id=None):
        if db_id:
            return db_id in self.connected_ids
        return bool(self.connected_ids)

    def get_db_id(self, workspace_id, db_id=None):
        return db_id or next(iter(self.connected_ids))

    def connect(self, workspace_id, url):
        self.connect_calls.append((workspace_id, url))
        if not self.connect_ok:
            return {"ok": False, "error": "could not connect to server"}
        self.connected_ids.add(DB_ID)
        return {"ok": True, "dialect": "postgresql", "tables": 12, "db_id": DB_ID}

    def get_info(self, workspace_id, db_id=None):
        return {
            "url": "postgresql://reader:***@db.example.com:5432/analytics",
            "tables": 12,
        }

    def get_dialect(self, workspace_id, db_id=None):
        return "postgresql"


def _stored(db_id=DB_ID, url=STORED_URL, alias="Analytics"):
    return {
        "id": "row-1",
        "db_id": db_id,
        "db_url": url,
        "display_url": "postgresql://reader:***@db.example.com:5432/analytics",
        "alias_name": alias,
        "dialect": "postgresql",
        "table_count": 12,
    }


@pytest.fixture
def stored_connection(monkeypatch):
    """Install a stored connection and report which lookups were used."""
    seen = {"by_db_id": [], "latest": []}

    def install(by_db_id=None, latest=None, raises=False):
        async def fake_by_db_id(workspace_id, db_id):
            seen["by_db_id"].append((workspace_id, db_id))
            if raises:
                raise RuntimeError("Failed to decrypt stored connection URL")
            return by_db_id

        async def fake_latest(workspace_id):
            seen["latest"].append(workspace_id)
            if raises:
                raise RuntimeError("Failed to decrypt stored connection URL")
            return latest

        monkeypatch.setattr(
            db_ctrl.mdb, "get_recent_connection_by_db_id", fake_by_db_id
        )
        monkeypatch.setattr(db_ctrl.mdb, "get_latest_recent_connection", fake_latest)
        return seen

    return install


def test_live_connection_is_used_without_touching_storage(stored_connection):
    seen = stored_connection(by_db_id=_stored())
    db = RestartedDB(connected_ids={DB_ID})

    resolved = asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, DB_ID))

    assert resolved == DB_ID
    assert db.connect_calls == [], "a connected database must not be reconnected"
    assert seen["by_db_id"] == [], "stored credentials shouldn't be read when connected"


def test_requested_database_is_restored_from_stored_credentials(stored_connection):
    stored_connection(by_db_id=_stored())
    db = RestartedDB()  # nothing connected — as after a restart

    resolved = asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, DB_ID))

    assert resolved == DB_ID
    assert db.connect_calls == [(WORKSPACE, STORED_URL)], (
        "the stored URL should have been used to reconnect"
    )


def test_without_a_requested_id_the_most_recent_connection_is_restored(
    stored_connection,
):
    seen = stored_connection(latest=_stored())
    db = RestartedDB()

    resolved = asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, None))

    assert resolved == DB_ID
    assert seen["latest"] == [WORKSPACE]
    assert db.connect_calls == [(WORKSPACE, STORED_URL)]


def test_no_stored_connection_means_no_database(stored_connection):
    stored_connection(by_db_id=None, latest=None)
    db = RestartedDB()

    assert asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, DB_ID)) is None
    assert asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, None)) is None
    assert db.connect_calls == []


def test_unreachable_database_reports_no_connection_rather_than_raising(
    stored_connection,
):
    """A database that is stored but down must not 500 the whole request."""
    stored_connection(by_db_id=_stored())
    db = RestartedDB(connect_ok=False)

    assert asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, DB_ID)) is None
    assert db.connect_calls == [(WORKSPACE, STORED_URL)]


def test_undecryptable_credentials_report_no_connection(stored_connection):
    stored_connection(raises=True)
    db = RestartedDB()

    assert asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, DB_ID)) is None
    assert db.connect_calls == []


def test_missing_workspace_never_reaches_storage(stored_connection):
    seen = stored_connection(by_db_id=_stored())

    assert asyncio.run(db_ctrl.ensure_connection(RestartedDB(), None, DB_ID)) is None
    assert seen["by_db_id"] == []


# ── the sample database self-heals without stored credentials ───────


def test_sample_is_rebuilt_when_targeted_with_nothing_stored(
    stored_connection, tmp_path, monkeypatch
):
    """Requesting the sample after a restart must work with zero config.

    The sample needs no saved credentials — it's regenerable — so even with no
    stored row and no encryption key, targeting its db_id rebuilds and connects
    it instead of returning "no database connected".
    """
    from backend.app.database import DatabaseManager
    from backend import sample_data

    monkeypatch.setattr(sample_data, "_DATA_DIR", tmp_path)
    monkeypatch.delenv("RECENT_CONNECTIONS_KEY", raising=False)
    stored_connection(by_db_id=None, latest=None)

    db = DatabaseManager()
    sample_id = db_ctrl._sample_db_id()

    resolved = asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, sample_id))

    assert resolved == sample_id, "the sample must reconnect from its own dump"
    assert db.connected(WORKSPACE, sample_id)


def test_non_sample_db_id_still_reports_no_connection(stored_connection):
    """The rebuild path is only for the sample, not any missing database."""
    stored_connection(by_db_id=None, latest=None)
    db = RestartedDB()

    assert asyncio.run(db_ctrl.ensure_connection(db, WORKSPACE, DB_ID)) is None
    assert db.connect_calls == []


# ── what the app actually sees ──────────────────────────────────────


class RecordingKB:
    async def count_verified(self, workspace_id, db_id):
        return 3

    async def trust_level(self, workspace_id, db_id):
        return {"level": "Supervised", "verified": 3}

    async def get_glossary(self, workspace_id, db_id):
        return []

    async def get_verified(self, workspace_id, db_id):
        return [{"question": "How many orders?"}]


def test_state_shows_the_database_again_after_a_restart(monkeypatch, stored_connection):
    """The regression the user hit: reconnect, then /api/state says connected."""
    stored_connection(by_db_id=_stored())

    async def fake_user(user_id):
        return {"tour_completed": True}

    async def fake_by_db_id(workspace_id, db_id):
        return _stored()

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_user)
    monkeypatch.setattr(
        system_ctrl.mdb, "get_recent_connection_by_db_id", fake_by_db_id
    )

    db = RestartedDB()  # the engine this workspace had is gone
    state = asyncio.run(
        system_ctrl.get_state(
            "user-1", WORKSPACE, DB_ID, db, {"last_db_url": "x"}, RecordingKB()
        )
    )

    assert state["connected"] is True, "a restart must not look like a disconnect"
    assert state["database"]["db_id"] == DB_ID
    assert state["database"]["alias_name"] == "Analytics", (
        "the header labels the database from this alias"
    )
    assert db.connect_calls == [(WORKSPACE, STORED_URL)]


def test_state_reports_disconnected_when_nothing_is_stored(
    monkeypatch, stored_connection
):
    stored_connection(by_db_id=None, latest=None)

    async def fake_user(user_id):
        return {"tour_completed": False}

    monkeypatch.setattr(system_ctrl.mdb, "get_user_by_id", fake_user)

    state = asyncio.run(
        system_ctrl.get_state(
            "user-1", WORKSPACE, None, RestartedDB(), {}, RecordingKB()
        )
    )

    assert state["connected"] is False
    assert "database" not in state
