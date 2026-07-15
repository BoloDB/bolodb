"""Recent connections CRUD with encryption."""

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.models import RecentConnection
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc
from backend.app.pgdatabase.models import _uuid7
from backend.app.config import CONFIG_DIR


_CONNECTIONS_KEY_FILE = CONFIG_DIR / "connections.key"


def _recent_connections_master_cipher():
    master = os.getenv("RECENT_CONNECTIONS_MASTER_KEY")
    if not master:
        return None
    master_key = base64.urlsafe_b64encode(hashlib.sha256(master.encode()).digest())
    return Fernet(master_key)


def _build_recent_connection_cipher():
    secret = os.getenv("RECENT_CONNECTIONS_KEY")
    if secret:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key)
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
        return Fernet(key)
    if master_cipher:
        new_secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        _CONNECTIONS_KEY_FILE.write_text(
            "v1:" + master_cipher.encrypt(new_secret.encode()).decode()
        )
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
    return Fernet(key)


_RECENT_CIPHER = None


def _recent_connection_cipher():
    global _RECENT_CIPHER
    if _RECENT_CIPHER is None:
        _RECENT_CIPHER = _build_recent_connection_cipher()
    return _RECENT_CIPHER


def _encrypt_connection_url(db_url):
    return _recent_connection_cipher().encrypt(db_url.encode()).decode()


def _decrypt_connection_url(value):
    try:
        return _recent_connection_cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        pass
    jwt_secret = os.getenv("JWT_SECRET")
    if jwt_secret:
        try:
            legacy_key = base64.urlsafe_b64encode(
                hashlib.sha256(jwt_secret.encode()).digest()
            )
            return Fernet(legacy_key).decrypt(value.encode()).decode()
        except (InvalidToken, ValueError, TypeError):
            pass
    if "://" in value:
        return value
    raise RuntimeError(
        "Failed to decrypt stored connection URL. The encryption key may have "
        "changed or the stored value is corrupted."
    )


async def save_recent_connection(
    user_id, db_url, display_url, dialect, db_id, table_count
):
    uid = _to_uuid(user_id)
    encrypted_url = _encrypt_connection_url(db_url)
    async with async_session() as session:
        try:
            stmt = (
                pg_insert(RecentConnection)
                .values(
                    id=_uuid7(),
                    user_id=uid,
                    db_url=encrypted_url,
                    display_url=display_url,
                    dialect=dialect,
                    db_id=db_id,
                    table_count=table_count,
                )
                .on_conflict_do_update(
                    index_elements=["user_id", "db_id"],
                    set_=dict(
                        db_url=encrypted_url,
                        display_url=display_url,
                        dialect=dialect,
                        table_count=table_count,
                    ),
                )
            )
            await session.execute(stmt)
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
