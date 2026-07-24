"""Recent connections CRUD with encryption.

Stored database URLs contain credentials, so they are encrypted at rest with a
key derived from ``RECENT_CONNECTIONS_KEY`` in the environment. That is the only
source — nothing is written to disk, so pointing a deploy at a fresh volume or
rotating the app image can never orphan the key. The env var must stay stable:
change it and previously saved connections can no longer be decrypted and have
to be re-added.
"""

import base64
import hashlib
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.pgdatabase.engine import async_session
from backend.app.models.recent_connection import RecentConnection
from backend.app.models.base import _uuid7
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc


class ConnectionKeyError(RuntimeError):
    """Raised when RECENT_CONNECTIONS_KEY is missing or unusable.

    A dedicated type so callers can tell "the server is misconfigured" (every
    save will fail until an operator fixes the environment) apart from a
    transient database error (worth retrying).
    """


def _build_recent_connection_cipher():
    secret = os.getenv("RECENT_CONNECTIONS_KEY")
    if not secret:
        raise ConnectionKeyError(
            "RECENT_CONNECTIONS_KEY is not set. It is required to encrypt saved "
            "database connections — set a stable secret in the environment."
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
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
    # A missing or unusable key configuration must not short-circuit the legacy
    # and plaintext paths below — rows written before the current key scheme are
    # still readable through them, and that migration path is the whole point of
    # the fallbacks. Hence RuntimeError is caught alongside the Fernet errors.
    try:
        return _recent_connection_cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError, RuntimeError):
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
    workspace_id, db_url, display_url, dialect, db_id, table_count, alias_name=None
):
    wid = _to_uuid(workspace_id)
    encrypted_url = _encrypt_connection_url(db_url)
    async with async_session() as session:
        try:
            stmt = (
                pg_insert(RecentConnection)
                .values(
                    id=_uuid7(),
                    workspace_id=wid,
                    db_url=encrypted_url,
                    display_url=display_url,
                    dialect=dialect,
                    db_id=db_id,
                    table_count=table_count,
                    alias_name=alias_name,
                )
                .on_conflict_do_update(
                    index_elements=["workspace_id", "db_id"],
                    set_=dict(
                        db_url=encrypted_url,
                        display_url=display_url,
                        dialect=dialect,
                        table_count=table_count,
                        alias_name=(
                            alias_name
                            if alias_name is not None
                            else RecentConnection.alias_name
                        ),
                        connected_at=func.now(),
                    ),
                )
            )
            await session.execute(stmt)
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def _serialize_connection(row, include_url: bool = False) -> dict:
    d = {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "display_url": row.display_url,
        "alias_name": row.alias_name,
        "dialect": row.dialect,
        "db_id": row.db_id,
        "table_count": row.table_count,
        "connected_at": row.connected_at,
    }
    if include_url:
        d["db_url"] = _decrypt_connection_url(row.db_url)
    return serialize_doc(d)


async def get_recent_connections(workspace_id: str, limit: int = 50):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(RecentConnection)
            .where(RecentConnection.workspace_id == wid)
            .order_by(RecentConnection.connected_at.desc())
            .limit(limit)
        )
        return [_serialize_connection(row) for row in result.scalars().all()]


async def get_latest_recent_connection(workspace_id: str) -> Optional[dict]:
    """The workspace's most recently used connection, with its URL decrypted.

    Used to restore a workspace's database after a server restart, when nothing
    tells us *which* database to reconnect to.
    """
    try:
        wid = _to_uuid(workspace_id)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        result = await session.execute(
            select(RecentConnection)
            .where(RecentConnection.workspace_id == wid)
            .order_by(RecentConnection.connected_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return _serialize_connection(row, include_url=True) if row else None


async def delete_recent_connection(workspace_id: str, connection_id: str) -> bool:
    try:
        wid = _to_uuid(workspace_id)
        cid = _to_uuid(connection_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                delete(RecentConnection).where(
                    RecentConnection.id == cid, RecentConnection.workspace_id == wid
                )
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise


async def get_recent_connection_by_db_id(
    workspace_id: str, db_id: str
) -> Optional[dict]:
    try:
        wid = _to_uuid(workspace_id)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        result = await session.execute(
            select(RecentConnection).where(
                RecentConnection.workspace_id == wid, RecentConnection.db_id == db_id
            )
        )
        conn = result.scalar_one_or_none()
        return _serialize_connection(conn, include_url=True) if conn else None


async def update_recent_connection_alias(
    workspace_id: str, connection_id: str, alias_name: str | None
) -> bool:
    try:
        wid = _to_uuid(workspace_id)
        cid = _to_uuid(connection_id)
    except (ValueError, TypeError):
        return False
    from sqlalchemy import update

    async with async_session() as session:
        try:
            result = await session.execute(
                update(RecentConnection)
                .where(RecentConnection.id == cid, RecentConnection.workspace_id == wid)
                .values(alias_name=alias_name)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise
