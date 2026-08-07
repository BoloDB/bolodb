"""Tests for the scheduled-queries API and its validation layer.

The controller is where a bad schedule gets caught before it becomes a report
that fires at the wrong time, mails the wrong people, or runs a statement that
was never meant to run unattended. Most of these tests live at that level; the
route tests cover the permission gates and the plumbing.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

import backend.app.controllers.schedules as ctrl
import backend.app.dependencies as deps
from backend.app.dependencies import get_current_user, get_current_workspace
from backend.app.pgdatabase.schedules import ScheduleLimitError
from backend.app.routes import schedules as schedule_routes

WORKSPACE_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())
SCHEDULE_ID = str(uuid.uuid4())


def valid_payload(**overrides):
    payload = {
        "name": "Daily signups",
        "sql": "SELECT count(*) FROM users",
        "cron": "0 9 * * *",
        "recipients": ["ops@example.com"],
    }
    payload.update(overrides)
    return payload


# ── Recipient handling ─────────────────────────────────────────────


class TestRecipients:
    def test_addresses_are_lowercased_and_deduped_in_order(self):
        assert ctrl.normalize_recipients(
            ["B@Example.com", "a@example.com", "b@example.com"]
        ) == ["b@example.com", "a@example.com"]

    def test_a_pasted_blob_is_split_on_whitespace_and_punctuation(self):
        assert ctrl.normalize_recipients("a@x.com, b@x.com; c@x.com") == [
            "a@x.com",
            "b@x.com",
            "c@x.com",
        ]

    def test_empty_input_is_an_empty_list(self):
        assert ctrl.normalize_recipients(None) == []
        assert ctrl.normalize_recipients([]) == []
        assert ctrl.normalize_recipients("  ") == []

    @pytest.mark.parametrize(
        "bad", ["not-an-email", "@example.com", "a@b", "a b@example.com"]
    )
    def test_malformed_addresses_are_rejected(self, bad):
        with pytest.raises(HTTPException) as exc:
            ctrl.normalize_recipients([bad])
        assert exc.value.status_code == 400

    def test_too_many_recipients_is_rejected(self):
        many = [f"user{i}@example.com" for i in range(ctrl.MAX_RECIPIENTS + 1)]
        with pytest.raises(HTTPException):
            ctrl.normalize_recipients(many)


# ── Payload validation ─────────────────────────────────────────────


class TestValidation:
    def test_a_valid_payload_passes_through(self):
        clean = ctrl.validate_payload(valid_payload())
        assert clean["cron"] == "0 9 * * *"
        assert clean["recipients"] == ["ops@example.com"]

    @pytest.mark.parametrize("field", ["name", "sql", "cron"])
    def test_required_fields_are_required_on_create(self, field):
        payload = valid_payload()
        payload.pop(field)
        with pytest.raises(HTTPException):
            ctrl.validate_payload(payload, partial=False)

    def test_partial_updates_only_check_what_is_present(self):
        clean = ctrl.validate_payload({"name": "Renamed"}, partial=True)
        assert clean == {"name": "Renamed"}

    @pytest.mark.parametrize(
        "sql",
        [
            "DELETE FROM users",
            "UPDATE users SET admin = true",
            "DROP TABLE users",
            "SELECT 1; DROP TABLE users",
            "SELECT * INTO copies FROM users",
        ],
    )
    def test_write_statements_cannot_be_scheduled(self, sql):
        """The read-only guarantee matters most for unattended, repeating runs."""
        with pytest.raises(HTTPException) as exc:
            ctrl.validate_payload(valid_payload(sql=sql))
        assert "read-only" in exc.value.detail

    def test_a_table_named_like_a_keyword_is_still_allowed(self):
        clean = ctrl.validate_payload(valid_payload(sql="SELECT * FROM updates_log"))
        assert clean["sql"] == "SELECT * FROM updates_log"

    def test_invalid_cron_is_rejected(self):
        with pytest.raises(HTTPException):
            ctrl.validate_payload(valid_payload(cron="not a cron"))

    def test_end_before_start_is_rejected(self):
        with pytest.raises(HTTPException) as exc:
            ctrl.validate_payload(
                valid_payload(
                    starts_at="2026-09-10T00:00:00Z", ends_at="2026-09-01T00:00:00Z"
                )
            )
        assert "after the start" in exc.value.detail

    def test_timestamps_are_parsed_to_utc_aware_datetimes(self):
        clean = ctrl.validate_payload(valid_payload(starts_at="2026-09-01T00:00:00Z"))
        assert clean["starts_at"].tzinfo is not None

    @pytest.mark.parametrize("bad", [0, -5, 100_000, "many"])
    def test_max_rows_is_bounded(self, bad):
        with pytest.raises(HTTPException):
            ctrl.validate_payload(valid_payload(max_rows=bad))

    def test_unknown_send_condition_is_rejected(self):
        with pytest.raises(HTTPException):
            ctrl.validate_payload(valid_payload(send_condition="whenever"))

    def test_a_threshold_condition_needs_a_threshold(self):
        with pytest.raises(HTTPException) as exc:
            ctrl.validate_payload(valid_payload(send_condition="row_count_gte"))
        assert "condition_value" in exc.value.detail

    def test_threshold_is_cleared_for_conditions_that_do_not_use_one(self):
        clean = ctrl.validate_payload(
            valid_payload(send_condition="non_empty", condition_value=5)
        )
        assert clean["condition_value"] is None

    def test_a_threshold_sent_alone_on_patch_is_still_validated(self):
        """A PATCH can retune the threshold without restating send_condition."""
        clean = ctrl.validate_payload({"condition_value": "12"}, partial=True)
        assert clean["condition_value"] == 12

        with pytest.raises(HTTPException):
            ctrl.validate_payload({"condition_value": -1}, partial=True)
        with pytest.raises(HTTPException):
            ctrl.validate_payload({"condition_value": "lots"}, partial=True)

    def test_display_columns_must_be_strings(self):
        with pytest.raises(HTTPException):
            ctrl.validate_payload(valid_payload(display_columns=[1, 2]))


# ── Create / update behaviour ──────────────────────────────────────


class TestCreate:
    @pytest.mark.asyncio
    async def test_create_computes_the_first_run(self, monkeypatch):
        captured = {}

        async def fake_create(workspace_id, user_id, **kwargs):
            captured.update(kwargs)
            return {"id": SCHEDULE_ID, **kwargs}

        monkeypatch.setattr(ctrl.mdb_sched, "create_schedule", fake_create)

        created = await ctrl.create_schedule(WORKSPACE_ID, USER_ID, valid_payload())

        assert captured["next_run_at"] is not None
        assert captured["next_run_at"].hour == 9
        # The response carries the derived fields the UI renders.
        assert created["cron_description"] == "Daily at 09:00 UTC"
        assert len(created["upcoming_runs"]) == 5

    @pytest.mark.asyncio
    async def test_create_requires_a_recipient(self, monkeypatch):
        monkeypatch.setattr(ctrl.mdb_sched, "create_schedule", AsyncMock())
        with pytest.raises(HTTPException) as exc:
            await ctrl.create_schedule(
                WORKSPACE_ID, USER_ID, valid_payload(recipients=[])
            )
        assert "recipient" in exc.value.detail

    @pytest.mark.asyncio
    async def test_a_window_with_no_runs_left_is_rejected(self, monkeypatch):
        monkeypatch.setattr(ctrl.mdb_sched, "create_schedule", AsyncMock())
        with pytest.raises(HTTPException) as exc:
            await ctrl.create_schedule(
                WORKSPACE_ID,
                USER_ID,
                valid_payload(ends_at="2020-01-01T00:00:00Z"),
            )
        assert "no runs left" in exc.value.detail

    @pytest.mark.asyncio
    async def test_hitting_the_workspace_cap_is_a_409(self, monkeypatch):
        async def at_limit(*a, **kw):
            raise ScheduleLimitError("too many")

        monkeypatch.setattr(ctrl.mdb_sched, "create_schedule", at_limit)
        with pytest.raises(HTTPException) as exc:
            await ctrl.create_schedule(WORKSPACE_ID, USER_ID, valid_payload())
        assert exc.value.status_code == 409


class TestUpdate:
    @pytest.fixture
    def existing(self):
        return {
            "id": SCHEDULE_ID,
            "workspace_id": WORKSPACE_ID,
            "cron": "0 9 * * *",
            "is_active": True,
            "starts_at": None,
            "ends_at": None,
            "consecutive_failures": 0,
        }

    @pytest.mark.asyncio
    async def test_changing_the_cron_recomputes_the_next_run(
        self, monkeypatch, existing
    ):
        captured = {}

        async def fake_update(workspace_id, schedule_id, **kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr(
            ctrl.mdb_sched, "get_schedule", AsyncMock(return_value=existing)
        )
        monkeypatch.setattr(ctrl.mdb_sched, "update_schedule", fake_update)

        await ctrl.update_schedule(WORKSPACE_ID, SCHEDULE_ID, {"cron": "0 17 * * *"})

        assert captured["next_run_at"].hour == 17

    @pytest.mark.asyncio
    async def test_renaming_alone_leaves_the_cadence_untouched(
        self, monkeypatch, existing
    ):
        captured = {}

        async def fake_update(workspace_id, schedule_id, **kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr(
            ctrl.mdb_sched, "get_schedule", AsyncMock(return_value=existing)
        )
        monkeypatch.setattr(ctrl.mdb_sched, "update_schedule", fake_update)

        await ctrl.update_schedule(WORKSPACE_ID, SCHEDULE_ID, {"name": "New name"})

        assert "next_run_at" not in captured

    @pytest.mark.asyncio
    async def test_pausing_clears_the_next_run(self, monkeypatch, existing):
        captured = {}

        async def fake_update(workspace_id, schedule_id, **kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr(
            ctrl.mdb_sched, "get_schedule", AsyncMock(return_value=existing)
        )
        monkeypatch.setattr(ctrl.mdb_sched, "update_schedule", fake_update)

        await ctrl.set_active(WORKSPACE_ID, SCHEDULE_ID, False)

        assert captured["next_run_at"] is None

    @pytest.mark.asyncio
    async def test_resuming_after_an_auto_pause_resets_the_failure_count(
        self, monkeypatch, existing
    ):
        existing["is_active"] = False
        existing["consecutive_failures"] = 5
        captured = {}

        async def fake_update(workspace_id, schedule_id, **kwargs):
            captured.update(kwargs)
            return True

        monkeypatch.setattr(
            ctrl.mdb_sched, "get_schedule", AsyncMock(return_value=existing)
        )
        monkeypatch.setattr(ctrl.mdb_sched, "update_schedule", fake_update)

        await ctrl.set_active(WORKSPACE_ID, SCHEDULE_ID, True)

        assert captured["consecutive_failures"] == 0
        assert captured["next_run_at"] is not None

    @pytest.mark.asyncio
    async def test_updating_a_missing_schedule_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            ctrl.mdb_sched, "get_schedule", AsyncMock(return_value=None)
        )
        assert (
            await ctrl.update_schedule(WORKSPACE_ID, SCHEDULE_ID, {"name": "x"}) is None
        )


@pytest.mark.asyncio
async def test_preview_returns_description_and_upcoming_runs():
    out = await ctrl.preview("0 9 * * 1")
    assert out["description"] == "Every Monday at 09:00 UTC"
    assert len(out["upcoming_runs"]) == 5


@pytest.mark.asyncio
async def test_preview_rejects_a_bad_expression():
    with pytest.raises(HTTPException):
        await ctrl.preview("* *")


# ── Routes ─────────────────────────────────────────────────────────


@pytest.fixture
def granted(monkeypatch):
    """Grant every permission without a database round trip.

    ``require_permission`` resolves the workspace's role-permission overrides out
    of Postgres. Patching the resolver on the dependencies module works because
    the closure looks it up as a global at call time.
    """
    checker = AsyncMock(return_value=True)
    monkeypatch.setattr(deps, "workspace_has_permission", checker)
    return checker


@pytest.fixture
def app(granted):
    application = FastAPI()
    application.include_router(schedule_routes.router)
    application.state.limiter = SimpleNamespace(enabled=False)
    application.dependency_overrides[get_current_workspace] = lambda: {
        "workspace_id": WORKSPACE_ID,
        "role": "admin",
        "user_id": USER_ID,
    }
    application.dependency_overrides[get_current_user] = lambda: {"user_id": USER_ID}
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app, monkeypatch):
    monkeypatch.setattr(schedule_routes, "log_activity", AsyncMock())
    return TestClient(app)


def test_mutating_routes_require_schedules_manage(client, granted, monkeypatch):
    """A member with only schedules.view must not be able to create one."""
    monkeypatch.setattr(ctrl, "create_schedule", AsyncMock())
    granted.side_effect = lambda workspace, key: key != "schedules.manage"

    res = client.post("/api/schedules", json=valid_payload())

    assert res.status_code == 403
    assert "schedules.manage" in res.json()["detail"]


def test_read_routes_require_schedules_view(client, granted, monkeypatch):
    monkeypatch.setattr(ctrl, "list_schedules", AsyncMock(return_value=[]))
    granted.side_effect = lambda workspace, key: False

    response = client.get("/api/schedules")
    assert response.status_code == 403


def test_list_returns_schedules_and_the_cap(client, monkeypatch):
    monkeypatch.setattr(
        ctrl, "list_schedules", AsyncMock(return_value=[{"id": SCHEDULE_ID}])
    )
    res = client.get("/api/schedules")
    assert res.status_code == 200
    body = res.json()
    assert body["schedules"] == [{"id": SCHEDULE_ID}]
    assert body["max_schedules"] == ctrl.MAX_SCHEDULES_PER_WORKSPACE


def test_create_returns_201(client, monkeypatch):
    monkeypatch.setattr(
        ctrl,
        "create_schedule",
        AsyncMock(return_value={"id": SCHEDULE_ID, "name": "Daily signups"}),
    )
    res = client.post("/api/schedules", json=valid_payload())
    assert res.status_code == 201
    assert res.json()["id"] == SCHEDULE_ID


def test_create_surfaces_validation_errors_as_400(client, monkeypatch):
    monkeypatch.setattr(
        ctrl,
        "create_schedule",
        AsyncMock(side_effect=HTTPException(400, "Only read-only queries")),
    )
    res = client.post("/api/schedules", json=valid_payload(sql="DELETE FROM t"))
    assert res.status_code == 400
    assert "read-only" in res.json()["detail"]


def test_get_missing_schedule_is_404(client, monkeypatch):
    monkeypatch.setattr(ctrl, "get_schedule", AsyncMock(return_value=None))
    response = client.get(f"/api/schedules/{SCHEDULE_ID}")
    assert response.status_code == 404


def test_delete_missing_schedule_is_404(client, monkeypatch):
    monkeypatch.setattr(ctrl, "delete_schedule", AsyncMock(return_value=False))
    response = client.delete(f"/api/schedules/{SCHEDULE_ID}")
    assert response.status_code == 404


def test_pause_toggles_the_active_flag(client, monkeypatch):
    monkeypatch.setattr(
        ctrl,
        "get_schedule",
        AsyncMock(return_value={"id": SCHEDULE_ID, "is_active": True}),
    )
    set_active = AsyncMock(return_value={"id": SCHEDULE_ID, "is_active": False})
    monkeypatch.setattr(ctrl, "set_active", set_active)

    res = client.post(f"/api/schedules/{SCHEDULE_ID}/pause")

    assert res.status_code == 200
    # An active schedule is toggled off.
    assert set_active.await_args.args[2] is False


def test_history_is_scoped_to_an_existing_schedule(client, monkeypatch):
    monkeypatch.setattr(
        ctrl, "get_schedule", AsyncMock(return_value={"id": SCHEDULE_ID})
    )
    monkeypatch.setattr(
        ctrl, "list_runs", AsyncMock(return_value=[{"status": "success"}])
    )
    res = client.get(f"/api/schedules/{SCHEDULE_ID}/history")
    assert res.status_code == 200
    assert res.json()["runs"] == [{"status": "success"}]


def test_history_for_a_missing_schedule_is_404(client, monkeypatch):
    monkeypatch.setattr(ctrl, "get_schedule", AsyncMock(return_value=None))
    response = client.get(f"/api/schedules/{SCHEDULE_ID}/history")
    assert response.status_code == 404


def test_run_now_reports_the_outcome(client, monkeypatch):
    monkeypatch.setattr(
        ctrl,
        "run_now",
        AsyncMock(return_value={"found": True, "status": "success", "row_count": 3}),
    )
    res = client.post(f"/api/schedules/{SCHEDULE_ID}/run")
    assert res.status_code == 200
    assert res.json()["row_count"] == 3


def test_run_now_on_a_missing_schedule_is_404(client, monkeypatch):
    monkeypatch.setattr(ctrl, "run_now", AsyncMock(return_value={"found": False}))
    response = client.post(f"/api/schedules/{SCHEDULE_ID}/run")
    assert response.status_code == 404


def test_preview_route_does_not_collide_with_the_id_route(client):
    """POST /preview must reach the preview handler, not be read as an id."""
    res = client.post("/api/schedules/preview", json={"cron": "0 9 * * *"})
    assert res.status_code == 200
    assert res.json()["description"] == "Daily at 09:00 UTC"


def test_preview_route_rejects_a_bad_expression(client):
    res = client.post("/api/schedules/preview", json={"cron": "nope"})
    assert res.status_code == 400
