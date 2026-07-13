import base64
import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv
from sqlalchemy import (
    String,
    Integer,
    UniqueConstraint,
    ForeignKey,
    Text,
    DateTime,
    text,
    select,
    delete,
    update,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import pool
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.app.models.user import UserInDB
from backend.app.config import CONFIG_DIR

_utcnow = lambda: datetime.now(timezone.utc)

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Example: postgresql+asyncpg://user:pass@host:5432/dbname"
    )

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            DATABASE_URL,
            poolclass=pool.NullPool,
            connect_args={"statement_cache_size": 0},
        )
    return _engine


def _get_session() -> AsyncSession:
    return async_sessionmaker(
        get_engine(), class_=AsyncSession, expire_on_commit=False
    )()


async_session = _get_session


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_pass: Mapped[str] = mapped_column(String, nullable=False, default="")
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    google_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    database_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class QueryHistory(Base):
    __tablename__ = "query_history"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[str] = mapped_column(String, nullable=False, default="low")
    restatement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class RecentConnection(Base):
    __tablename__ = "recent_connections"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_url: Mapped[str] = mapped_column(Text, nullable=False)
    display_url: Mapped[str] = mapped_column(String, nullable=False)
    dialect: Mapped[str] = mapped_column(String, nullable=False)
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (UniqueConstraint("user_id", "db_id"),)


async def init_db():
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def dispose_db():
    if _engine is not None:
        await _engine.dispose()


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(val)


def serialize_doc(doc):
    if doc is None:
        return None
    out = doc.copy()
    out["_id"] = str(out.pop("id", ""))
    if "user_id" in out and out["user_id"] is not None:
        out["user_id"] = str(out["user_id"])
    if "conversation_id" in out and out["conversation_id"] is not None:
        out["conversation_id"] = str(out["conversation_id"])
    for key in ("created_at", "updated_at", "timestamp", "connected_at"):
        if key in out and isinstance(out[key], datetime):
            out[key] = out[key].isoformat()
    return out


_CONNECTIONS_KEY_FILE = CONFIG_DIR / "connections.key"


def _recent_connections_master_cipher():
    master = os.getenv("RECENT_CONNECTIONS_MASTER_KEY")
    if not master:
        return None
    master_key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
    return Fernet(master_key)


def _recent_connection_cipher():
    secret = os.getenv("RECENT_CONNECTIONS_KEY")
    if secret:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key), None
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    master_cipher = _recent_connections_master_cipher()
    if _CONNECTIONS_KEY_FILE.exists():
        persisted = _CONNECTIONS_KEY_FILE.read_text().strip()
        if master_cipher:
            if persisted.startswith("v1:"):
                try:
                    loaded_secret = master_cipher.decrypt(
                        persisted[3:].encode()
                    ).decode()
                except (InvalidToken, ValueError, TypeError):
                    raise RuntimeError(
                        "Failed to decrypt connections key file with RECENT_CONNECTIONS_MASTER_KEY. "
                        "The master key may have changed or the key file is corrupted."
                    )
            else:
                raise RuntimeError(
                    "RECENT_CONNECTIONS_MASTER_KEY is set but connections key file "
                    "is not encrypted. Re-run with RECENT_CONNECTIONS_MASTER_KEY unset "
                    "to regenerate, or set RECENT_CONNECTIONS_KEY directly."
                )
        else:
            loaded_secret = persisted
        key = base64.urlsafe_b64encode(hashlib.sha256(loaded_secret.encode()).digest())
        return Fernet(key), None
    if master_cipher:
        new_secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        stored_secret = "v1:" + master_cipher.encrypt(new_secret.encode()).decode()
        _CONNECTIONS_KEY_FILE.write_text(stored_secret)
        try:
            os.chmod(_CONNECTIONS_KEY_FILE, 0o600)
        except OSError:
            pass
        key = base64.urlsafe_b64encode(hashlib.sha256(new_secret.encode()).digest())
    else:
        jwt_secret = os.getenv("JWT_SECRET")
        if jwt_secret:
            key = base64.urlsafe_b64encode(hashlib.sha256(jwt_secret.encode()).digest())
        else:
            key = base64.urlsafe_b64encode(os.urandom(32))
    return Fernet(key), None


