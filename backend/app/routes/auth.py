from fastapi import APIRouter, Request, Depends, Cookie, HTTPException
from fastapi.responses import JSONResponse
from backend.app.models.user import UserSignup
import backend.app.controllers.auth
from backend.app.dependencies import get_current_user
from backend.app.secrets import get_jwt_secret
import jwt

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/refresh")
async def refresh_jwt(refresh_token: str = Cookie(None)):
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Access Denied")
    try:
        token = jwt.decode(refresh_token, get_jwt_secret(), algorithms=["HS256"])
        response = JSONResponse({"message": "Token Set successfully"})
        new_token = backend.app.controllers.auth.create_access_jwt(
            user_id=token["user_id"], role=token["role"]
        )
        response.set_cookie(key="access_token", value=new_token, httponly=True)
        return response
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Session Expired, please login again"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")


@router.get("/me")
async def me(user_token=Depends(get_current_user)):
    user = backend.app.controllers.auth.get_me(user_token["user_id"])
    user.pop("hashed_pass", None)
    return JSONResponse({"message": "My details", "content": user})


@router.post("/login")
async def login(request: Request):
    body = await request.json()
    token = backend.app.controllers.auth.login(body["email"], body["password"])
    response = JSONResponse({"message": "Login Success"})
    response.set_cookie(
        key="access_token",
        value=token["access_token"],
        httponly=True,
        secure=True,
        samesite="lax",
    )
    response.set_cookie(
        key="refresh_token", value=token["refresh_token"], httponly=True
    )
    return response


@router.post("/signup")
async def signup(request: Request):
    body = await request.json()
    user_data = UserSignup(email=body["email"], password=body["password"])
    backend.app.controllers.auth.signup(user_data)
    return JSONResponse({"message": "Signup Successful"}, status_code=201)


@router.post("/logout")
async def logout():
    response = JSONResponse({"message": "Logout Successfull"})
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return response


@router.post("/change-password")
async def change_password(request: Request, user_token=Depends(get_current_user)):
    body = await request.json()
    backend.app.controllers.auth.change_password(
        user_token["user_id"], body["old_password"], body["new_password"]
    )
    return JSONResponse({"message": "Password changed successfully"})
