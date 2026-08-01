"""Business logic for scheduled queries.

Routes stay thin; the validation that decides whether a schedule is *runnable*
lives here, because "will this actually fire, and will anyone get the mail?" is a
question worth answering at creation time rather than discovering at 9am.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from fastapi import HTTPException

from backend.app.models.scheduled_query import (
    MAX_INLINE_ROWS,
    SEND_CONDITIONS,
)
from backend.app.pgdatabase import schedules as mdb_sched
from backend.app.pgdatabase.schedules import (
    MAX_SCHEDULES_PER_WORKSPACE,
    ScheduleLimitError,
)
from backend.app.database import readonly_violation
from backend.app.services import cron

log = logging.getLogger(__name__)

MAX_RECIPIENTS = 25

# Deliberately permissive. The mail provider is the real authority on whether an
# address exists; this only catches the shapes that are certainly not addresses,
# so a valid-but-unusual address is never rejected outright.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


def _bad(message: str) -> HTTPException:
    return HTTPException(400, message)


def normalize_recipients(raw) -> list[str]:
    """Lower-case, de-duplicate and sanity-check a recipient list.

    Mirrors the frontend's ``parseEmailList``: order is preserved so the list
    reads back the way it was entered.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        candidates = re.split(r"[\s,;]+", raw)
    elif isinstance(raw, list):
        candidates = [str(item) for item in raw]
    else:
        raise _bad("Recipients must be a list of email addresses.")

    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        address = candidate.strip().lower()
        if not address:
            continue
        if not _EMAIL_RE.match(address):
            raise _bad(f"{candidate.strip()!r} is not a valid email address.")
        if address in seen:
            continue
        seen.add(address)
        out.append(address)

    if len(out) > MAX_RECIPIENTS:
        raise _bad(
            f"A schedule can have at most {MAX_RECIPIENTS} recipients, got {len(out)}."
        )
    return out


def _parse_when(value, field: str) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            raise _bad(f"{field} must be an ISO 8601 timestamp.") from None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def validate_payload(data: dict, *, partial: bool = False) -> dict:
    """Validate and normalise a create/update payload.

    ``partial`` is for PATCH: only the keys present are checked, so an update
    that touches the name alone doesn't have to resend the whole schedule.
    """
    clean = dict(data)

    if "name" in clean:
        name = (clean["name"] or "").strip()
        if not name:
            raise _bad("Give the schedule a name.")
        clean["name"] = name[:255]
    elif not partial:
        raise _bad("Give the schedule a name.")

    if "sql" in clean:
        sql = (clean["sql"] or "").strip()
        if not sql:
            raise _bad("A schedule needs SQL to run.")
        # A scheduled statement runs unattended and repeatedly, so the read-only
        # guarantee matters more here than anywhere else in the product. Checked
        # at creation as well as at execution: failing now is a form the user can
        # fix, failing at 9am is an email nobody gets. The dialect is left blank
        # because the connection may not be live at creation time — sqlglot's
        # default parse is the stricter reading, and db.execute re-checks with
        # the real dialect before anything runs.
        violation = readonly_violation(sql)
        if violation:
            raise _bad(f"Only read-only queries can be scheduled. {violation}")
        clean["sql"] = sql
    elif not partial:
        raise _bad("A schedule needs SQL to run.")

    if "cron" in clean:
        try:
            clean["cron"] = cron.validate(clean["cron"])
        except cron.CronError as e:
            raise _bad(str(e)) from None
    elif not partial:
        raise _bad("A schedule needs a cron expression.")

    if "recipients" in clean:
        clean["recipients"] = normalize_recipients(clean["recipients"])
    elif not partial:
        clean["recipients"] = []

    starts_at = _parse_when(clean.get("starts_at"), "starts_at")
    ends_at = _parse_when(clean.get("ends_at"), "ends_at")
    if "starts_at" in clean:
        clean["starts_at"] = starts_at
    if "ends_at" in clean:
        clean["ends_at"] = ends_at
    if starts_at and ends_at and ends_at <= starts_at:
        raise _bad("The end date must be after the start date.")

    if "max_rows" in clean and clean["max_rows"] is not None:
        try:
            max_rows = int(clean["max_rows"])
        except (TypeError, ValueError):
            raise _bad("max_rows must be a whole number.") from None
        if not 1 <= max_rows <= MAX_INLINE_ROWS:
            raise _bad(f"max_rows must be between 1 and {MAX_INLINE_ROWS}.")
        clean["max_rows"] = max_rows

    if "send_condition" in clean and clean["send_condition"] is not None:
        condition = str(clean["send_condition"])
        if condition not in SEND_CONDITIONS:
            raise _bad(f"send_condition must be one of {', '.join(SEND_CONDITIONS)}.")
        clean["send_condition"] = condition
        if condition in ("row_count_gte", "row_count_lte"):
            value = clean.get("condition_value")
            if value is None:
                raise _bad(
                    "A row-count condition needs a threshold in condition_value."
                )
            try:
                clean["condition_value"] = int(value)
            except (TypeError, ValueError):
                raise _bad("condition_value must be a whole number.") from None
            if clean["condition_value"] < 0:
                raise _bad("condition_value cannot be negative.")
        else:
            clean["condition_value"] = None

    if "display_columns" in clean and clean["display_columns"] is not None:
        columns = clean["display_columns"]
        if not isinstance(columns, list) or not all(
            isinstance(c, str) for c in columns
        ):
            raise _bad("display_columns must be a list of column names.")
        clean["display_columns"] = columns or None

    for field in ("subject_template", "intro", "footer", "description", "question"):
        if field in clean and clean[field] is not None:
            clean[field] = str(clean[field]).strip() or None

    return clean


