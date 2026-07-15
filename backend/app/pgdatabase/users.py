"""User CRUD operations."""

import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import UserInDB
from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.models import User
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc

logger = logging.getLogger(__name__)


class UserAlreadyExistsError(Exception):
    """Raised when a user with the same email, google_id, or supabase_id already exists."""


def _user_to_dict(user) -> dict:
    return serialize_doc(
        {
            "id": user.id,
            "email": user.email,
            "hashed_pass": user.hashed_pass,
            "role": user.role,
            "google_id": user.google_id,
            "supabase_id": user.supabase_id,
            "created_at": user.created_at,
        }
    )


async def get_user_by_email(email: str) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return _user_to_dict(user)


async def get_user_by_google_id(google_id: str) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.google_id == google_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return _user_to_dict(user)


async def get_user_by_supabase_id(supabase_id: str) -> Optional[dict]:
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.supabase_id == supabase_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return _user_to_dict(user)


async def create_user(user_data: UserInDB) -> str:
    async with async_session() as session:
        try:
            user = User(
                email=user_data.email,
                hashed_pass=user_data.hashed_pass,
                role=user_data.role.value,
                google_id=user_data.google_id,
                supabase_id=user_data.supabase_id,
            )
            session.add(user)
            await session.commit()
            return str(user.id)
        except IntegrityError as exc:
            await session.rollback()
            raise UserAlreadyExistsError(str(exc)) from exc
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
        return _user_to_dict(user)


_ALLOWED_USER_FIELDS = frozenset({"google_id", "supabase_id", "hashed_pass"})


async def update_user(user_id: str, **fields):
    unexpected = set(fields) - _ALLOWED_USER_FIELDS
    if unexpected:
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
