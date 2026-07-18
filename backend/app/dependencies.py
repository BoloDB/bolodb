from fastapi import HTTPException, Cookie, Request
import jwt

from backend.app.secrets import get_jwt_secret


async def get_current_user(access_token: str = Cookie(None)):
    if access_token is None:
        raise HTTPException(status_code=401, detail="Access Denied")
    try:
        token_data = jwt.decode(access_token, get_jwt_secret(), algorithms=["HS256"])
        return token_data
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, detail="Session Expired, please login again"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Token")


def get_db(request: Request):
    return request.app.state.db


def get_kb(request: Request):
    """
    Return the application's knowledge base collection.

    Parameters:
        request (Request): The current application request.

    Returns:
        The knowledge base collection stored in the application state.
    """
    return request.app.state.kbs


def get_providers(request: Request):
    """Return the providers stored in the application state.

    Parameters:
        request (Request): The incoming request containing the application state.

    Returns:
        The configured providers.
    """
    return request.app.state.providers


def get_session_log(request: Request):
    return request.app.state.session_log


def get_cfg(request: Request):
    return request.app.state.cfg
