"""Persistence for scheduled queries and their execution history."""

from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from backend.app.models.base import _utcnow
from backend.app.models.scheduled_query import ScheduledQuery, ScheduleRun
from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc

# Per-workspace ceiling. Each schedule is a recurring query against a customer
# database and a recurring send against the mail provider, so this is a real
# resource bound rather than a formality.
MAX_SCHEDULES_PER_WORKSPACE = 100

# Execution history kept per schedule. Enough to see a pattern of failures
# without the table growing without limit.
RUN_HISTORY_LIMIT = 100


class ScheduleLimitError(RuntimeError):
    """Raised when a workspace is already at MAX_SCHEDULES_PER_WORKSPACE."""


async def count_schedules(workspace_id: str) -> int:
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(func.count())
            .select_from(ScheduledQuery)
            .where(ScheduledQuery.workspace_id == wid)
        )
        return int(result.scalar_one())


async def create_schedule(workspace_id: str, created_by: str | None, **kwargs):
    wid = _to_uuid(workspace_id)
    c_uid = _to_uuid(created_by) if created_by else None

    async with async_session() as session:
        try:
            # Counted in the same session as the insert so a workspace can't slip
            # past the cap by firing several creates at once.
            existing = await session.execute(
                select(func.count())
                .select_from(ScheduledQuery)
                .where(ScheduledQuery.workspace_id == wid)
            )
            if int(existing.scalar_one()) >= MAX_SCHEDULES_PER_WORKSPACE:
                raise ScheduleLimitError(
                    f"This workspace already has the maximum of "
                    f"{MAX_SCHEDULES_PER_WORKSPACE} scheduled queries. "
                    "Delete one before creating another."
                )

            schedule = ScheduledQuery(workspace_id=wid, created_by=c_uid, **kwargs)
            session.add(schedule)
            await session.commit()
            await session.refresh(schedule)
            return serialize_doc(schedule.__dict__)
        except Exception:
            await session.rollback()
            raise


async def list_schedules(workspace_id: str, limit: int = 100, offset: int = 0):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledQuery)
            .where(ScheduledQuery.workspace_id == wid)
            .order_by(ScheduledQuery.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [serialize_doc(r.__dict__) for r in result.scalars().all()]


async def get_schedule(workspace_id: str, schedule_id: str):
    wid = _to_uuid(workspace_id)
    sid = _to_uuid(schedule_id)
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledQuery).where(
                ScheduledQuery.id == sid, ScheduledQuery.workspace_id == wid
            )
        )
        schedule = result.scalar_one_or_none()
        return serialize_doc(schedule.__dict__) if schedule else None


