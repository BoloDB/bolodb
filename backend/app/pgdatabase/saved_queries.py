from sqlalchemy import select, delete, update
from backend.app.pgdatabase.engine import async_session
from backend.app.models.saved_query import SavedQuery
from backend.app.models.base import _utcnow
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc


async def create_saved_query(workspace_id: str, created_by: str, **kwargs):
    uid = _to_uuid(workspace_id)
    c_uid = _to_uuid(created_by) if created_by else None

    async with async_session() as session:
        try:
            sq = SavedQuery(workspace_id=uid, created_by=c_uid, **kwargs)
            session.add(sq)
            await session.commit()
            await session.refresh(sq)
            return serialize_doc(sq.__dict__)
        except Exception:
            await session.rollback()
            raise


async def list_saved_queries(workspace_id: str, limit: int = 50, offset: int = 0):
    uid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(SavedQuery)
            .where(SavedQuery.workspace_id == uid)
            .order_by(SavedQuery.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [serialize_doc(r.__dict__) for r in result.scalars().all()]


async def get_saved_query(workspace_id: str, query_id: str):
    uid = _to_uuid(workspace_id)
    qid = _to_uuid(query_id)
    async with async_session() as session:
        result = await session.execute(
            select(SavedQuery).where(
                SavedQuery.id == qid, SavedQuery.workspace_id == uid
            )
        )
        sq = result.scalar_one_or_none()
        if sq:
            return serialize_doc(sq.__dict__)
        return None


async def update_saved_query(workspace_id: str, query_id: str, **kwargs):
    uid = _to_uuid(workspace_id)
    qid = _to_uuid(query_id)
    async with async_session() as session:
        try:
            kwargs["updated_at"] = _utcnow()
            result = await session.execute(
                update(SavedQuery)
                .where(SavedQuery.id == qid, SavedQuery.workspace_id == uid)
                .values(**kwargs)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def delete_saved_query(workspace_id: str, query_id: str):
    uid = _to_uuid(workspace_id)
    qid = _to_uuid(query_id)
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(SavedQuery).where(
                    SavedQuery.id == qid, SavedQuery.workspace_id == uid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise
