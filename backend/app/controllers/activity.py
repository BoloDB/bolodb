from sqlalchemy import select, desc
from datetime import datetime, timedelta, timezone
from backend.app.pgdatabase.engine import async_session
from backend.app.models.activity import WorkspaceActivityLog
from backend.app.models.orm_user import User
from backend.app.pgdatabase.serialization import _to_uuid
from backend.app.config import ACTIVITY_LOG_RETENTION_DAYS


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

    cutoff_date = datetime.now(timezone.utc) - timedelta(
        days=ACTIVITY_LOG_RETENTION_DAYS
    )

    async with async_session() as session:
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