async def update_schedule(workspace_id: str, schedule_id: str, **kwargs) -> bool:
    wid = _to_uuid(workspace_id)
    sid = _to_uuid(schedule_id)
    async with async_session() as session:
        try:
            kwargs["updated_at"] = _utcnow()
            result = await session.execute(
                update(ScheduledQuery)
                .where(ScheduledQuery.id == sid, ScheduledQuery.workspace_id == wid)
                .values(**kwargs)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def delete_schedule(workspace_id: str, schedule_id: str) -> bool:
    wid = _to_uuid(workspace_id)
    sid = _to_uuid(schedule_id)
    async with async_session() as session:
        try:
            # schedule_runs cascades on the FK, so the history goes with it.
            result = await session.execute(
                delete(ScheduledQuery).where(
                    ScheduledQuery.id == sid, ScheduledQuery.workspace_id == wid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


# ── Scheduler-facing operations (no workspace filter: the loop is global) ──


async def list_due_schedules(now: datetime | None = None, limit: int = 50):
    """Active schedules whose next_run_at has passed, oldest due first.

    Returns raw dicts rather than claiming anything — the caller claims each one
    individually via ``claim_schedule`` so a slow run can't hold a lock.
    """
    moment = now or datetime.now(timezone.utc)
    async with async_session() as session:
        result = await session.execute(
            select(ScheduledQuery)
            .where(
                ScheduledQuery.is_active.is_(True),
                ScheduledQuery.next_run_at.isnot(None),
                ScheduledQuery.next_run_at <= moment,
            )
            .order_by(ScheduledQuery.next_run_at)
            .limit(limit)
        )
        return [serialize_doc(r.__dict__) for r in result.scalars().all()]


async def claim_schedule(
    schedule_id: str,
    expected_next_run_at: datetime | None,
    new_next_run_at: datetime | None,
    now: datetime | None = None,
) -> bool:
    """Advance a due schedule to its next slot, returning whether we won it.

    A compare-and-swap on ``next_run_at``: only the caller that still sees the
    due timestamp gets to run it. The advance happens *before* the query runs,
    not after, so a crash mid-run skips that occurrence rather than replaying it
    on the next boot — a missed report is recoverable, a duplicate report
    already in someone's inbox is not.
    """
    sid = _to_uuid(schedule_id)
    moment = now or datetime.now(timezone.utc)
    async with async_session() as session:
        try:
            result = await session.execute(
                update(ScheduledQuery)
                .where(
                    ScheduledQuery.id == sid,
                    ScheduledQuery.is_active.is_(True),
                    ScheduledQuery.next_run_at == expected_next_run_at,
                )
                .values(next_run_at=new_next_run_at, last_run_at=moment)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def finish_schedule_run(
    schedule_id: str,
    status: str,
    consecutive_failures: int,
    is_active: bool | None = None,
) -> bool:
    """Write back the outcome flags after a run completes."""
    sid = _to_uuid(schedule_id)
    values = {
        "last_status": status,
        "consecutive_failures": consecutive_failures,
        "updated_at": _utcnow(),
    }
    if is_active is not None:
        values["is_active"] = is_active
        if not is_active:
            values["next_run_at"] = None

    async with async_session() as session:
        try:
            result = await session.execute(
                update(ScheduledQuery).where(ScheduledQuery.id == sid).values(**values)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


# ── Execution history ──────────────────────────────────────────────


async def record_run(
    schedule_id: str,
    workspace_id: str,
    status: str,
    started_at: datetime,
    finished_at: datetime | None = None,
    row_count: int | None = None,
    duration_ms: int | None = None,
    detail: str | None = None,
    delivered_to: list | None = None,
    manual: bool = False,
):
    """Append a completed run and trim the schedule's history to the cap."""
    sid = _to_uuid(schedule_id)
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        try:
            run = ScheduleRun(
                schedule_id=sid,
                workspace_id=wid,
                status=status,
                started_at=started_at,
                finished_at=finished_at or _utcnow(),
                row_count=row_count,
                duration_ms=duration_ms,
                detail=detail,
                delivered_to=delivered_to,
                manual=manual,
            )
            session.add(run)
            await session.flush()

            # Trim in the same transaction so history can't drift above the cap
            # even under concurrent runs of the same schedule.
            keep = (
                select(ScheduleRun.id)
                .where(ScheduleRun.schedule_id == sid)
                .order_by(ScheduleRun.started_at.desc())
                .limit(RUN_HISTORY_LIMIT)
                .scalar_subquery()
            )
            await session.execute(
                delete(ScheduleRun).where(
                    ScheduleRun.schedule_id == sid, ScheduleRun.id.notin_(keep)
                )
            )
            await session.commit()
            await session.refresh(run)
            return serialize_doc(run.__dict__)
        except Exception:
            await session.rollback()
            raise


async def list_runs(workspace_id: str, schedule_id: str, limit: int = 25):
    wid = _to_uuid(workspace_id)
    sid = _to_uuid(schedule_id)
    async with async_session() as session:
        result = await session.execute(
            select(ScheduleRun)
            .where(
                ScheduleRun.schedule_id == sid,
                ScheduleRun.workspace_id == wid,
            )
            .order_by(ScheduleRun.started_at.desc())
            .limit(limit)
        )
        return [serialize_doc(r.__dict__) for r in result.scalars().all()]
