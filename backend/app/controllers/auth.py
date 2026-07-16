import logging
import hashlib
import secrets

import bcrypt
from pydantic import EmailStr
from fastapi import HTTPException
from backend.app.models.user import (
    UserSignup,
    UserInDB,
    Role,
    validate_password_strength,
)
from backend.app.pgdatabase import (
    create_user,
    get_user_by_email,
    get_user_by_supabase_id,
    get_user_by_id,
    update_user,
    UserAlreadyExistsError,
)
from backend.app.pgdatabase.models import PasswordResetToken
from backend.app.pgdatabase.engine import get_engine
import jwt
from jwt import PyJWKClient
from datetime import datetime, timedelta, UTC
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, update as sqlalchemy_update
from backend.app.secrets import (
    get_jwt_secret,
    get_supabase_jwt_secret,
    get_supabase_url,
)

log = logging.getLogger(__name__)

_JWKS_CLIENT: PyJWKClient | None = None


def _get_jwks_client():
    global _JWKS_CLIENT
    if _JWKS_CLIENT is None:
        supabase_url = get_supabase_url()
        if not supabase_url:
            raise HTTPException(status_code=500, detail="Supabase URL not configured")
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        _JWKS_CLIENT = PyJWKClient(jwks_url, cache_keys=True)
    return _JWKS_CLIENT


async def get_me(user_id):
    data = await get_user_by_id(user_id)
    if not data:
        return None
    data.pop("hashed_pass", None)
    return data


