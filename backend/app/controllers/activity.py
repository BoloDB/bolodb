import asyncio
import logging
from sqlalchemy import select, desc, delete, func
from datetime import datetime, timedelta, timezone
from backend.app.pgdatabase.engine import async_session
from backend.app.models.workspace_settings import WorkspaceSettings
from backend.app.models.activity import WorkspaceActivityLog
from backend.app.models.orm_user import User
from backend.app.pgdatabase.serialization import _to_uuid
from backend.app.config import (
    ACTIVITY_CLEANUP_INTERVAL_HOURS,
    ACTIVITY_LOG_RETENTION_DAYS,
)

log = logging.getLogger(__name__)


async def log_activity(
    workspace_id: str,
    actor_id: str | None,
    event_type: str,
    resource_type: str,
    resource_id: str = None,
    metadata: dict = None,
):
    try:
        wid = _to_uuid(workspace_id)
        aid = _to_uuid(actor_id) if actor_id else None
    except ValueError:
        return

    async with async_session() as session:
        log = WorkspaceActivityLog(
            workspace_id=wid,
            actor_id=aid,
            event_type=event_type,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata or {},
        )
        session.add(log)
        await session.commit()


async def get_workspace_activity(
    workspace_id: str, limit: int = 50, offset: int = 0, event_type: str = None
):
    try:
        wid = _to_uuid(workspace_id)
    except ValueError:
        return []

    async with async_session() as session:
        settings_res = await session.execute(
            select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == wid)
        )
        settings = settings_res.scalar_one_or_none()
        retention_days = getattr(
            settings, "activity_retention_days", ACTIVITY_LOG_RETENTION_DAYS
        )

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)

        stmt = (
            select(WorkspaceActivityLog, User.email)
            .outerjoin(User, WorkspaceActivityLog.actor_id == User.id)
            .where(WorkspaceActivityLog.workspace_id == wid)
            .where(WorkspaceActivityLog.created_at >= cutoff_date)
        )

        if event_type:
            stmt = stmt.where(WorkspaceActivityLog.event_type == event_type)

        stmt = (
            stmt.order_by(desc(WorkspaceActivityLog.created_at))
            .limit(limit)
            .offset(offset)
        )
        result = await session.execute(stmt)
        rows = result.all()

        return [
            {
                "id": str(log.id),
                "workspace_id": str(log.workspace_id),
                "actor_id": str(log.actor_id) if log.actor_id else None,
                "actor_email": email,
                "event_type": log.event_type,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "metadata_": log.metadata_,
                "created_at": log.created_at,
            }
            for log, email in rows
        ]


# The UI route caps a page at 100 rows; an export should cover the whole
# retention window, so it pages through instead of taking a single big limit.
EXPORT_PAGE_SIZE = 500
EXPORT_MAX_ROWS = 50_000


async def iter_workspace_activity(workspace_id: str, event_type: str = None):
    """Yield every retained activity row for a workspace, newest first."""
    offset = 0
    while offset < EXPORT_MAX_ROWS:
        batch = await get_workspace_activity(
            workspace_id,
            limit=EXPORT_PAGE_SIZE,
            offset=offset,
            event_type=event_type,
        )
        if not batch:
            return
        for row in batch:
            yield row
        if len(batch) < EXPORT_PAGE_SIZE:
            return
        offset += EXPORT_PAGE_SIZE


async def delete_old_activity(retention_days: int | None = None) -> int:
    """Prune activity rows past the retention window.

    Reads beyond the window are already filtered out by
    ``get_workspace_activity``; this reclaims the storage behind them.

    When ``retention_days`` is given it overrides every workspace's window.
    Otherwise each workspace is pruned by its own ``activity_retention_days``
    setting, falling back to ``ACTIVITY_LOG_RETENTION_DAYS`` for workspaces
    without a settings row. Returns the number of rows removed.
    """
    async with async_session() as session:
        if retention_days is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            stmt = delete(WorkspaceActivityLog).where(
                WorkspaceActivityLog.created_at < cutoff
            )
        else:
            retention = func.coalesce(
                select(WorkspaceSettings.activity_retention_days)
                .where(
                    WorkspaceSettings.workspace_id == WorkspaceActivityLog.workspace_id
                )
                .scalar_subquery(),
                ACTIVITY_LOG_RETENTION_DAYS,
            )
            stmt = delete(WorkspaceActivityLog).where(
                WorkspaceActivityLog.created_at
                < func.now() - func.make_interval(0, 0, 0, retention)
            )

        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount or 0


async def cleanup_old_activity_logs(db=None, retention_days: int | None = None) -> int:
    """Alias function delegating to ``delete_old_activity`` or returning deleted count."""
    if isinstance(db, int) and retention_days is None:
        retention_days = db
    return await delete_old_activity(retention_days=retention_days)


async def activity_cleanup_loop(interval_hours: float | None = None):
    """Run ``delete_old_activity`` forever on a fixed interval.

    Started from the app lifespan. Every failure is swallowed and retried on the
    next tick — a pruning job must never be able to take the server down.
    """
    interval = (
        interval_hours
        if interval_hours is not None
        else ACTIVITY_CLEANUP_INTERVAL_HOURS
    ) * 3600
    while True:
        try:
            removed = await delete_old_activity()
            if removed:
                log.info("activity cleanup removed %d expired rows", removed)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("activity cleanup failed; retrying next interval")
        await asyncio.sleep(interval)
