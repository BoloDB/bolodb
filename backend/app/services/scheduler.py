"""The background loop that runs scheduled queries and emails their results.

A plain asyncio loop started from the app lifespan, following
``activity_cleanup_loop``. Every tick asks Postgres for schedules whose
``next_run_at`` has passed, claims each one with a compare-and-swap, and runs it.

Two properties matter more than throughput here:

*Never send twice.* The claim advances ``next_run_at`` before the query runs, so
a crash mid-run loses an occurrence rather than replaying it. A missing report
gets noticed and re-run; a duplicate one is already read.

*Never take the server down.* Every failure path is caught and recorded against
the schedule. A broken query, an unreachable database and a dead mail provider
are all just rows in the run history.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi.concurrency import run_in_threadpool

from backend.app import config as cfgmod
from backend.app.pgdatabase import schedules as mdb_sched
from backend.app.secrets import get_frontend_url
from backend.app.services import cron
from backend.app.services.email import attachment_from_text, send_email
from backend.app.services.email_templates import (
    build_csv,
    csv_filename,
    render_failure_html,
    render_report_html,
    render_subject,
    select_columns,
)

log = logging.getLogger(__name__)

# How many due schedules one tick will pick up. Anything past this waits for the
# next tick rather than being run all at once.
DUE_BATCH_SIZE = 50

_RUN_SLOTS: asyncio.Semaphore | None = None


def _run_slots() -> asyncio.Semaphore:
    """Concurrency limiter bound to whichever loop is running.

    Created lazily for the same reason the Slack bot's is: a Semaphore latches
    onto the first loop that awaits it, which under pytest's fresh-loop-per-test
    turns into "bound to a different event loop".
    """
    global _RUN_SLOTS
    loop = asyncio.get_running_loop()
    if _RUN_SLOTS is None or getattr(_RUN_SLOTS, "_bolodb_loop", None) is not loop:
        _RUN_SLOTS = asyncio.Semaphore(cfgmod.SCHEDULE_MAX_CONCURRENT)
        _RUN_SLOTS._bolodb_loop = loop
    return _RUN_SLOTS


def _parse_dt(value) -> datetime | None:
    """Read a timestamp back out of a serialized schedule row."""
    if value is None or isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _manage_url() -> str | None:
    base = (get_frontend_url() or "").rstrip("/")
    return f"{base}/schedules" if base else None


def _wait_timeout(app) -> float:
    """How long to await one run before giving up on it.

    ``asyncio.wait_for`` only stops *awaiting* the run — the SQL itself is in a
    threadpool worker and keeps going until the server-side ``statement_timeout``
    kills it. So this has to stay the outer of the two bounds; configure it below
    the statement timeout and every slow query would leak a busy worker while the
    run is already recorded as timed out. The floor makes that unconfigurable.
    """
    configured = float(cfgmod.SCHEDULE_QUERY_TIMEOUT_SECONDS)
    server_side = getattr(getattr(app.state, "db", None), "statement_timeout", 0) or 0
    return max(configured, float(server_side) + 5)


def should_send(
    condition: str, threshold: int | None, row_count: int
) -> tuple[bool, str]:
    """Apply the schedule's delivery condition to a result.

    Returns (send, reason); ``reason`` explains a suppression for the run history.
    """
    if condition == "non_empty":
        if row_count == 0:
            return False, "Condition not met: query returned no rows"
        return True, ""
    if condition == "row_count_gte":
        limit = threshold or 0
        if row_count < limit:
            return False, f"Condition not met: {row_count} rows, needs at least {limit}"
        return True, ""
    if condition == "row_count_lte":
        limit = threshold or 0
        if row_count > limit:
            return False, f"Condition not met: {row_count} rows, needs at most {limit}"
        return True, ""
    return True, ""


async def run_schedule(app, schedule: dict, manual: bool = False) -> dict:
    """Execute one schedule end to end and record the outcome.

    Returns a summary dict — ``{"status", "row_count", "detail", "delivered_to"}``
    — which the "Run now" endpoint hands straight back to the caller. Never
    raises: every failure becomes a recorded run.
    """
    started = datetime.now(timezone.utc)
    schedule_id = schedule["id"]
    workspace_id = schedule["workspace_id"]
    name = schedule.get("name") or "Scheduled report"

    status = "failed"
    detail: str | None = None
    row_count: int | None = None
    delivered_to: list[str] | None = None

    try:
        async with _run_slots():
            outcome = await asyncio.wait_for(
                _execute_and_deliver(app, schedule, manual),
                timeout=_wait_timeout(app),
            )
        status = outcome["status"]
        detail = outcome.get("detail")
        row_count = outcome.get("row_count")
        delivered_to = outcome.get("delivered_to")
    except asyncio.TimeoutError:
        detail = (
            f"The query did not finish within "
            f"{int(_wait_timeout(app))}s and was stopped."
        )
        log.warning("Scheduled query %s (%s) timed out", schedule_id, name)
    except asyncio.CancelledError:
        # Shutdown mid-run. Record it so the gap in the history is explained,
        # then let the cancellation continue.
        with contextlib.suppress(Exception):
            await mdb_sched.record_run(
                schedule_id=schedule_id,
                workspace_id=workspace_id,
                status="failed",
                started_at=started,
                detail="BoloDB restarted while this run was in flight.",
                manual=manual,
            )
        raise
    except Exception as e:
        detail = str(e)
        log.exception("Scheduled query %s (%s) failed", schedule_id, name)

    finished = datetime.now(timezone.utc)
    duration_ms = int((finished - started).total_seconds() * 1000)

    with contextlib.suppress(Exception):
        await mdb_sched.record_run(
            schedule_id=schedule_id,
            workspace_id=workspace_id,
            status=status,
            started_at=started,
            finished_at=finished,
            row_count=row_count,
            duration_ms=duration_ms,
            detail=detail,
            delivered_to=delivered_to,
            manual=manual,
        )

    # "Run now" is a delivery test, so it stays out of the failure counter: a
    # failed test must not auto-pause a healthy schedule (or fire the paused
    # alert at every recipient), and a successful one must not paper over a real
    # failure streak. record_run above still logs it either way.
    if not manual:
        await _write_back_state(schedule, status, detail)

    return {
        "status": status,
        "row_count": row_count,
        "detail": detail,
        "delivered_to": delivered_to,
        "duration_ms": duration_ms,
    }


async def _execute_and_deliver(app, schedule: dict, manual: bool) -> dict:
    """Run the SQL, apply the schedule's formatting rules, and send the email."""
    from backend.app.controllers.database import ensure_connection

    workspace_id = schedule["workspace_id"]
    name = schedule.get("name") or "Scheduled report"
    sql = (schedule.get("sql") or "").strip()
    if not sql:
        raise RuntimeError("This schedule has no SQL to run.")

    db = app.state.db
    db_id = await ensure_connection(db, workspace_id, schedule.get("database_id"))
    if not db_id:
        raise RuntimeError(
            "The database this report runs against is no longer connected. "
            "Reconnect it in BoloDB, then resume the schedule."
        )

    result = await run_in_threadpool(db.execute, workspace_id, sql, db_id)
    if "error" in result:
        raise RuntimeError(result["error"])

    all_columns = list(result.get("columns") or [])
    all_rows = list(result.get("rows") or [])
    total_rows = int(result.get("row_count") or len(all_rows))
    truncated = bool(result.get("truncated"))

    columns = select_columns(all_columns, schedule.get("display_columns"))
    max_rows = int(schedule.get("max_rows") or 50)
    inline_rows = all_rows[:max_rows]

    recipients = [r for r in (schedule.get("recipients") or []) if r]
    if not recipients:
        return {
            "status": "skipped",
            "row_count": total_rows,
            "detail": "No recipients configured for this schedule.",
        }

    condition = schedule.get("send_condition") or "always"
    if manual:
        # "Run now" is how someone checks the report actually lands, so it
        # delivers regardless of the alerting condition.
        send, reason = True, ""
    else:
        send, reason = should_send(
            condition, schedule.get("condition_value"), total_rows
        )
    if not send:
        return {"status": "skipped", "row_count": total_rows, "detail": reason}

    run_at = datetime.now(timezone.utc)
    subject = render_subject(
        schedule.get("subject_template"),
        name=name,
        row_count=total_rows,
        when=run_at,
    )
    if manual:
        subject = f"[Test] {subject}"

    html = render_report_html(
        name=name,
        columns=columns,
        rows=inline_rows,
        total_rows=total_rows,
        question=schedule.get("question"),
        sql=sql,
        intro=schedule.get("intro"),
        footer=schedule.get("footer"),
        schedule_summary=cron.describe(schedule.get("cron") or ""),
        truncated=truncated,
        run_at=run_at,
        manage_url=_manage_url(),
    )

    attachments = None
    if schedule.get("attach_csv"):
        # The attachment carries every row the query returned, not just the
        # inline slice — the row cap is a formatting choice, not a data one.
        attachments = [
            attachment_from_text(
                csv_filename(name, run_at), build_csv(columns, all_rows)
            )
        ]

    sent = await send_email(recipients, subject, html, attachments=attachments)
    if not sent:
        raise RuntimeError(
            "The report ran but the email could not be sent. "
            "Check that RESEND_API_KEY is configured and the sender domain is verified."
        )

    return {
        "status": "success",
        "row_count": total_rows,
        "delivered_to": recipients,
        "detail": None,
    }


