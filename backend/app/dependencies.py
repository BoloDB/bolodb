from fastapi import HTTPException, Cookie, Request, Depends, Header
import jwt
from sqlalchemy import select

from backend.app import tokens
from backend.app.secrets import get_jwt_secret
from backend.app.pgdatabase.engine import async_session
from backend.app.models.orm_user import User
from backend.app.models.workspace import WorkspaceMember
from backend.app.models.workspace_settings import WorkspaceSettings
from backend.app.permissions import has_permission
from backend.app.pgdatabase.serialization import _to_uuid


async def _token_version_is_current(token_data) -> bool:
    """Whether this token was minted since the account was last recovered.

    This is the one part of authentication that cannot be answered from the
    token alone. A JWT is only a claim the server signed at some point in the
    past; deciding it is *no longer* valid means keeping something on the server
    that the token can be measured against, and one integer per user is the
    cheapest form of that — far cheaper than remembering every token issued.

    Costs a primary-key lookup per authenticated request. Most routes already
    make one for workspace membership, so this roughly doubles auth queries
    rather than introducing the first. If that ever shows up in a profile, cache
    it with a short TTL — but note the TTL becomes the window in which a revoked
    session still works, which is exactly the thing being bought here.
    """
    try:
        uid = _to_uuid(token_data.get("user_id", token_data.get("sub")))
    except (ValueError, TypeError):
        return False

    async with async_session() as session:
        stored = await session.scalar(select(User.token_version).where(User.id == uid))

    if stored is None:
        # No such user — a token for a deleted account is not a live session.
        return False
    # A token predating the claim reads as 0, which is where every user starts,
    # so nothing is revoked until something actually bumps the number.
    return int(token_data.get(tokens.VERSION_CLAIM, 0)) == int(stored)


async def get_current_user(access_token: str = Cookie(None)):
    if access_token is None:
        raise HTTPException(status_code=401, detail="Access Denied")
    try:
        token_data = jwt.decode(access_token, get_jwt_secret(), algorithms=["HS256"])
        # A valid signature only says we minted this, not what for. Every token
        # this app issues carries a user_id and verifies against the same secret,
        # so without the kind check a refresh token, a password-reset token or a
        # Slack OAuth state would each work here as a session.
        if not tokens.is_kind(token_data, tokens.ACCESS):
            raise HTTPException(status_code=401, detail="Invalid Token")
        if not await _token_version_is_current(token_data):
            # The account was recovered (password changed or reset) after this
            # token was minted, so it belongs to a session that is meant to be
            # over. Same message as any other bad token: which one it is is not
            # the holder's business.
            raise HTTPException(status_code=401, detail="Invalid Token")
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


async def workspace_has_permission(workspace, permission_key: str) -> bool:
    """Resolve whether the current workspace member holds a fine-grained permission."""
    if workspace["role"] == "owner":
        return True

    wid = _to_uuid(workspace["workspace_id"])
    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceSettings).where(WorkspaceSettings.workspace_id == wid)
        )
        settings = result.scalar_one_or_none()

    role_permissions = getattr(settings, "role_permissions", None)
    return has_permission(workspace["role"], role_permissions, permission_key)


def require_permission(permission_key: str):
    async def permission_dependency(workspace=Depends(get_current_workspace)):
        if not await workspace_has_permission(workspace, permission_key):
            raise HTTPException(
                status_code=403, detail=f"Permission '{permission_key}' required"
            )

        return workspace

    return permission_dependency


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
