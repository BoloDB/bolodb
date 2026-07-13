from fastapi import APIRouter, Request, Depends, Cookie, HTTPException
from fastapi.responses import JSONResponse
from backend.app.models.user import UserSignup, UserLogin, GoogleLogin
import backend.app.controllers.auth
from backend.app.dependencies import get_current_user
from backend.app.secrets import get_jwt_secret, get_cookie_secure, get_google_client_id
from backend.app.i18n.translator import _
import jwt

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/refresh")
async def refresh_jwt(refresh_token: str = Cookie(None)):
    if refresh_token is None:
        raise HTTPException(status_code=401, detail=_("Access Denied"))
    try:
        token = jwt.decode(refresh_token, get_jwt_secret(), algorithms=["HS256"])
        response = JSONResponse({"message": _("Token Set successfully")})
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
            status_code=401, detail=_("Session Expired, please login again")
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail=_("Invalid Token"))


@router.get("/me")
async def me(user_token=Depends(get_current_user)):
    user = backend.app.controllers.auth.get_me(user_token["user_id"])
    user.pop("hashed_pass", None)
    return JSONResponse({"message": _("My details"), "content": user})


@router.post("/login")
async def login(login_data: UserLogin):
    token = backend.app.controllers.auth.login(login_data.email, login_data.password)
    response = JSONResponse({"message": _("Login Success")})
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
async def signup(user_data: UserSignup):
    backend.app.controllers.auth.signup(user_data)
    return JSONResponse({"message": _("Signup Successful")}, status_code=201)


@router.post("/google")
async def google_auth(google_data: GoogleLogin):
    client_id = get_google_client_id()
    if not client_id:
        raise HTTPException(
            status_code=500, detail=_("Google sign-in is not configured")
        )
    if google_data.client_id != client_id:
        raise HTTPException(status_code=400, detail=_("Client ID mismatch"))
    tokens = backend.app.controllers.auth.google_login(
        google_data.id_token, google_data.client_id
    )
    response = JSONResponse({"message": _("Google sign-in successful")})
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
    response = JSONResponse({"message": _("Logout Successfull")})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.post("/change-password")
async def change_password(request: Request, user_token=Depends(get_current_user)):
    body = await request.json()
    backend.app.controllers.auth.change_password(
        user_token["user_id"], body["old_password"], body["new_password"]
    )
    return JSONResponse({"message": _("Password changed successfully")})