async def _write_back_state(schedule: dict, status: str, detail: str | None) -> None:
    """Update the failure counter, pausing and alerting if a schedule is stuck."""
    schedule_id = schedule["id"]
    previous = int(schedule.get("consecutive_failures") or 0)

    if status == "failed":
        failures = previous + 1
        should_pause = failures >= cfgmod.SCHEDULE_MAX_FAILURES
    else:
        failures = 0
        should_pause = False

    with contextlib.suppress(Exception):
        await mdb_sched.finish_schedule_run(
            schedule_id=schedule_id,
            status=status,
            consecutive_failures=failures,
            is_active=False if should_pause else None,
        )

    if not should_pause:
        return

    log.warning(
        "Pausing scheduled query %s after %d consecutive failures",
        schedule_id,
        failures,
    )
    recipients = [r for r in (schedule.get("recipients") or []) if r]
    if not recipients:
        return
    with contextlib.suppress(Exception):
        await send_email(
            recipients,
            f"BoloDB paused “{schedule.get('name') or 'a scheduled report'}”",
            render_failure_html(
                name=schedule.get("name") or "Scheduled report",
                error=detail or "Unknown error",
                failures=failures,
                paused=True,
                sql=schedule.get("sql"),
                manage_url=_manage_url(),
            ),
        )