async def login(email: EmailStr, password: str):
    user_details = await get_user_by_email(email)
    if user_details is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    # Accounts without a password hash (Google/Supabase-only) cannot log in via password.
    if not user_details.get("hashed_pass"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    user_bytes = password.encode()
    if bcrypt.checkpw(user_bytes, user_details["hashed_pass"].encode("utf-8")):
        return create_jwt(str(user_details["_id"]), user_details["role"])
    raise HTTPException(status_code=401, detail="Invalid credentials")


def create_access_jwt(user_id, role):
    ALGORITHM = "HS256"
    data = {"user_id": user_id, "role": role}
    expiry = datetime.now(UTC) + timedelta(minutes=60)
    data.update({"exp": expiry})
    return jwt.encode(data, get_jwt_secret(), algorithm=ALGORITHM)


def create_jwt(user_id, role):
    ALGORITHM = "HS256"
    secret = get_jwt_secret()
    data = {"user_id": user_id, "role": role}
    refresh_data = {"user_id": user_id, "role": role}
    access_expiry = datetime.now(UTC) + timedelta(hours=1)
    refresh_expiry = datetime.now(UTC) + timedelta(days=7)
    data.update({"exp": access_expiry})
    refresh_data.update({"exp": refresh_expiry})
    access_encoded_jwt = jwt.encode(data, secret, algorithm=ALGORITHM)
    refresh_encoded_jwt = jwt.encode(refresh_data, secret, algorithm=ALGORITHM)
    return {"access_token": access_encoded_jwt, "refresh_token": refresh_encoded_jwt}


async def signup(user: UserSignup):
    # Real-time email verification (blocks invalid/unknown/disposable addresses)
    """
    Create a user account after verifying the email address.
    
    Parameters:
    	user (UserSignup): The signup details, including email and password.
    
    Returns:
    	bool: `True` when the account is created successfully.
    """
    from backend.app.services.email_verification import verify_email

    verification = await verify_email(user.email)
    if not verification.allowed:
        raise HTTPException(status_code=400, detail=verification.reason)

    if await get_user_by_email(user.email) is not None:
        raise HTTPException(status_code=400, detail="Could not create account")
    encoded_pass = user.password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(encoded_pass, salt)
    hashed_pw = hashed_pw.decode("utf-8")
    user_in_db = UserInDB(email=user.email, hashed_pass=hashed_pw, role=Role.user)
    try:
        await create_user(user_in_db)
    except UserAlreadyExistsError:
        raise HTTPException(status_code=400, detail="Could not create account")
    return True


async def supabase_google_login(access_token: str):
    """Verify a Supabase access token and return BoloDB JWT tokens.

    Supports both ES256 (current) and HS256 (legacy) Supabase tokens.
    Auto-detects the algorithm from the token header.
    """
    try:
        header = jwt.get_unverified_header(access_token)
    except Exception as e:
        log.warning("Failed to decode Supabase token header: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    alg = header.get("alg", "")

    try:
        if alg == "ES256":
            jwks_client = _get_jwks_client()

            signing_key = await run_in_threadpool(
                jwks_client.get_signing_key_from_jwt, access_token
            )
            payload = jwt.decode(
                access_token,
                signing_key.key,
                algorithms=["ES256"],
                audience="authenticated",
            )
        elif alg == "HS256":
            try:
                jwt_secret = get_supabase_jwt_secret()
            except RuntimeError:
                raise HTTPException(
                    status_code=500,
                    detail="SUPABASE_JWT_SECRET is not configured on the server",
                )
            payload = jwt.decode(
                access_token,
                jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            raise HTTPException(
                status_code=401, detail=f"Unsupported signing algorithm: {alg}"
            )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Supabase token has expired")
    except HTTPException:
        raise
    except Exception as e:
        log.warning("Supabase token verification failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid Supabase token")

    try:
        supabase_id = payload.get("sub")
        if not supabase_id:
            raise HTTPException(status_code=400, detail="Invalid Supabase token")

        email = payload.get("email", "")
        if not email:
            raise HTTPException(status_code=400, detail="Supabase account has no email")

        app_metadata = payload.get("app_metadata", {})
        user_metadata = payload.get("user_metadata", {})
        provider = app_metadata.get("provider", "")
        email_verified = user_metadata.get("email_verified", False)

        existing = await get_user_by_supabase_id(supabase_id)
        if existing:
            return create_jwt(str(existing["_id"]), existing["role"])

        if provider == "google" and email_verified is True:
            existing_by_email = await get_user_by_email(email)
            if existing_by_email:
                await update_user(existing_by_email["_id"], supabase_id=supabase_id)
                return create_jwt(
                    str(existing_by_email["_id"]), existing_by_email["role"]
                )

        user_in_db = UserInDB(email=email, role=Role.user, supabase_id=supabase_id)
        try:
            uid = await create_user(user_in_db)
        except UserAlreadyExistsError:
            existing = await get_user_by_supabase_id(
                supabase_id
            ) or await get_user_by_email(email)
            if existing:
                return create_jwt(str(existing["_id"]), existing["role"])
            raise HTTPException(status_code=409, detail="Account already exists")
        return create_jwt(uid, Role.user.value)
    except HTTPException:
        raise
    except Exception:
        log.exception("Supabase login failed after token verification")
        raise HTTPException(
            status_code=500, detail="Login failed due to an internal error"
        )


async def change_password(user_id, old_password, new_password):
    """
    Change the password for a locally authenticated user.
    
    Parameters:
    	user_id: Identifier of the user whose password is being changed.
    	old_password: The user's current password.
    	new_password: The replacement password.
    
    Returns:
    	bool: `True` when the password is changed successfully.
    """
    validate_password_strength(new_password)
    user_details = await get_user_by_id(user_id)
    if user_details is None:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_details.get("hashed_pass"):
        raise HTTPException(
            status_code=400,
            detail="Social login accounts cannot change password here",
        )
    old_pass_enc = old_password.encode("utf-8")
    new_pass_enc = new_password.encode("utf-8")
    if bcrypt.checkpw(old_pass_enc, user_details["hashed_pass"].encode("utf-8")):
        salt = bcrypt.gensalt()
        new_hashed_pw = bcrypt.hashpw(new_pass_enc, salt)
        user_details["hashed_pass"] = new_hashed_pw.decode("utf-8")
        await update_user(
            user_id,
            hashed_pass=user_details["hashed_pass"],
        )
        return True
    raise HTTPException(status_code=401, detail="Incorrect Password, Please try again")


# ── Forgot / reset password ──────────────────────────────────────────────
# We generate a short-lived JWT reset token (15 min) rather than storing tokens
# server-side. For production, deliver the reset link via email (Resend/SendGrid);
# in this preview env, the link is logged so it can be copied from the console.


async def create_reset_token(user_id: str) -> str:
    """
    Create a short-lived token for resetting a user's password.

    Parameters:
    	user_id (str): Identifier of the user whose password will be reset.

    Returns:
    	str: A password reset token that expires after 15 minutes.
    """
    jti = secrets.token_urlsafe(32)
    jti_hash = hashlib.sha256(jti.encode()).hexdigest()
    expires_at = datetime.now(UTC) + timedelta(minutes=15)

    # Persist the hashed JTI with its expiry
    engine = get_engine()
    async with engine.begin() as conn:
        token_record = PasswordResetToken(
            user_id=user_id,
            jti_hash=jti_hash,
            expires_at=expires_at,
        )
        await conn.execute(
            PasswordResetToken.__table__.insert().values(
                user_id=user_id,
                jti_hash=jti_hash,
                expires_at=expires_at,
                consumed=False,
            )
        )

    data = {
        "user_id": user_id,
        "type": "password_reset",
        "jti": jti,
        "exp": expires_at,
    }
    return jwt.encode(data, get_jwt_secret(), algorithm="HS256")


async def request_password_reset(email: str, base_url: str = ""):
    """
    Request a password reset without revealing whether the email belongs to an eligible account.

    Parameters:
        email (str): Email address associated with the account.
        base_url (str): Optional base URL used to construct the reset link.

    Returns:
        bool: `True` in all cases.
    """
    user = await get_user_by_email(email)
    if user and user.get("hashed_pass"):
        token = await create_reset_token(str(user["_id"]))
        link = (
            f"{base_url.rstrip('/')}/reset-password?token={token}"
            if base_url
            else f"/reset-password?token={token}"
        )
        # TODO: Send this via email service (Resend/SendGrid). Logged for dev.
        log.info("Password reset requested")
    # Always return generic success to prevent user enumeration
    return True


async def reset_password(token: str, new_password: str):
    """
    Reset a user's password using a valid password-reset token.

    Parameters:
        token (str): Password-reset token containing the target user identifier.
        new_password (str): Replacement password that meets the required strength criteria.

    Returns:
        bool: `True` when the password is successfully updated.
    """
    validate_password_strength(new_password)
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=400, detail="Reset link expired. Please request a new one."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid reset link.")

    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid reset link.")

    jti = payload.get("jti")
    if not jti:
        raise HTTPException(status_code=400, detail="Invalid reset link.")

    user_id = payload.get("user_id")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset link.")

    # Hash the JTI and atomically consume the stored record
    jti_hash = hashlib.sha256(jti.encode()).hexdigest()
    engine = get_engine()
    async with engine.begin() as conn:
        # Find the token record
        result = await conn.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.jti_hash == jti_hash,
                PasswordResetToken.user_id == user_id,
            )
        )
        token_record = result.scalar_one_or_none()

        if not token_record:
            raise HTTPException(status_code=400, detail="Invalid reset link.")

        if token_record.consumed:
            raise HTTPException(status_code=400, detail="Reset link already used.")

        if datetime.now(UTC) > token_record.expires_at:
            raise HTTPException(
                status_code=400, detail="Reset link expired. Please request a new one."
            )

        # Mark as consumed
        await conn.execute(
            sqlalchemy_update(PasswordResetToken)
            .where(PasswordResetToken.jti_hash == jti_hash)
            .values(consumed=True)
        )

    salt = bcrypt.gensalt()
    new_hashed = bcrypt.hashpw(new_password.encode("utf-8"), salt).decode("utf-8")
    await update_user(user_id, hashed_pass=new_hashed)
    return True
