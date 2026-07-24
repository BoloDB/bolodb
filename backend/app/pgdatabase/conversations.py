"""Conversation CRUD operations."""

import uuid
from datetime import datetime

from sqlalchemy import select, delete, update, text

from backend.app.pgdatabase.engine import async_session
from backend.app.models.conversation import Conversation, QueryHistory
from backend.app.models.base import _utcnow
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc

# Max result rows returned per turn when restoring a conversation.
MAX_RESTORED_ROWS = 100
# Max result rows stored per turn when saving a query execution.
MAX_SAVED_ROWS = 500


async def create_conversation(workspace_id, user_id, title="", database_id=None):
    uid = _to_uuid(workspace_id)
    usr = _to_uuid(user_id)
    async with async_session() as session:
        try:
            conv = Conversation(
                workspace_id=uid,
                user_id=usr,
                title=title,
                database_id=database_id,
            )
            session.add(conv)
            await session.commit()
            await session.refresh(conv)
        except Exception:
            await session.rollback()
            raise
        d = {
            "id": conv.id,
            "_id": conv.id,
            "workspace_id": conv.workspace_id,
            "title": conv.title,
            "database_id": conv.database_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
        }
        return serialize_doc(d)


async def conversation_owned_by(
    workspace_id: str, user_id: str, conversation_id: str
) -> bool:
    try:
        uid = _to_uuid(workspace_id)
        usr = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        result = await session.execute(
            select(Conversation.id).where(
                Conversation.id == cid,
                Conversation.workspace_id == uid,
                Conversation.user_id == usr,
            )
        )
        return result.scalar_one_or_none() is not None


async def get_conversations(workspace_id: str, user_id: str):
    uid = _to_uuid(workspace_id)
    usr = _to_uuid(user_id)
    async with async_session() as session:
        conv_result = await session.execute(
            select(Conversation)
            .where(Conversation.workspace_id == uid, Conversation.user_id == usr)
            .order_by(Conversation.updated_at.desc())
        )
        convs = conv_result.scalars().all()
        if not convs:
            return []

        conv_ids = [c.id for c in convs]
        cid_params = [str(c) for c in conv_ids]

        agg_rows = await session.execute(
            text(
                "SELECT qh.conversation_id, COUNT(*) AS turn_count, "
                "MAX(qh.timestamp) AS last_ts "
                "FROM query_history qh "
                "WHERE qh.workspace_id = :uid AND qh.conversation_id = ANY(CAST(:cids AS uuid[])) "
                "GROUP BY qh.conversation_id"
            ),
            {"uid": uid, "cids": cid_params},
        )
        turn_map: dict[uuid.UUID, int] = {}
        ts_map: dict[uuid.UUID, datetime] = {}
        for row in agg_rows:
            turn_map[row[0]] = row[1]
            ts_map[row[0]] = row[2]

        question_rows = await session.execute(
            text(
                "SELECT DISTINCT ON (qh.conversation_id) qh.conversation_id, qh.question "
                "FROM query_history qh "
                "WHERE qh.workspace_id = :uid AND qh.conversation_id = ANY(CAST(:cids AS uuid[])) "
                "ORDER BY qh.conversation_id, qh.timestamp DESC"
            ),
            {"uid": uid, "cids": cid_params},
        )
        question_map: dict[uuid.UUID, str] = {row[0]: row[1] for row in question_rows}

        out = []
        for conv in convs:
            d = {
                "id": conv.id,
                "_id": conv.id,
                "workspace_id": conv.workspace_id,
                "title": conv.title,
                "database_id": conv.database_id,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            }
            d = serialize_doc(d)
            d["turn_count"] = turn_map.get(conv.id, 0)
            d["last_question"] = question_map.get(conv.id, "")
            out.append(d)
        return out


