import uuid
import re
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy import select, delete
from backend.app.pgdatabase.engine import async_session
from backend.app.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite
from backend.app.models.user import UserInDB
from backend.app.pgdatabase.serialization import _to_uuid


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


async def list_workspaces(user_id: str):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(WorkspaceMember.user_id == uid)
            .order_by(Workspace.created_at.desc())
        )
        rows = result.all()
        return [
            {
                "id": str(r[0].id),
                "name": r[0].name,
                "slug": r[0].slug,
                "role": r[1],
                "created_at": r[0].created_at,
            }
            for r in rows
        ]


async def create_workspace(user_id: str, name: str):
    uid = _to_uuid(user_id)
    base_slug = slugify(name) or "workspace"

    async with async_session() as session:
        # Simple unique slug generation
        slug = base_slug
        counter = 1
        while True:
            exists = await session.execute(
                select(Workspace).where(Workspace.slug == slug)
            )
            if not exists.scalar_one_or_none():
                break
            slug = f"{base_slug}-{counter}"
            counter += 1

        workspace = Workspace(name=name, slug=slug, created_by=uid)
        session.add(workspace)
        await session.flush()

        member = WorkspaceMember(workspace_id=workspace.id, user_id=uid, role="owner")
        session.add(member)
        await session.commit()
        return {
            "id": str(workspace.id),
            "name": workspace.name,
            "slug": workspace.slug,
            "role": "owner",
        }


async def get_workspace(workspace_id: str, user_id: str):
    wid = _to_uuid(workspace_id)
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(Workspace, WorkspaceMember.role)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(Workspace.id == wid, WorkspaceMember.user_id == uid)
        )
        row = result.first()
        if not row:
            raise HTTPException(404, "Workspace not found")
        return {
            "id": str(row[0].id),
            "name": row[0].name,
            "slug": row[0].slug,
            "role": row[1],
            "created_at": row[0].created_at,
        }


async def list_members(workspace_id: str):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(
                WorkspaceMember, UserInDB.email, UserInDB.first_name, UserInDB.last_name
            )
            .join(UserInDB, WorkspaceMember.user_id == UserInDB.id)
            .where(WorkspaceMember.workspace_id == wid)
        )
        rows = result.all()
        return [
            {
                "user_id": str(r[0].user_id),
                "email": r[1],
                "first_name": r[2],
                "last_name": r[3],
                "role": r[0].role,
                "joined_at": r[0].joined_at,
            }
            for r in rows
        ]


async def invite_user(workspace_id: str, email: str, role: str, inviter_id: str):
    wid = _to_uuid(workspace_id)
    uid = _to_uuid(inviter_id)
    async with async_session() as session:
        # Check if already a member
        user_exists = await session.execute(
            select(UserInDB).where(UserInDB.email == email)
        )
        user = user_exists.scalar_one_or_none()
        if user:
            member = await session.execute(
                select(WorkspaceMember).where(
                    WorkspaceMember.workspace_id == wid,
                    WorkspaceMember.user_id == user.id,
                )
            )
            if member.scalar_one_or_none():
                raise HTTPException(400, "User is already a member")

        # Create invite
        token = str(uuid.uuid4())
        from datetime import datetime, timedelta, timezone

        expires = datetime.now(timezone.utc) + timedelta(days=7)

        invite = WorkspaceInvite(
            workspace_id=wid,
            email=email,
            role=role,
            token=token,
            invited_by=uid,
            expires_at=expires,
        )
        session.add(invite)
        await session.commit()
        return {
            "id": str(invite.id),
            "email": invite.email,
            "role": invite.role,
            "token": invite.token,
            "expires_at": invite.expires_at,
        }


async def update_member_role(workspace_id: str, target_user_id: str, role: str):
    wid = _to_uuid(workspace_id)
    tuid = _to_uuid(target_user_id)
    if role not in ["admin", "member", "owner"]:
        raise HTTPException(400, "Invalid role")

    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == tuid
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(404, "Member not found")
        member.role = role
        await session.commit()
        return {"ok": True}


async def remove_member(workspace_id: str, target_user_id: str):
    wid = _to_uuid(workspace_id)
    tuid = _to_uuid(target_user_id)
    async with async_session() as session:
        await session.execute(
            delete(WorkspaceMember).where(
                WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == tuid
            )
        )
        await session.commit()
        return {"ok": True}


async def get_invites(user_email: str):
    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceInvite, Workspace.name)
            .join(Workspace, WorkspaceInvite.workspace_id == Workspace.id)
            .where(
                WorkspaceInvite.email == user_email,
                WorkspaceInvite.accepted_at.is_(None),
            )
        )
        rows = result.all()
        return [
            {
                "id": str(r[0].id),
                "workspace_id": str(r[0].workspace_id),
                "workspace_name": r[1],
                "role": r[0].role,
                "token": r[0].token,
                "expires_at": r[0].expires_at,
            }
            for r in rows
        ]


async def accept_invite(token: str, user_id: str, user_email: str):
    uid = _to_uuid(user_id)
    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceInvite).where(
                WorkspaceInvite.token == token, WorkspaceInvite.email == user_email
            )
        )
        invite = result.scalar_one_or_none()
        if not invite:
            raise HTTPException(404, "Invite not found or invalid email")
        if invite.accepted_at:
            raise HTTPException(400, "Invite already accepted")
        if invite.expires_at < datetime.now(invite.expires_at.tzinfo):
            raise HTTPException(400, "Invite expired")

        member = WorkspaceMember(
            workspace_id=invite.workspace_id, user_id=uid, role=invite.role
        )
        invite.accepted_at = datetime.now(invite.expires_at.tzinfo)
        session.add(member)
        await session.commit()
        return {"ok": True, "workspace_id": str(invite.workspace_id)}
