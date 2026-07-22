from fastapi import HTTPException, Cookie, Request, Depends, Header
import jwt
from sqlalchemy import select

from backend.app.secrets import get_jwt_secret
from backend.app.pgdatabase.engine import async_session
from backend.app.models.workspace import WorkspaceMember
from backend.app.pgdatabase.serialization import _to_uuid


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


async def get_current_workspace(
    x_workspace_id: str = Header(None), user=Depends(get_current_user)
):
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header missing")
    try:
        wid = _to_uuid(x_workspace_id)
        uid = _to_uuid(user.get("user_id", user.get("sub")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid workspace_id or user_id")

    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == uid
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(
                status_code=403, detail="Not a member of this workspace"
            )

        return {
            "workspace_id": str(member.workspace_id),
            "role": member.role,
            "user_id": str(member.user_id),
        }


def require_role(minimum_role: str):
    def role_dependency(workspace=Depends(get_current_workspace)):
        roles = {"member": 1, "admin": 2, "owner": 3}
        user_role = workspace["role"]
        if roles.get(user_role, 0) < roles.get(minimum_role, 1):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return workspace

    return role_dependency


def get_current_db_id(x_db_id: str = Header(None)):
    return x_db_id


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
