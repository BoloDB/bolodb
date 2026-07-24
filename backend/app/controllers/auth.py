import logging
import hashlib
import secrets

import bcrypt
from pydantic import EmailStr
from fastapi import HTTPException
from backend.app.models.user import (
    UpdateProfile,
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
from backend.app.models.auth_token import PasswordResetToken
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


async def update_profile(user_id: str, req: UpdateProfile):
    fields = req.model_dump(mode="json", exclude_unset=True)
    new_email = fields.get("email")

    if new_email:
        existing = await get_user_by_email(new_email)
        if existing and str(existing["_id"]) != str(user_id):
            raise HTTPException(
                status_code=409, detail="An account with this email already exists"
            )

        current = await get_me(user_id)
        if current and current.get("email") != new_email:
            fields["email_verified"] = False

    if fields:
        from sqlalchemy.exc import IntegrityError

        try:
            await update_user(user_id, **fields)
        except (IntegrityError, UserAlreadyExistsError):
            raise HTTPException(
                status_code=409, detail="An account with this email already exists"
            )

    if new_email and fields.get("email_verified") is False:
        from backend.app.pgdatabase.otp import create_otp
        from backend.app.services.email import send_verification_email

        otp_code = await create_otp(user_id, purpose="signup")
        await send_verification_email(new_email, otp_code)

    return await get_me(user_id)


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
        dict: {"email": user.email} when the account is created successfully.
    """
    from backend.app.services.email_verification import verify_email
    from backend.app.pgdatabase.otp import create_otp
    from backend.app.services.email import send_verification_email

    verification = await verify_email(user.email)
    if not verification.allowed:
        raise HTTPException(status_code=400, detail=verification.reason)

    if await get_user_by_email(user.email) is not None:
        raise HTTPException(
            status_code=400, detail="An account with this email already exists"
        )
    encoded_pass = user.password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_pw = bcrypt.hashpw(encoded_pass, salt)
    hashed_pw = hashed_pw.decode("utf-8")
    user_in_db = UserInDB(email=user.email, hashed_pass=hashed_pw, role=Role.user)
    try:
        uid = await create_user(user_in_db)
    except UserAlreadyExistsError:
        raise HTTPException(
            status_code=400, detail="An account with this email already exists"
        )

    # Generate OTP and send verification email
    otp_code = await create_otp(str(uid), purpose="signup")
    await send_verification_email(user.email, otp_code)

    return {"email": user.email}


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


# ── Email verification ──────────────────────────────────────────────────


async def verify_email_code(email: str, code: str):
    """Verify an OTP code and log the user in.

    Parameters:
        email (str): The user's email address.
        code (str): The 6-digit OTP code.

    Returns:
        dict: JWT tokens on success.

    Raises:
        HTTPException: If the user is not found, code is invalid/expired,
            or email is already verified.
    """
    from backend.app.pgdatabase.otp import verify_otp

    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email")

    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email is already verified")

    valid = await verify_otp(str(user["_id"]), code, purpose="signup")
    if not valid:
        raise HTTPException(
            status_code=400, detail="Invalid or expired verification code"
        )

    # Mark email as verified
    await update_user(user["_id"], email_verified=True)

    return create_jwt(str(user["_id"]), user["role"])


async def resend_verification_email(email: str):
    """Regenerate and resend the verification OTP.

    Parameters:
        email (str): The user's email address.

    Returns:
        dict: Always returns success to prevent email enumeration.

    Raises:
        HTTPException: If user not found or already verified.
    """
    from backend.app.pgdatabase.otp import create_otp
    from backend.app.services.email import send_verification_email as send_otp_email

    user = await get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="No account found with that email")

    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email is already verified")

    try:
        otp_code = await create_otp(str(user["_id"]), purpose="signup")
    except Exception:
        log.warning("create_otp failed for %s, retrying with fresh delete", email)
        from backend.app.pgdatabase.otp import delete_otp_for_user

        await delete_otp_for_user(str(user["_id"]), purpose="signup")
        otp_code = await create_otp(str(user["_id"]), purpose="signup")
    await send_otp_email(email, otp_code)

    return {"message": "Verification code sent"}


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
        from backend.app.services.email import send_password_reset_email

        await send_password_reset_email(email, link)
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
        # Lock the row so two concurrent resets can't both pass the consumed check.
        result = await conn.execute(
            select(PasswordResetToken)
            .where(
                PasswordResetToken.jti_hash == jti_hash,
                PasswordResetToken.user_id == user_id,
            )
            .with_for_update()
        )
        # Core connection (conn.execute) yields column Rows, not ORM entities,
        # so use one_or_none() to get a Row that supports .consumed/.expires_at
        # attribute access. scalar_one_or_none() would return just the id column.
        token_record = result.one_or_none()

        if not token_record:
            raise HTTPException(status_code=400, detail="Invalid reset link.")

        if token_record.consumed:
            raise HTTPException(status_code=400, detail="Reset link already used.")

        if datetime.now(UTC) > token_record.expires_at:
            raise HTTPException(
                status_code=400, detail="Reset link expired. Please request a new one."
            )

        # Mark as consumed. The extra `consumed == False` guard makes the write a
        # no-op for an already-used token even if the lock above is unavailable.
        await conn.execute(
            sqlalchemy_update(PasswordResetToken)
            .where(
                PasswordResetToken.jti_hash == jti_hash,
                PasswordResetToken.consumed.is_(False),
            )
            .values(consumed=True)
        )

    salt = bcrypt.gensalt()
    new_hashed = bcrypt.hashpw(new_password.encode("utf-8"), salt).decode("utf-8")
    await update_user(user_id, hashed_pass=new_hashed)
    return True
