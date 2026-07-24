"""Query history CRUD operations."""

from sqlalchemy import select, delete, func, text

from backend.app.pgdatabase.engine import async_session
from backend.app.models.conversation import QueryHistory
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc


async def save_query(
    workspace_id,
    question,
    sql,
    result,
    confidence,
    conversation_id=None,
    restatement="",
    user_id=None,
    chart=None,
):
    wid = _to_uuid(workspace_id)
    uid = _to_uuid(user_id) if user_id else None
    conv_id = _to_uuid(conversation_id) if conversation_id else None
    async with async_session() as session:
        try:
            qh = QueryHistory(
                workspace_id=wid,
                user_id=uid,
                question=question,
                sql=sql,
                result=result,
                confidence=confidence,
                restatement=restatement,
                chart=chart,
                conversation_id=conv_id,
            )
            session.add(qh)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_query_history(workspace_id: str, limit: int = 100):
    uid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(QueryHistory)
            .where(QueryHistory.workspace_id == uid)
            .order_by(QueryHistory.timestamp.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        out = []
        for row in rows:
            d = {
                "id": row.id,
                "workspace_id": row.workspace_id,
                "user_id": row.user_id,
                "question": row.question,
                "sql": row.sql,
                "result": row.result,
                "confidence": row.confidence,
                "restatement": row.restatement,
                "conversation_id": row.conversation_id,
                "timestamp": row.timestamp,
            }
            out.append(serialize_doc(d))
        return out


async def get_query_stats(workspace_id: str):
    uid = _to_uuid(workspace_id)
    async with async_session() as session:
        total_q = await session.scalar(
            select(func.count()).where(QueryHistory.workspace_id == uid)
        )
        total = total_q or 0

        conf_rows = await session.execute(
            text(
                "SELECT LOWER(COALESCE(confidence, 'low')) AS level, COUNT(*) AS count "
                "FROM query_history WHERE workspace_id = :uid GROUP BY LOWER(COALESCE(confidence, 'low'))"
            ).bindparams(uid=uid)
        )
        confidence_counts = {"High": 0, "Medium": 0, "Low": 0}
        for level, count in conf_rows:
            key = level.capitalize() if level else "Low"
            confidence_counts[key] = count

        day_rows = await session.execute(
            text(
                "SELECT DATE(timestamp) AS date, COUNT(*) AS count "
                "FROM query_history WHERE workspace_id = :uid "
                "GROUP BY DATE(timestamp) ORDER BY date DESC LIMIT 90"
            ).bindparams(uid=uid)
        )
        daily = [{"date": str(row[0]), "count": row[1]} for row in day_rows]
        daily.reverse()

        sql_rows = await session.execute(
            text(
                "SELECT sql FROM query_history WHERE workspace_id = :uid "
                "ORDER BY timestamp DESC LIMIT 200"
            ).bindparams(uid=uid)
        )
        table_usage: dict[str, int] = {}
        for (sql_text,) in sql_rows:
            sql_lower = (sql_text or "").lower()
            for keyword in ("from ", "join "):
                idx = 0
                while True:
                    pos = sql_lower.find(keyword, idx)
                    if pos == -1:
                        break
                    start = pos + len(keyword)
                    end = start
                    while end < len(sql_lower) and sql_lower[end] not in (
                        " ",
                        "\n",
                        "\t",
                        ";",
                        "(",
                        ",",
                    ):
                        end += 1
                    tbl = sql_lower[start:end].strip().strip('"').strip("'").strip("`")
                    if (
                        tbl
                        and not tbl.startswith("(")
                        and tbl
                        not in (
                            "select",
                            "where",
                            "on",
                            "and",
                            "or",
                            "set",
                            "into",
                            "values",
                        )
                    ):
                        table_usage[tbl] = table_usage.get(tbl, 0) + 1
                    idx = end
        top_tables = sorted(table_usage.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "total_queries": total,
            "confidence": confidence_counts,
            "daily_activity": daily,
            "top_tables": [{"table": t, "count": c} for t, c in top_tables],
        }


async def delete_history_entry(workspace_id: str, entry_id: str) -> bool:
    try:
        uid = _to_uuid(workspace_id)
        eid = _to_uuid(entry_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(QueryHistory).where(
                    QueryHistory.id == eid, QueryHistory.workspace_id == uid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def clear_history(workspace_id: str):
    uid = _to_uuid(workspace_id)
    async with async_session() as session:
        try:
            await session.execute(
                delete(QueryHistory).where(QueryHistory.workspace_id == uid)
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise
