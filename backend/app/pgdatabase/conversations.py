"""Conversation CRUD operations."""

import uuid
from datetime import datetime

from sqlalchemy import select, delete, update, text

from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.models import Conversation, QueryHistory, _utcnow
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc


async def create_conversation(user_id, title="", database_id=None):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        try:
            conv = Conversation(
                user_id=uid,
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
            "user_id": conv.user_id,
            "title": conv.title,
            "database_id": conv.database_id,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
        }
        return serialize_doc(d)


async def conversation_owned_by(user_id: str, conversation_id: str) -> bool:
    try:
        uid = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        result = await session.execute(
            select(Conversation.id).where(
                Conversation.id == cid, Conversation.user_id == uid
            )
        )
        return result.scalar_one_or_none() is not None


async def get_conversations(user_id: str):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        conv_result = await session.execute(
            select(Conversation)
            .where(Conversation.user_id == uid)
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
                "WHERE qh.user_id = :uid AND qh.conversation_id = ANY(CAST(:cids AS uuid[])) "
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
                "WHERE qh.user_id = :uid AND qh.conversation_id = ANY(CAST(:cids AS uuid[])) "
                "ORDER BY qh.conversation_id, qh.timestamp DESC"
            ),
            {"uid": uid, "cids": cid_params},
        )
        question_map: dict[uuid.UUID, str] = {row[0]: row[1] for row in question_rows}

        out = []
        for conv in convs:
            d = {
                "id": conv.id,
                "user_id": conv.user_id,
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


async def get_conversation(user_id: str, conversation_id: str):
    try:
        uid = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == cid, Conversation.user_id == uid
            )
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return None
        d = {
            "id": conv.id,
            "user_id": conv.user_id,
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
                QueryHistory.user_id == uid,
            )
            .order_by(QueryHistory.timestamp.asc())
        )
        turns = []
        for turn in turns_result.scalars().all():
            td = {
                "id": turn.id,
                "user_id": turn.user_id,
                "question": turn.question,
                "sql": turn.sql,
                "result": turn.result,
                "confidence": turn.confidence,
                "restatement": turn.restatement,
                "conversation_id": turn.conversation_id,
                "timestamp": turn.timestamp,
            }
            turns.append(serialize_doc(td))
        d["turns"] = turns
        return d


async def rename_conversation(user_id: str, conversation_id: str, title: str) -> bool:
    try:
        uid = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                update(Conversation)
                .where(Conversation.id == cid, Conversation.user_id == uid)
                .values(title=title, updated_at=_utcnow())
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def touch_conversation(conversation_id: str):
    try:
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return
    async with async_session() as session:
        try:
            await session.execute(
                update(Conversation)
                .where(Conversation.id == cid)
                .values(updated_at=_utcnow())
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def delete_conversation(user_id: str, conversation_id: str) -> bool:
    try:
        uid = _to_uuid(user_id)
        cid = _to_uuid(conversation_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        async with session.begin():
            owner = await session.execute(
                select(Conversation.id).where(
                    Conversation.id == cid, Conversation.user_id == uid
                )
            )
            if owner.scalar_one_or_none() is None:
                return False
            await session.execute(
                delete(QueryHistory).where(
                    QueryHistory.conversation_id == cid,
                    QueryHistory.user_id == uid,
                )
            )
            await session.execute(
                delete(Conversation).where(
                    Conversation.id == cid, Conversation.user_id == uid
                )
            )
        return True


async def clear_conversations(user_id: str):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        async with session.begin():
            conv_ids_result = await session.execute(
                select(Conversation.id).where(Conversation.user_id == uid)
            )
            conv_ids = [row[0] for row in conv_ids_result]
            if conv_ids:
                await session.execute(
                    delete(QueryHistory).where(
                        QueryHistory.conversation_id.in_(conv_ids),
                        QueryHistory.user_id == uid,
                    )
                )
            await session.execute(
                delete(Conversation).where(Conversation.user_id == uid)
            )
