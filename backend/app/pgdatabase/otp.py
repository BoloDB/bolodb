"""OTP code CRUD operations for email verification."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sqlalchemy_delete, select, update as sqlalchemy_update

from backend.app.pgdatabase.engine import get_engine
from backend.app.models.auth_token import OtpCode

logger = logging.getLogger(__name__)

OTP_TTL_MINUTES = 10
OTP_LENGTH = 6
# Wrong guesses a single code will tolerate before it is spent. Five leaves
# room for fat fingers and a stale code in another tab, while cutting the
# reachable share of the 10^6 space to a rounding error.
MAX_OTP_ATTEMPTS = 5


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def generate_otp() -> str:
    """Generate a numeric OTP code (e.g. '048291')."""
    return "".join(secrets.choice("0123456789") for _ in range(OTP_LENGTH))


async def create_otp(user_id: str, purpose: str = "signup") -> str:
    """Create an OTP code for a user and return the plain-text code.

    Any existing OTP for the same (user_id, purpose) is deleted before creating
    a new one, avoiding unique-constraint conflicts.
    """
    code = generate_otp()
    code_hash = _hash_code(code)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_TTL_MINUTES)

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            sqlalchemy_delete(OtpCode).where(
                OtpCode.user_id == user_id,
                OtpCode.purpose == purpose,
            )
        )
        await conn.execute(
            OtpCode.__table__.insert().values(
                user_id=user_id,
                code_hash=code_hash,
                purpose=purpose,
                expires_at=expires_at,
                used=False,
            )
        )

    return code


async def delete_otp_for_user(user_id: str, purpose: str = "signup") -> None:
    """Delete all OTPs for a user/purpose pair."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            sqlalchemy_delete(OtpCode).where(
                OtpCode.user_id == user_id,
                OtpCode.purpose == purpose,
            )
        )


async def verify_otp(user_id: str, code: str, purpose: str = "signup") -> bool:
    """Verify an OTP code. Returns True if valid and marks it as used.

    A wrong guess is counted, and after ``MAX_OTP_ATTEMPTS`` the code stops
    answering even to the right value — it has to be reissued. Without that,
    six digits is a 10^6 space that a script walks well inside the ten-minute
    window, and a hit here returns session cookies.

    The row is selected by ``(user_id, purpose)`` rather than by the code hash so
    that a *wrong* guess still finds the row it needs to count against. Matching
    on the hash, as this did, meant a wrong guess selected nothing and there was
    nowhere to record the attempt.
    """
    code_hash = _hash_code(code)

    engine = get_engine()
    async with engine.begin() as conn:
        result = await conn.execute(
            select(
                OtpCode.id,
                OtpCode.expires_at,
                OtpCode.code_hash,
                OtpCode.attempts,
            )
            .where(
                OtpCode.user_id == user_id,
                OtpCode.purpose == purpose,
                OtpCode.used.is_(False),
            )
            .with_for_update()
        )
        row = result.first()

        if not row:
            return False

        otp_id, expires_at, stored_hash, attempts = row

        if datetime.now(timezone.utc) > expires_at:
            return False

        if attempts >= MAX_OTP_ATTEMPTS:
            logger.warning("OTP for purpose=%s exhausted its attempts", purpose)
            return False

        # compare_digest, not ==: both sides are SHA-256 hex of the same length,
        # so the timing signal is slight, but constant-time is free here.
        if not secrets.compare_digest(stored_hash, code_hash):
            await conn.execute(
                sqlalchemy_update(OtpCode)
                .where(OtpCode.id == otp_id)
                .values(attempts=OtpCode.attempts + 1)
            )
            return False

        await conn.execute(
            sqlalchemy_update(OtpCode)
            .where(
                OtpCode.id == otp_id,
                OtpCode.used.is_(False),
            )
            .values(used=True)
        )

    return True
