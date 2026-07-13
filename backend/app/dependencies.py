from fastapi import HTTPException, Cookie, Request
import jwt

from backend.app.secrets import get_jwt_secret
from backend.app.i18n.translator import _


async def get_current_user(access_token: str = Cookie(None)):
    if access_token is None:
        raise HTTPException(status_code=401, detail=_("Access Denied"))
    try:
        token_data = jwt.decode(access_token, get_jwt_secret(), algorithms=["HS256"])
        return token_data
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail=_("Session Expired, please login again")
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail=_("Invalid Token"))


def get_db(request: Request):
    return request.app.state.db


def get_kb(request: Request):
    return request.app.state.kb


def get_providers(request: Request):
    return request.app.state.providers


def get_session_log(request: Request):
    return request.app.state.session_log


def get_cfg(request: Request):
    return request.app.state.cfg
