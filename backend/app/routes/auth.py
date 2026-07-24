from fastapi import APIRouter, Depends, Cookie, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from backend.app.models.user import UserSignup, UserLogin, SupabaseLogin
import backend.app.controllers.auth
from backend.app.dependencies import get_current_user
from backend.app.ratelimit import limiter
from backend.app.secrets import get_jwt_secret, get_cookie_secure, get_frontend_url
import jwt

router = APIRouter(prefix="/api/auth", tags=["auth"])


class ChangePasswordReq(BaseModel):
    old_password: str
    new_password: str


class ForgotPasswordReq(BaseModel):
    email: str


class ResetPasswordReq(BaseModel):
    token: str
    new_password: str


class VerifyEmailReq(BaseModel):
    email: str
    code: str


class ResendVerificationReq(BaseModel):
    email: str


@router.post("/refresh")
async def refresh_jwt(refresh_token: str = Cookie(None)):
    """
    Refreshes the access token using a valid refresh token.

    Parameters:
        refresh_token (str): Refresh token used to authenticate the session.

    Returns:
        JSONResponse: Response containing a newly issued access token cookie.

    Raises:
        HTTPException: If the refresh token is missing, expired, or invalid.
    """
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Access Denied")
    try:
        token = jwt.decode(refresh_token, get_jwt_secret(), algorithms=["HS256"])
        response = JSONResponse({"message": "Token Set successfully"})
        new_token = backend.app.controllers.auth.create_access_jwt(
            user_id=token["user_id"], role=token["role"]
        )
        secure = get_cookie_secure()
        response.set_cookie(
            key="access_token",
            value=new_token,
            httponly=True,
            secure=secure,
            samesite="lax",
        )
        return response
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Session Expired, please login again"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")


@router.get("/me")
async def me(user_token=Depends(get_current_user)):
    user = await backend.app.controllers.auth.get_me(user_token["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return JSONResponse({"message": "My details", "content": user})


@router.patch("/me")
async def update_me(
    req: backend.app.models.user.UpdateProfile, user_token=Depends(get_current_user)
):
    user = await backend.app.controllers.auth.update_profile(user_token["user_id"], req)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return JSONResponse({"message": "Profile updated", "content": user})


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, login_data: UserLogin):
    token = await backend.app.controllers.auth.login(
        login_data.email, login_data.password
    )
    response = JSONResponse({"message": "Login Success"})
    secure = get_cookie_secure()
    response.set_cookie(
        key="access_token",
        value=token["access_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=token["refresh_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    return response


@router.post("/signup")
@limiter.limit("5/minute")
async def signup(request: Request, user_data: UserSignup):
    result = await backend.app.controllers.auth.signup(user_data)
    return JSONResponse(
        {"message": "Check your email for verification code", "email": result["email"]},
        status_code=201,
    )


@router.post("/supabase-google")
@limiter.limit("20/minute")
async def supabase_google_auth(request: Request, supabase_data: SupabaseLogin):
    tokens = await backend.app.controllers.auth.supabase_google_login(
        supabase_data.access_token
    )
    response = JSONResponse({"message": "Supabase Google sign-in successful"})
    secure = get_cookie_secure()
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    return response


@router.post("/logout")
async def logout():
    response = JSONResponse({"message": "Logout Successfull"})
    secure = get_cookie_secure()
    response.delete_cookie("access_token", httponly=True, secure=secure, samesite="lax")
    response.delete_cookie(
        "refresh_token", httponly=True, secure=secure, samesite="lax"
    )
    return response


@router.post("/change-password")
async def change_password(
    req: ChangePasswordReq,
    user_token=Depends(get_current_user),
):
    """Change the authenticated user's password.

    Parameters:
        req (ChangePasswordReq): The current and replacement passwords.
        user_token: Authentication data for the current user.

    Returns:
        JSONResponse: A success message confirming the password change.
    """
    await backend.app.controllers.auth.change_password(
        user_token["user_id"], req.old_password, req.new_password
    )
    return JSONResponse({"message": "Password changed successfully"})


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordReq, request: Request):
    """Request a password reset link. Always returns success to prevent user enumeration."""
    frontend_url = get_frontend_url()
    if frontend_url:
        base_url = frontend_url.rstrip("/")
    else:
        base_url = str(request.base_url).rstrip("/")
    await backend.app.controllers.auth.request_password_reset(
        req.email, base_url=base_url
    )
    return JSONResponse(
        {
            "message": "If an account exists for that email, we've sent reset instructions."
        }
    )


@router.post("/reset-password")
async def reset_password(req: ResetPasswordReq):
    """
    Reset a user's password using a password-reset token.

    Parameters:
        req (ResetPasswordReq): The reset token and new password.

    Returns:
        JSONResponse: A success message confirming the password reset.
    """
    await backend.app.controllers.auth.reset_password(req.token, req.new_password)
    return JSONResponse({"message": "Password reset successfully"})


@router.post("/verify-email")
async def verify_email(req: VerifyEmailReq):
    """Verify email with OTP code and log the user in."""
    tokens = await backend.app.controllers.auth.verify_email_code(req.email, req.code)
    response = JSONResponse({"message": "Email verified successfully"})
    secure = get_cookie_secure()
    response.set_cookie(
        key="access_token",
        value=tokens["access_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=secure,
        samesite="lax",
    )
    return response


@router.post("/resend-verification")
async def resend_verification(req: ResendVerificationReq):
    """Resend the email verification OTP code."""
    result = await backend.app.controllers.auth.resend_verification_email(req.email)
    return JSONResponse(result)
