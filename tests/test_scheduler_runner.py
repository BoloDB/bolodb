"""Tests for the scheduled-query runner and its email rendering.

The properties worth pinning down are the ones a user notices when they are
wrong: a report delivered twice, a report delivered hours late after a restart,
an alert that fires when it shouldn't, and untrusted database content landing
unescaped in an HTML email.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from backend.app.services import email as email_svc
from backend.app.services import email_templates as tpl
from backend.app.services import scheduler

NOW = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc)
WORKSPACE = "11111111-1111-1111-1111-111111111111"
SCHEDULE = "22222222-2222-2222-2222-222222222222"


def make_schedule(**overrides):
    base = {
        "id": SCHEDULE,
        "workspace_id": WORKSPACE,
        "name": "Daily signups",
        "sql": "SELECT 1",
        "cron": "0 9 * * *",
        "database_id": "db123",
        "recipients": ["ops@example.com"],
        "is_active": True,
        "max_rows": 50,
        "send_condition": "always",
        "condition_value": None,
        "attach_csv": False,
        "display_columns": None,
        "consecutive_failures": 0,
        "next_run_at": NOW.isoformat(),
        "starts_at": None,
        "ends_at": None,
    }
    base.update(overrides)
    return base


@pytest.fixture
def fake_app():
    return SimpleNamespace(state=SimpleNamespace(db=object()))


@pytest.fixture
def patched(monkeypatch):
    """Stub out the database, the mail provider and persistence.

    Returns a namespace the test can assert against and reconfigure.
    """
    sent = []
    recorded = []
    finished = []

    async def fake_ensure_connection(db, workspace_id, db_id=None):
        return db_id or "db123"

    result = {
        "columns": ["email", "signups"],
        "rows": [{"email": "a@example.com", "signups": 3}],
        "row_count": 1,
        "truncated": False,
    }

    def fake_execute(workspace_id, sql, db_id=None):
        return dict(state.result)

    async def fake_send_email(to, subject, html, attachments=None):
        sent.append(
            {
                "to": to,
                "subject": subject,
                "html": html,
                "attachments": attachments,
            }
        )
        return state.send_ok

    async def fake_record_run(**kwargs):
        recorded.append(kwargs)
        return kwargs

    async def fake_finish(**kwargs):
        finished.append(kwargs)
        return True

    state = SimpleNamespace(
        sent=sent,
        recorded=recorded,
        finished=finished,
        result=result,
        send_ok=True,
    )

    import backend.app.controllers.database as db_ctrl

    monkeypatch.setattr(db_ctrl, "ensure_connection", fake_ensure_connection)
    monkeypatch.setattr(scheduler, "send_email", fake_send_email)
    monkeypatch.setattr(scheduler.mdb_sched, "record_run", fake_record_run)
    monkeypatch.setattr(scheduler.mdb_sched, "finish_schedule_run", fake_finish)
    state.fake_execute = fake_execute
    return state


@pytest.fixture
def app_with_db(fake_app, patched):
    fake_app.state.db = SimpleNamespace(execute=patched.fake_execute)
    return fake_app


# ── Delivery conditions ────────────────────────────────────────────


@pytest.mark.parametrize(
    "condition,threshold,rows,expected",
    [
        ("always", None, 0, True),
        ("always", None, 5, True),
        ("non_empty", None, 0, False),
        ("non_empty", None, 1, True),
        ("row_count_gte", 10, 9, False),
        ("row_count_gte", 10, 10, True),
        ("row_count_gte", 10, 11, True),
        ("row_count_lte", 5, 6, False),
        ("row_count_lte", 5, 5, True),
        ("unknown_condition", None, 0, True),
    ],
)
def test_should_send(condition, threshold, rows, expected):
    send, reason = scheduler.should_send(condition, threshold, rows)
    assert send is expected
    assert (reason == "") is expected


@pytest.mark.asyncio
async def test_successful_run_sends_and_records(app_with_db, patched):
    outcome = await scheduler.run_schedule(app_with_db, make_schedule())

    assert outcome["status"] == "success"
    assert outcome["row_count"] == 1
    assert len(patched.sent) == 1
    assert patched.sent[0]["to"] == ["ops@example.com"]
    assert patched.recorded[0]["status"] == "success"
    # A success resets the failure counter.
    assert patched.finished[0]["consecutive_failures"] == 0


@pytest.mark.asyncio
async def test_empty_result_with_non_empty_condition_skips_the_email(
    app_with_db, patched
):
    patched.result = {"columns": ["x"], "rows": [], "row_count": 0, "truncated": False}

    outcome = await scheduler.run_schedule(
        app_with_db, make_schedule(send_condition="non_empty")
    )

    assert outcome["status"] == "skipped"
    assert patched.sent == []
    # The skip is still recorded, so "why no email?" has an answer.
    assert patched.recorded[0]["status"] == "skipped"
    assert "no rows" in patched.recorded[0]["detail"]


@pytest.mark.asyncio
async def test_manual_run_ignores_the_condition(app_with_db, patched):
    """ "Run now" is how you check delivery works, so it always sends."""
    patched.result = {"columns": ["x"], "rows": [], "row_count": 0, "truncated": False}

    outcome = await scheduler.run_schedule(
        app_with_db, make_schedule(send_condition="non_empty"), manual=True
    )

    assert outcome["status"] == "success"
    assert len(patched.sent) == 1
    assert patched.sent[0]["subject"].startswith("[Test]")


@pytest.mark.asyncio
async def test_a_failed_manual_run_does_not_touch_the_failure_counter(
    app_with_db, patched, monkeypatch
):
    """A test send that fails must not auto-pause a schedule that is fine."""
    monkeypatch.setattr(scheduler.cfgmod, "SCHEDULE_MAX_FAILURES", 3)
    patched.result = {"error": "boom"}

    outcome = await scheduler.run_schedule(
        app_with_db, make_schedule(consecutive_failures=2), manual=True
    )

    assert outcome["status"] == "failed"
    # Recorded in the history...
    assert patched.recorded[0]["manual"] is True
    # ...but the counter is untouched, so nothing paused and nobody was mailed
    # a "we stopped your report" notice over a button press.
    assert patched.finished == []
    assert patched.sent == []


@pytest.mark.asyncio
async def test_a_successful_manual_run_does_not_clear_a_failure_streak(
    app_with_db, patched
):
    """Otherwise "Run now" would silently hide an ongoing scheduled failure."""
    outcome = await scheduler.run_schedule(
        app_with_db, make_schedule(consecutive_failures=2), manual=True
    )

    assert outcome["status"] == "success"
    assert patched.finished == []


@pytest.mark.asyncio
async def test_schedule_without_recipients_is_skipped_not_failed(app_with_db, patched):
    outcome = await scheduler.run_schedule(app_with_db, make_schedule(recipients=[]))

    assert outcome["status"] == "skipped"
    assert patched.sent == []


@pytest.mark.asyncio
async def test_query_error_is_recorded_as_a_failure(app_with_db, patched):
    patched.result = {"error": 'relation "signups" does not exist'}

    outcome = await scheduler.run_schedule(app_with_db, make_schedule())

    assert outcome["status"] == "failed"
    assert "does not exist" in outcome["detail"]
    assert patched.sent == []
    assert patched.finished[0]["consecutive_failures"] == 1


@pytest.mark.asyncio
async def test_mail_provider_failure_is_a_failed_run(app_with_db, patched):
    patched.send_ok = False

    outcome = await scheduler.run_schedule(app_with_db, make_schedule())

    assert outcome["status"] == "failed"
    assert "email could not be sent" in outcome["detail"]


@pytest.mark.asyncio
async def test_repeated_failures_pause_the_schedule_and_warn(
    app_with_db, patched, monkeypatch
):
    monkeypatch.setattr(scheduler.cfgmod, "SCHEDULE_MAX_FAILURES", 3)
    patched.result = {"error": "boom"}

    # Already failed twice; this run is the third.
    await scheduler.run_schedule(app_with_db, make_schedule(consecutive_failures=2))

    assert patched.finished[0]["consecutive_failures"] == 3
    assert patched.finished[0]["is_active"] is False
    # And the recipients are told, exactly once, that it stopped.
    assert len(patched.sent) == 1
    assert "paused" in patched.sent[0]["subject"].lower()


@pytest.mark.asyncio
async def test_csv_attachment_carries_every_row_not_just_the_inline_slice(
    app_with_db, patched
):
    patched.result = {
        "columns": ["n"],
        "rows": [{"n": i} for i in range(10)],
        "row_count": 10,
        "truncated": False,
    }

    await scheduler.run_schedule(
        app_with_db, make_schedule(attach_csv=True, max_rows=3)
    )

    attachments = patched.sent[0]["attachments"]
    assert attachments and attachments[0]["filename"].endswith(".csv")

    import base64

    csv_text = base64.b64decode(attachments[0]["content"]).decode()
    # Header plus all ten rows, even though only three are shown inline.
    assert len(csv_text.strip().splitlines()) == 11
    # The inline table shows the capped set.
    assert patched.sent[0]["html"].count("<td") == 3


@pytest.mark.asyncio
async def test_missing_connection_fails_with_an_actionable_message(
    fake_app, patched, monkeypatch
):
    import backend.app.controllers.database as db_ctrl

    async def no_connection(db, workspace_id, db_id=None):
        return None

    monkeypatch.setattr(db_ctrl, "ensure_connection", no_connection)
    fake_app.state.db = SimpleNamespace(execute=patched.fake_execute)

    outcome = await scheduler.run_schedule(fake_app, make_schedule())

    assert outcome["status"] == "failed"
    assert "no longer connected" in outcome["detail"]


# ── The tick: claiming, double-fire and misfires ───────────────────


@pytest.fixture
def tick_env(monkeypatch, app_with_db, patched):
    """Drive scheduler.tick against an in-memory set of due schedules."""
    state = SimpleNamespace(due=[], claims=[], claim_ok=True, ran=[])

    async def fake_list_due(now=None, limit=50):
        return list(state.due)

    async def fake_claim(schedule_id, expected_next_run_at, new_next_run_at, now=None):
        state.claims.append(
            {
                "id": schedule_id,
                "expected": expected_next_run_at,
                "new": new_next_run_at,
            }
        )
        return state.claim_ok

    async def fake_run(app, schedule, manual=False):
        state.ran.append(schedule["id"])
        return {"status": "success"}

    monkeypatch.setattr(scheduler.mdb_sched, "list_due_schedules", fake_list_due)
    monkeypatch.setattr(scheduler.mdb_sched, "claim_schedule", fake_claim)
    monkeypatch.setattr(scheduler, "run_schedule", fake_run)
    state.app = app_with_db
    state.patched = patched
    return state


@pytest.mark.asyncio
async def test_tick_claims_before_running_and_advances_the_slot(tick_env):
    tick_env.due = [make_schedule()]

    started = await scheduler.tick(tick_env.app, now=NOW)

    assert started == 1
    claim = tick_env.claims[0]
    # The CAS compares against the slot we read...
    assert claim["expected"] == NOW
    # ...and moves it to tomorrow's 09:00 before the query runs.
    assert claim["new"] == NOW + timedelta(days=1)
    assert tick_env.ran == [SCHEDULE]


@pytest.mark.asyncio
async def test_losing_the_claim_means_not_running(tick_env):
    """The guard against two workers mailing the same report twice."""
    tick_env.due = [make_schedule()]
    tick_env.claim_ok = False

    started = await scheduler.tick(tick_env.app, now=NOW)

    assert started == 0
    assert tick_env.ran == []


@pytest.mark.asyncio
async def test_a_long_missed_slot_is_skipped_rather_than_delivered_late(
    tick_env, monkeypatch
):
    monkeypatch.setattr(scheduler.cfgmod, "SCHEDULE_MISFIRE_GRACE_SECONDS", 3600)
    stale = NOW - timedelta(days=2)
    tick_env.due = [make_schedule(next_run_at=stale.isoformat())]

    started = await scheduler.tick(tick_env.app, now=NOW)

    assert started == 0
    assert tick_env.ran == []
    # It is still claimed (so the slot advances) and recorded as skipped.
    assert tick_env.claims[0]["expected"] == stale
    skipped = tick_env.patched.recorded[0]
    assert skipped["status"] == "skipped"
    assert "was not running" in skipped["detail"]


@pytest.mark.asyncio
async def test_a_slot_inside_the_grace_window_still_runs(tick_env, monkeypatch):
    monkeypatch.setattr(scheduler.cfgmod, "SCHEDULE_MISFIRE_GRACE_SECONDS", 3600)
    recent = NOW - timedelta(minutes=5)
    tick_env.due = [make_schedule(next_run_at=recent.isoformat())]

    assert await scheduler.tick(tick_env.app, now=NOW) == 1
    assert tick_env.ran == [SCHEDULE]


@pytest.mark.asyncio
async def test_a_schedule_past_its_end_date_retires_after_its_last_run(tick_env):
    tick_env.due = [make_schedule(ends_at=(NOW + timedelta(hours=1)).isoformat())]

    await scheduler.tick(tick_env.app, now=NOW)

    # No future slot inside the window, so next_run_at is cleared...
    assert tick_env.claims[0]["new"] is None
    # ...and the schedule is deactivated.
    assert tick_env.patched.finished[0]["is_active"] is False
    # The final occurrence still goes out.
    assert tick_env.ran == [SCHEDULE]


@pytest.mark.asyncio
async def test_tick_with_nothing_due_does_nothing(tick_env):
    assert await scheduler.tick(tick_env.app, now=NOW) == 0
    assert tick_env.claims == []


@pytest.mark.asyncio
async def test_due_schedules_run_concurrently_not_one_after_another(
    tick_env, monkeypatch
):
    """One slow report must not hold up the others, or the next tick."""
    tick_env.due = [make_schedule(id=f"sched-{i}") for i in range(3)]

    in_flight = 0
    peak = 0

    async def fake_run(app, schedule, manual=False):
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return {"status": "success"}

    monkeypatch.setattr(scheduler, "run_schedule", fake_run)

    started = await scheduler.tick(tick_env.app, now=NOW)

    assert started == 3
    # Sequential awaits would never put more than one run in flight, which is
    # what made SCHEDULE_MAX_CONCURRENT a no-op.
    assert peak > 1


@pytest.mark.asyncio
async def test_one_failing_run_does_not_abort_the_rest_of_the_tick(
    tick_env, monkeypatch
):
    tick_env.due = [make_schedule(id=f"sched-{i}") for i in range(3)]
    ran = []

    async def fake_run(app, schedule, manual=False):
        ran.append(schedule["id"])
        if schedule["id"] == "sched-1":
            raise RuntimeError("this one blew up")
        return {"status": "success"}

    monkeypatch.setattr(scheduler, "run_schedule", fake_run)

    started = await scheduler.tick(tick_env.app, now=NOW)

    assert started == 3
    assert sorted(ran) == ["sched-0", "sched-1", "sched-2"]


# ── Rendering ──────────────────────────────────────────────────────


class TestRendering:
    def test_cell_values_are_html_escaped(self):
        """Result cells are customer data and must never render as markup."""
        html = tpl.render_report_html(
            name="Report",
            columns=["note"],
            rows=[{"note": "<script>alert(1)</script>"}],
            total_rows=1,
        )
        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_column_names_are_escaped_too(self):
        html = tpl.render_report_html(
            name="Report",
            columns=["<img onerror=x>"],
            rows=[{"<img onerror=x>": 1}],
            total_rows=1,
        )
        assert "<img onerror=x>" not in html

    def test_author_written_intro_is_escaped_but_keeps_line_breaks(self):
        html = tpl.render_report_html(
            name="Report",
            columns=["a"],
            rows=[{"a": 1}],
            total_rows=1,
            intro="line one\nline two <b>",
            footer=None,
        )
        assert "line one<br>line two" in html
        assert "<b>" not in html

    def test_empty_result_renders_a_message_not_an_empty_table(self):
        html = tpl.render_report_html(
            name="Report", columns=["a"], rows=[], total_rows=0
        )
        assert "returned no rows" in html

    def test_row_counts_report_the_full_total_when_capped(self):
        html = tpl.render_report_html(
            name="Report",
            columns=["a"],
            rows=[{"a": i} for i in range(3)],
            total_rows=42,
        )
        assert "Showing the first 3 of 42 rows" in html

    def test_subject_template_placeholders(self):
        subject = tpl.render_subject(
            "{{name}}: {{row_count}} rows on {{date}}",
            name="Signups",
            row_count=7,
            when=datetime(2026, 8, 1, 9, 0),
        )
        assert subject == "Signups: 7 rows on 2026-08-01"

    def test_subject_falls_back_when_no_template(self):
        assert "Signups" in tpl.render_subject(None, name="Signups")
        assert "Signups" in tpl.render_subject("   ", name="Signups")

    def test_unknown_subject_placeholder_is_left_visible(self):
        """A typo should be obvious in the subject, not silently blanked."""
        assert (
            tpl.render_subject("{{nope}}", name="X", when=datetime(2026, 8, 1))
            == "{{nope}}"
        )

    def test_select_columns_filters_and_orders(self):
        assert tpl.select_columns(["a", "b", "c"], ["c", "a"]) == ["c", "a"]

    def test_select_columns_ignores_names_that_no_longer_exist(self):
        assert tpl.select_columns(["a", "b"], ["b", "gone"]) == ["b"]

    def test_select_columns_falls_back_to_everything(self):
        assert tpl.select_columns(["a", "b"], None) == ["a", "b"]
        assert tpl.select_columns(["a", "b"], []) == ["a", "b"]
        # A selection that is entirely stale is better than an empty report.
        assert tpl.select_columns(["a", "b"], ["gone"]) == ["a", "b"]

    def test_csv_neutralises_formula_injection(self):
        csv_text = tpl.build_csv(["f"], [{"f": "=cmd|'/c calc'!A1"}])
        assert "\n'=cmd" in csv_text

    def test_csv_neutralises_formula_injection_in_the_header_too(self):
        """Column names come from the customer's schema, so they need it as much."""
        csv_text = tpl.build_csv(["=1+1", "ok"], [])
        assert csv_text.splitlines()[0] == "'=1+1,ok"

    def test_csv_leaves_ordinary_values_alone(self):
        csv_text = tpl.build_csv(["a", "b"], [{"a": "hi", "b": 3}])
        assert csv_text.splitlines()[1] == "hi,3"

    def test_csv_filename_is_safe(self):
        name = tpl.csv_filename("Weekly / Report: Q3", datetime(2026, 8, 1, 9, 30))
        assert name == "Weekly-Report-Q3-20260801-0930.csv"
        assert "/" not in name


# ── Mail transport ─────────────────────────────────────────────────


class TestSenderAddress:
    def test_a_blank_from_address_falls_back_to_the_default(self, monkeypatch):
        """docker-compose substitutes an unset variable to "", not to nothing."""
        monkeypatch.setenv("RESEND_FROM_EMAIL", "")
        assert email_svc._get_from_email() == "noreply@bolodb.dev"
        monkeypatch.setenv("RESEND_FROM_EMAIL", "   ")
        assert email_svc._get_from_email() == "noreply@bolodb.dev"

    def test_a_configured_address_is_used(self, monkeypatch):
        monkeypatch.setenv("RESEND_FROM_EMAIL", "reports@acme.com")
        assert email_svc._get_from_email() == "reports@acme.com"
