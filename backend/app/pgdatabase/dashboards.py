from sqlalchemy import select, delete, update
from sqlalchemy.orm import selectinload
from backend.app.pgdatabase.engine import async_session
from backend.app.models.dashboard import Dashboard, DashboardPanel
from backend.app.models.saved_query import SavedQuery
from backend.app.models.base import _utcnow
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc


async def create_dashboard(
    workspace_id: str, created_by: str, name: str, description: str = None
):
    uid = _to_uuid(workspace_id)
    c_uid = _to_uuid(created_by) if created_by else None

    async with async_session() as session:
        try:
            d = Dashboard(
                workspace_id=uid, created_by=c_uid, name=name, description=description
            )
            session.add(d)
            await session.commit()
            await session.refresh(d)
            return serialize_doc(d.__dict__)
        except Exception:
            await session.rollback()
            raise


async def list_dashboards(workspace_id: str):
    uid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(Dashboard)
            .where(Dashboard.workspace_id == uid)
            .order_by(Dashboard.updated_at.desc())
        )
        return [serialize_doc(r.__dict__) for r in result.scalars().all()]


async def get_dashboard(workspace_id: str, dashboard_id: str):
    uid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    async with async_session() as session:
        result = await session.execute(
            select(Dashboard)
            .options(selectinload(Dashboard.panels))
            .where(Dashboard.id == did, Dashboard.workspace_id == uid)
        )
        d = result.scalar_one_or_none()
        if not d:
            return None

        doc = serialize_doc(d.__dict__)
        doc["panels"] = [serialize_doc(p.__dict__) for p in d.panels]
        return doc


async def update_dashboard(workspace_id: str, dashboard_id: str, **kwargs):
    uid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    async with async_session() as session:
        try:
            kwargs["updated_at"] = _utcnow()
            result = await session.execute(
                update(Dashboard)
                .where(Dashboard.id == did, Dashboard.workspace_id == uid)
                .values(**kwargs)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def delete_dashboard(workspace_id: str, dashboard_id: str):
    uid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(Dashboard).where(
                    Dashboard.id == did, Dashboard.workspace_id == uid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def add_panel(workspace_id: str, dashboard_id: str, **kwargs):
    wid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    if "saved_query_id" in kwargs and kwargs["saved_query_id"]:
        kwargs["saved_query_id"] = _to_uuid(kwargs["saved_query_id"])

    async with async_session() as session:
        try:
            d = await session.execute(
                select(Dashboard).where(
                    Dashboard.id == did, Dashboard.workspace_id == wid
                )
            )
            if not d.scalar_one_or_none():
                raise ValueError("Dashboard not found in workspace")

            if kwargs.get("saved_query_id"):
                sq = await session.execute(
                    select(SavedQuery.id).where(
                        SavedQuery.id == kwargs["saved_query_id"],
                        SavedQuery.workspace_id == wid,
                    )
                )
                if not sq.scalar_one_or_none():
                    raise ValueError("Saved query not found in workspace")

            panel = DashboardPanel(dashboard_id=did, **kwargs)
            session.add(panel)
            await session.commit()
            await session.refresh(panel)
            return serialize_doc(panel.__dict__)
        except Exception:
            await session.rollback()
            raise


async def update_panel(workspace_id: str, dashboard_id: str, panel_id: str, **kwargs):
    wid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    pid = _to_uuid(panel_id)

    if "saved_query_id" in kwargs and kwargs["saved_query_id"]:
        kwargs["saved_query_id"] = _to_uuid(kwargs["saved_query_id"])

    async with async_session() as session:
        try:
            d = await session.execute(
                select(Dashboard).where(
                    Dashboard.id == did, Dashboard.workspace_id == wid
                )
            )
            if not d.scalar_one_or_none():
                raise ValueError("Dashboard not found in workspace")

            if kwargs.get("saved_query_id"):
                sq = await session.execute(
                    select(SavedQuery.id).where(
                        SavedQuery.id == kwargs["saved_query_id"],
                        SavedQuery.workspace_id == wid,
                    )
                )
                if not sq.scalar_one_or_none():
                    raise ValueError("Saved query not found in workspace")

            kwargs["updated_at"] = _utcnow()
            result = await session.execute(
                update(DashboardPanel)
                .where(DashboardPanel.id == pid, DashboardPanel.dashboard_id == did)
                .values(**kwargs)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def delete_panel(workspace_id: str, dashboard_id: str, panel_id: str):
    wid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    pid = _to_uuid(panel_id)
    async with async_session() as session:
        try:
            d = await session.execute(
                select(Dashboard).where(
                    Dashboard.id == did, Dashboard.workspace_id == wid
                )
            )
            if not d.scalar_one_or_none():
                return False

            result = await session.execute(
                delete(DashboardPanel).where(
                    DashboardPanel.id == pid, DashboardPanel.dashboard_id == did
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def update_panels_batch(workspace_id: str, dashboard_id: str, updates: list):
    wid = _to_uuid(workspace_id)
    did = _to_uuid(dashboard_id)
    async with async_session() as session:
        try:
            d = await session.execute(
                select(Dashboard).where(
                    Dashboard.id == did, Dashboard.workspace_id == wid
                )
            )
            if not d.scalar_one_or_none():
                return False

            for u in updates:
                pid = _to_uuid(u["id"])
                await session.execute(
                    update(DashboardPanel)
                    .where(DashboardPanel.id == pid, DashboardPanel.dashboard_id == did)
                    .values(position=u["position"], updated_at=_utcnow())
                )
            await session.commit()
            return True
        except Exception:
            await session.rollback()
            raise