def compute_next_run(schedule: dict) -> datetime | None:
    """Where the schedule's next firing time comes from, in one place."""
    if not schedule.get("is_active", True):
        return None
    return cron.next_run(
        schedule["cron"],
        after=datetime.now(timezone.utc),
        starts_at=schedule.get("starts_at"),
        ends_at=schedule.get("ends_at"),
    )


def decorate(schedule: dict) -> dict:
    """Add the derived fields the UI wants but the table doesn't store."""
    if not schedule:
        return schedule
    out = dict(schedule)
    expression = out.get("cron") or ""
    out["cron_description"] = cron.describe(expression)
    try:
        out["upcoming_runs"] = [
            moment.isoformat()
            for moment in cron.next_runs(
                expression,
                count=5,
                starts_at=_parse_when(out.get("starts_at"), "starts_at"),
                ends_at=_parse_when(out.get("ends_at"), "ends_at"),
            )
        ]
    except cron.CronError:
        out["upcoming_runs"] = []
    return out


async def list_schedules(workspace_id: str) -> list[dict]:
    rows = await mdb_sched.list_schedules(workspace_id)
    return [decorate(row) for row in rows]


async def get_schedule(workspace_id: str, schedule_id: str) -> dict | None:
    row = await mdb_sched.get_schedule(workspace_id, schedule_id)
    return decorate(row) if row else None


async def create_schedule(workspace_id: str, user_id: str | None, data: dict) -> dict:
    clean = validate_payload(data, partial=False)
    if not clean.get("recipients"):
        raise _bad(
            "Add at least one recipient — a report with nobody to send to "
            "would run and go nowhere."
        )

    clean.setdefault("is_active", True)
    clean["next_run_at"] = compute_next_run(
        {
            "cron": clean["cron"],
            "starts_at": clean.get("starts_at"),
            "ends_at": clean.get("ends_at"),
            "is_active": clean["is_active"],
        }
    )
    if clean["next_run_at"] is None and clean["is_active"]:
        raise _bad("That schedule has no runs left inside its start and end dates.")

    try:
        created = await mdb_sched.create_schedule(workspace_id, user_id, **clean)
    except ScheduleLimitError as e:
        raise HTTPException(409, str(e)) from None
    return decorate(created)


async def update_schedule(
    workspace_id: str, schedule_id: str, data: dict
) -> dict | None:
    existing = await mdb_sched.get_schedule(workspace_id, schedule_id)
    if not existing:
        return None

    clean = validate_payload(data, partial=True)
    if "recipients" in clean and not clean["recipients"]:
        raise _bad("A schedule needs at least one recipient.")

    # Anything that moves the firing times has to move next_run_at with it,
    # otherwise the schedule keeps running on its old cadence until it next fires.
    if {"cron", "starts_at", "ends_at", "is_active"} & clean.keys():
        merged = {
            "cron": clean.get("cron", existing.get("cron")),
            "starts_at": clean.get(
                "starts_at", _parse_when(existing.get("starts_at"), "starts_at")
            ),
            "ends_at": clean.get(
                "ends_at", _parse_when(existing.get("ends_at"), "ends_at")
            ),
            "is_active": clean.get("is_active", existing.get("is_active", True)),
        }
        clean["next_run_at"] = compute_next_run(merged)
        if clean["next_run_at"] is None and merged["is_active"]:
            raise _bad("That schedule has no runs left inside its start and end dates.")
        # Reactivating after an auto-pause should start from a clean slate.
        if clean.get("is_active") and not existing.get("is_active", True):
            clean["consecutive_failures"] = 0

    updated = await mdb_sched.update_schedule(workspace_id, schedule_id, **clean)
    if not updated:
        return None
    return await get_schedule(workspace_id, schedule_id)


async def set_active(workspace_id: str, schedule_id: str, is_active: bool):
    """Pause or resume, recomputing the next slot on resume."""
    return await update_schedule(workspace_id, schedule_id, {"is_active": is_active})


async def delete_schedule(workspace_id: str, schedule_id: str) -> bool:
    return await mdb_sched.delete_schedule(workspace_id, schedule_id)


async def list_runs(workspace_id: str, schedule_id: str, limit: int = 25):
    return await mdb_sched.list_runs(workspace_id, schedule_id, limit=limit)


async def preview(cron_expression: str, starts_at=None, ends_at=None, count: int = 5):
    """Validate an expression and show what it would do, for the create dialog."""
    try:
        expression = cron.validate(cron_expression)
    except cron.CronError as e:
        raise _bad(str(e)) from None

    upcoming = cron.next_runs(
        expression,
        count=count,
        starts_at=_parse_when(starts_at, "starts_at"),
        ends_at=_parse_when(ends_at, "ends_at"),
    )
    return {
        "cron": expression,
        "description": cron.describe(expression),
        "upcoming_runs": [moment.isoformat() for moment in upcoming],
    }


async def run_now(app, workspace_id: str, schedule_id: str) -> dict:
    """Execute a schedule immediately without disturbing its cadence.

    Used as "send me a test". It delivers regardless of the alerting condition —
    the point is to confirm the mail arrives — and does not touch next_run_at.
    """
    from backend.app.services.scheduler import run_schedule

    schedule = await mdb_sched.get_schedule(workspace_id, schedule_id)
    if not schedule:
        return {"found": False}

    outcome = await run_schedule(app, schedule, manual=True)
    return {"found": True, **outcome}


__all__ = [
    "MAX_RECIPIENTS",
    "MAX_SCHEDULES_PER_WORKSPACE",
    "create_schedule",
    "decorate",
    "delete_schedule",
    "get_schedule",
    "list_runs",
    "list_schedules",
    "normalize_recipients",
    "preview",
    "run_now",
    "set_active",
    "update_schedule",
    "validate_payload",
]