def _encrypt_connection_url(db_url):
    return _recent_connection_cipher()[0].encrypt(db_url.encode()).decode()


def _decrypt_connection_url(value):
    try:
        return _recent_connection_cipher()[0].decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        jwt_secret = os.getenv("JWT_SECRET")
        if jwt_secret:
            try:
                legacy_key = base64.urlsafe_b64encode(
                    hashlib.sha256(jwt_secret.encode()).digest()
                )
                return Fernet(legacy_key).decrypt(value.encode()).decode()
            except (InvalidToken, ValueError, TypeError):
                pass
        return value


async def get_user_by_email(email: str) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return serialize_doc(
            {
                "id": user.id,
                "email": user.email,
                "hashed_pass": user.hashed_pass,
                "role": user.role,
                "google_id": user.google_id,
                "created_at": user.created_at,
            }
        )


async def get_user_by_google_id(google_id: str) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return serialize_doc(
            {
                "id": user.id,
                "email": user.email,
                "hashed_pass": user.hashed_pass,
                "role": user.role,
                "google_id": user.google_id,
                "created_at": user.created_at,
            }
        )


async def create_user(user_data: UserInDB) -> str:
    async with async_session() as session:
        try:
            user = User(
                email=user_data.email,
                hashed_pass=user_data.hashed_pass,
                role=user_data.role.value,
                google_id=user_data.google_id,
            )
            session.add(user)
            await session.commit()
            return str(user.id)
        except Exception:
            await session.rollback()
            raise


async def get_user_by_id(user_id: str) -> Optional[dict]:
    try:
        uid = _to_uuid(user_id)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        result = await session.execute(select(User).where(User.id == uid))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return serialize_doc(
            {
                "id": user.id,
                "email": user.email,
                "hashed_pass": user.hashed_pass,
                "role": user.role,
                "google_id": user.google_id,
                "created_at": user.created_at,
            }
        )


_ALLOWED_USER_FIELDS = frozenset({"google_id", "hashed_pass"})


async def update_user(user_id: str, **fields):
    unexpected = set(fields) - _ALLOWED_USER_FIELDS
    if unexpected:
        logger = __import__("logging").getLogger(__name__)
        logger.warning("Blocked update of disallowed user fields: %s", unexpected)
        return False
    try:
        uid = _to_uuid(user_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            stmt = update(User).where(User.id == uid).values(**fields)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def save_query(
    user_id, question, sql, result, confidence, conversation_id=None, restatement=""
):
    uid = _to_uuid(user_id)
    conv_id = _to_uuid(conversation_id) if conversation_id else None
    async with async_session() as session:
        try:
            qh = QueryHistory(
                user_id=uid,
                question=question,
                sql=sql,
                result=result,
                confidence=confidence,
                restatement=restatement,
                conversation_id=conv_id,
            )
            session.add(qh)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_query_history(user_id: str, limit: int = 100):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(QueryHistory)
            .where(QueryHistory.user_id == uid)
            .order_by(QueryHistory.timestamp.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        out = []
        for row in rows:
            d = {
                "id": row.id,
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


async def get_query_stats(user_id: str):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        total_q = await session.scalar(
            select(func.count()).where(QueryHistory.user_id == uid)
        )
        total = total_q or 0

        conf_rows = await session.execute(
            text(
                "SELECT LOWER(COALESCE(confidence, 'low')) AS level, COUNT(*) AS count "
                "FROM query_history WHERE user_id = :uid GROUP BY LOWER(COALESCE(confidence, 'low'))"
            ).bindparams(uid=uid)
        )
        confidence_counts = {"High": 0, "Medium": 0, "Low": 0}
        for level, count in conf_rows:
            key = level.capitalize() if level else "Low"
            confidence_counts[key] = count

        day_rows = await session.execute(
            text(
                "SELECT DATE(timestamp) AS date, COUNT(*) AS count "
                "FROM query_history WHERE user_id = :uid "
                "GROUP BY DATE(timestamp) ORDER BY date DESC LIMIT 90"
            ).bindparams(uid=uid)
        )
        daily = [{"date": str(row[0]), "count": row[1]} for row in day_rows]
        daily.reverse()

        sql_rows = await session.execute(
            text(
                "SELECT sql FROM query_history WHERE user_id = :uid "
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


async def delete_history_entry(user_id: str, entry_id: str) -> bool:
    try:
        uid = _to_uuid(user_id)
        eid = _to_uuid(entry_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(QueryHistory).where(
                    QueryHistory.id == eid, QueryHistory.user_id == uid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def clear_history(user_id: str):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        try:
            await session.execute(
                delete(QueryHistory).where(QueryHistory.user_id == uid)
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def save_recent_connection(
    user_id, db_url, display_url, dialect, db_id, table_count
):
    uid = _to_uuid(user_id)
    encrypted_url = _encrypt_connection_url(db_url)
    async with async_session() as session:
        try:
            existing = await session.execute(
                select(RecentConnection).where(
                    RecentConnection.user_id == uid, RecentConnection.db_id == db_id
                )
            )
            conn = existing.scalar_one_or_none()
            if conn:
                conn.db_url = encrypted_url
                conn.display_url = display_url
                conn.dialect = dialect
                conn.table_count = table_count
                conn.connected_at = _utcnow()
            else:
                conn = RecentConnection(
                    user_id=uid,
                    db_url=encrypted_url,
                    display_url=display_url,
                    dialect=dialect,
                    db_id=db_id,
                    table_count=table_count,
                )
                session.add(conn)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_recent_connections(user_id: str, limit: int = 5):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(RecentConnection)
            .where(RecentConnection.user_id == uid)
            .order_by(RecentConnection.connected_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
        out = []
        for row in rows:
            d = {
                "id": row.id,
                "user_id": row.user_id,
                "db_url": row.db_url,
                "display_url": row.display_url,
                "dialect": row.dialect,
                "db_id": row.db_id,
                "table_count": row.table_count,
                "connected_at": row.connected_at,
            }
            out.append(serialize_doc(d))
        return out


async def delete_recent_connection(user_id: str, connection_id: str) -> bool:
    try:
        uid = _to_uuid(user_id)
        cid = _to_uuid(connection_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(RecentConnection).where(
                    RecentConnection.id == cid, RecentConnection.user_id == uid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def get_recent_connection_by_db_id(user_id: str, db_id: str) -> Optional[dict]:
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(RecentConnection).where(
                RecentConnection.user_id == uid, RecentConnection.db_id == db_id
            )
        )
        conn = result.scalar_one_or_none()
        if conn is None:
            return None
        d = {
            "id": conn.id,
            "user_id": conn.user_id,
            "db_url": conn.db_url,
            "display_url": conn.display_url,
            "dialect": conn.dialect,
            "db_id": conn.db_id,
            "table_count": conn.table_count,
            "connected_at": conn.connected_at,
        }
        if "db_url" in d:
            d["db_url"] = _decrypt_connection_url(d["db_url"])
        return serialize_doc(d)


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

        agg_rows = await session.execute(
            text(
                "SELECT qh.conversation_id, COUNT(*) AS turn_count, "
                "MAX(qh.timestamp) AS last_ts "
                "FROM query_history qh "
                "WHERE qh.user_id = :uid AND qh.conversation_id = ANY(:cids) "
                "GROUP BY qh.conversation_id"
            ),
            {"uid": uid, "cids": conv_ids},
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
                "WHERE qh.user_id = :uid AND qh.conversation_id = ANY(:cids) "
                "ORDER BY qh.conversation_id, qh.timestamp DESC"
            ),
            {"uid": uid, "cids": conv_ids},
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