async def tick(app, now: datetime | None = None) -> int:
    """Run every schedule that is currently due. Returns how many were started.

    Split out from the loop so tests can drive a single pass, and so the loop
    body stays a sleep and a call.
    """
    moment = now or datetime.now(timezone.utc)
    due = await mdb_sched.list_due_schedules(moment, limit=DUE_BATCH_SIZE)
    if not due:
        return 0

    grace = timedelta(seconds=cfgmod.SCHEDULE_MISFIRE_GRACE_SECONDS)
    runs = []
    claimed_ids = []

    for schedule in due:
        slot = _parse_dt(schedule.get("next_run_at"))
        if slot is None:
            # Can't happen via list_due_schedules, which filters out NULLs — but
            # an unparseable timestamp would make the claim below a guaranteed
            # miss, and the grace check a TypeError that aborts the whole tick.
            continue

        upcoming = cron.next_run(
            schedule.get("cron") or "",
            after=moment,
            starts_at=_parse_dt(schedule.get("starts_at")),
            ends_at=_parse_dt(schedule.get("ends_at")),
        )

        # Claim first, whatever we decide to do with the occurrence. Losing the
        # CAS means another tick (or another process) already took it. A claim
        # that errors outright is treated the same way — one unreachable row
        # must not abandon the schedules already queued behind it, which would
        # leave their coroutines never awaited.
        try:
            claimed = await mdb_sched.claim_schedule(
                schedule_id=schedule["id"],
                expected_next_run_at=slot,
                new_next_run_at=upcoming,
                now=moment,
            )
        except Exception:
            log.exception("Could not claim scheduled query %s", schedule["id"])
            continue
        if not claimed:
            continue

        if upcoming is None:
            # No future occurrence inside the schedule's window — this is its
            # last run. Retire it now so it doesn't sit around due forever; the
            # occurrence we just claimed still goes out below.
            with contextlib.suppress(Exception):
                await mdb_sched.finish_schedule_run(
                    schedule_id=schedule["id"],
                    status=schedule.get("last_status") or "success",
                    consecutive_failures=int(schedule.get("consecutive_failures") or 0),
                    is_active=False,
                )

        if moment - slot > grace:
            # The server was down through this slot. Record the gap and move on
            # rather than delivering a report hours after the time it names.
            with contextlib.suppress(Exception):
                await mdb_sched.record_run(
                    schedule_id=schedule["id"],
                    workspace_id=schedule["workspace_id"],
                    status="skipped",
                    started_at=moment,
                    detail=(
                        f"Missed its {slot.strftime('%Y-%m-%d %H:%M UTC')} slot — "
                        "BoloDB was not running. Skipped to the next occurrence."
                    ),
                )
            continue

        runs.append(run_schedule(app, schedule))
        claimed_ids.append(schedule["id"])

    if not runs:
        return 0

    # Claim every due schedule first, then run them together. Awaiting each one
    # in the loop above would leave the semaphore in _run_slots with nothing to
    # limit, and would let a single slow report hold up every other schedule —
    # and the next tick — for the length of its timeout.
    outcomes = await asyncio.gather(*runs, return_exceptions=True)
    for schedule, outcome in zip(claimed_ids, outcomes):
        # run_schedule records its own failures, so anything surfacing here got
        # past that and would otherwise vanish into the gather.
        if isinstance(outcome, BaseException):
            log.error(
                "Scheduled query %s raised out of run_schedule",
                schedule,
                exc_info=outcome,
            )
    return len(runs)


async def scheduler_loop(app, interval_seconds: float | None = None) -> None:
    """Poll for due schedules forever. Started and cancelled by the lifespan."""
    interval = (
        interval_seconds
        if interval_seconds is not None
        else cfgmod.SCHEDULER_TICK_SECONDS
    )
    log.info("Scheduled queries enabled — polling every %.0fs", interval)
    while True:
        try:
            ran = await tick(app)
            if ran:
                log.info(
                    "Scheduler tick ran %d scheduled quer%s",
                    ran,
                    "y" if ran == 1 else "ies",
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Scheduler tick failed; retrying next interval")
        await asyncio.sleep(interval)