async def get_conversation(workspace_id: str, user_id: str, conversation_id: str):
    try:
        uid = _to_uuid(workspace_id)
        usr = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == cid,
                Conversation.workspace_id == uid,
                Conversation.user_id == usr,
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return None
        d = {
            "id": conv.id,
            "_id": conv.id,
            "workspace_id": conv.workspace_id,
            "title": conv.title,
            "database_id": conv.database_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
        }
        d = serialize_doc(d)

        turns_result = await session.execute(
            select(QueryHistory)
            .where(
                QueryHistory.conversation_id == cid,
                QueryHistory.workspace_id == uid,
            )
            .order_by(QueryHistory.timestamp.asc())
        )
        turns = []
        for turn in turns_result.scalars().all():
            # Cap restored result payloads: a turn can hold up to 500 rows of
            # JSONB, and shipping every row of every turn made opening long
            # conversations slow. The UI table previews 8 rows.
            result = turn.result if isinstance(turn.result, list) else []
            truncated = len(result) > MAX_RESTORED_ROWS
            td = {
                "id": turn.id,
                "_id": turn.id,
                "workspace_id": turn.workspace_id,
                "question": turn.question,
                "sql": turn.sql,
                "result": result[:MAX_RESTORED_ROWS],
                "result_truncated": truncated,
                "confidence": turn.confidence,
                "restatement": turn.restatement,
                "chart": turn.chart,
                "conversation_id": turn.conversation_id,
                "timestamp": turn.timestamp,
            }
            turns.append(serialize_doc(td))
        d["turns"] = turns
        return d


async def rename_conversation(
    workspace_id: str, user_id: str, conversation_id: str, title: str
) -> bool:
    try:
        uid = _to_uuid(workspace_id)
        usr = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                update(Conversation)
                .where(
                    Conversation.id == cid,
                    Conversation.workspace_id == uid,
                    Conversation.user_id == usr,
                )
                .values(title=title, updated_at=_utcnow())
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def touch_conversation(conversation_id: str, user_id: str = None):
    try:
        cid = _to_uuid(conversation_id)
        usr = _to_uuid(user_id) if user_id else None
    except (ValueError, TypeError):
        return
    async with async_session() as session:
        try:
            stmt = update(Conversation).where(Conversation.id == cid)
            if usr is not None:
                stmt = stmt.where(Conversation.user_id == usr)
            await session.execute(stmt.values(updated_at=_utcnow()))
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def delete_conversation(
    workspace_id: str, user_id: str, conversation_id: str
) -> bool:
    try:
        uid = _to_uuid(workspace_id)
        usr = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        async with session.begin():
            owner = await session.execute(
                select(Conversation.id).where(
                    Conversation.id == cid,
                    Conversation.workspace_id == uid,
                    Conversation.user_id == usr,
                )
            )
            if owner.scalar_one_or_none() is None:
                return False
            await session.execute(
                delete(QueryHistory).where(
                    QueryHistory.conversation_id == cid,
                    QueryHistory.workspace_id == uid,
                )
            )
            await session.execute(
                delete(Conversation).where(
                    Conversation.id == cid,
                    Conversation.workspace_id == uid,
                    Conversation.user_id == usr,
                )
            )
        return True


async def clear_conversations(workspace_id: str, user_id: str):
    uid = _to_uuid(workspace_id)
    usr = _to_uuid(user_id)
    async with async_session() as session:
        async with session.begin():
            conv_ids_result = await session.execute(
                select(Conversation.id).where(
                    Conversation.workspace_id == uid, Conversation.user_id == usr
                )
            )
            conv_ids = [row[0] for row in conv_ids_result]
            if conv_ids:
                await session.execute(
                    delete(QueryHistory).where(
                        QueryHistory.conversation_id.in_(conv_ids),
                        QueryHistory.workspace_id == uid,
                    )
                )
            await session.execute(
                delete(Conversation).where(
                    Conversation.workspace_id == uid, Conversation.user_id == usr
                )
            )
