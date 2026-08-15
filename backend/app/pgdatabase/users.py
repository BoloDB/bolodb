"""User CRUD operations."""

import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.app.models.user import UserInDB
from backend.app.pgdatabase.engine import async_session
from backend.app.models.orm_user import User
from backend.app.pgdatabase.serialization import _to_uuid, serialize_doc

logger = logging.getLogger(__name__)


class UserAlreadyExistsError(Exception):
    """Raised when a user with the same email, google_id, or supabase_id already exists."""


def _user_to_dict(user) -> dict:
    """
    Serialize a user record into a dictionary containing its persisted fields.

    Parameters:
        user: The user record to serialize.

    Returns:
        dict: A serialized dictionary containing the user's identity, authentication,
            role, verification, tour completion, and creation-time fields.
    """
    return serialize_doc(
        {
            "id": user.id,
            "email": user.email,
            "hashed_pass": user.hashed_pass,
            "role": user.role,
            "google_id": user.google_id,
            "supabase_id": user.supabase_id,
            "email_verified": user.email_verified,
            "tour_completed": user.tour_completed,
            "token_version": user.token_version,
            "created_at": user.created_at,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "avatar_url": user.avatar_url,
            "metadata": user.metadata_,
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
                email_verified=user_data.email_verified,
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


_ALLOWED_USER_FIELDS = frozenset(
    {
        "google_id",
        "supabase_id",
        "hashed_pass",
        "email_verified",
        "email",
        "tour_completed",
        "first_name",
        "last_name",
        "avatar_url",
        "metadata",
    }
)


async def update_user(user_id: str, **fields):
    unexpected = set(fields) - _ALLOWED_USER_FIELDS
    if unexpected:
        logger.warning("Blocked update of disallowed user fields: %s", unexpected)
        return False

    if "metadata" in fields:
        fields["metadata_"] = fields.pop("metadata")

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


async def set_password_and_revoke_sessions(
    user_id: str, hashed_pass: str
) -> Optional[int]:
    """Change the password and retire every existing session, in one transaction.

    Both or neither. Committed separately — as two awaits, which is the obvious
    way to write it — a failure in between leaves the password changed and the
    old sessions alive. That is the worst of the available outcomes, because the
    user has been told their account is secured and it is not: the very sessions
    they changed the password to end are the ones still running.

    Recovery makes it worse still. By the time this runs, the reset token has
    already been consumed, so a user who hits that failure cannot simply retry
    the link — they have to request a new one. Rolling the password back with
    the bump at least leaves their old password working in the meantime.

    Returns the version the bump landed on, so a caller that wants to keep the
    current session alive can mint a replacement for it. Read back with
    ``RETURNING`` rather than a follow-up ``SELECT``: a second revocation racing
    this one would make the re-read describe a bump that is not this one, and
    the caller would hand out a token for a session it never authorised.
    """
    try:
        uid = _to_uuid(user_id)
    except (ValueError, TypeError):
        return None
    async with async_session() as session:
        try:
            result = await session.execute(
                update(User)
                .where(User.id == uid)
                .values(
                    hashed_pass=hashed_pass,
                    token_version=User.token_version + 1,
                )
                .returning(User.token_version)
            )
            new_version = result.scalar_one_or_none()
            await session.commit()
            return new_version
        except Exception:
            await session.rollback()
            raise


async def bump_token_version(user_id: str) -> bool:
    """Retire every token already issued to this user.

    Deliberately not routed through ``update_user``: this is not a field a
    caller should be able to set to a value of its choosing, only one the server
    may advance. Incrementing in SQL rather than read-modify-write also means
    two concurrent revocations cannot land on the same number and leave one of
    them ineffective.
    """
    try:
        uid = _to_uuid(user_id)
    except (ValueError, TypeError):
        return False
    async with async_session() as session:
        try:
            result = await session.execute(
                update(User)
                .where(User.id == uid)
                .values(token_version=User.token_version + 1)
            )
            await session.commit()
            return result.rowcount > 0
        except Exception:
            await session.rollback()
            raise
