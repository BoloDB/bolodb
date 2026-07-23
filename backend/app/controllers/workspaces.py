import re
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from backend.app.services.email import send_workspace_invite_email
from backend.app.pgdatabase.engine import async_session
from backend.app.models.workspace import Workspace, WorkspaceMember, WorkspaceInvite
from backend.app.models.orm_user import User
from backend.app.pgdatabase.serialization import _to_uuid
from backend.app.controllers.activity import log_activity


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# Crockford base32: no I, L, O or U, so a code survives being read aloud or
# copied by hand without the 1/I and 0/O confusions.
_CODE_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def generate_invite_code() -> str:
    """A short, human-readable invite code in the form BOLO-XXXX-XXXX."""
    body = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
    return f"BOLO-{body[:4]}-{body[4:]}"


def normalize_invite_code(token: str) -> str:
    """Canonicalise a pasted code so casing, spaces and stray hyphens still match.

    Only applied to codes in our own format — legacy UUID tokens are left as
    typed, since they are lowercase and hyphen-significant.
    """
    if not token:
        return ""
    stripped = token.strip()
    compact = re.sub(r"[\s-]+", "", stripped).upper()
    if not compact.startswith("BOLO") or len(compact) != 12:
        return stripped
    return f"BOLO-{compact[4:8]}-{compact[8:]}"


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

    max_attempts = 10
    slug = base_slug

    for attempt in range(max_attempts):
        async with async_session() as session:
            try:
                if attempt > 0:
                    slug = f"{base_slug}-{attempt}"

                exists = await session.execute(
                    select(Workspace).where(Workspace.slug == slug)
                )
                if exists.scalar_one_or_none():
                    continue

                workspace = Workspace(name=name, slug=slug, created_by=uid)
                session.add(workspace)
                await session.flush()

                member = WorkspaceMember(
                    workspace_id=workspace.id, user_id=uid, role="owner"
                )
                session.add(member)
                await session.commit()
                await log_activity(
                    str(workspace.id),
                    user_id,
                    "workspace.created",
                    "workspace",
                    str(workspace.id),
                    {"name": name},
                )
                return {
                    "id": str(workspace.id),
                    "name": workspace.name,
                    "slug": workspace.slug,
                    "role": "owner",
                }
            except IntegrityError:
                await session.rollback()
                continue

    raise HTTPException(500, "Could not generate a unique workspace slug")


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


async def update_workspace(
    workspace_id: str, name: str | None, actor_id: str | None = None
):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        try:
            from sqlalchemy import update

            stmt = update(Workspace).where(Workspace.id == wid)
            values = {}
            if name is not None:
                values["name"] = name.strip()
            if values:
                stmt = stmt.values(**values)
                result = await session.execute(stmt)
                await session.commit()

                await log_activity(
                    workspace_id,
                    actor_id,
                    "workspace.updated",
                    "workspace",
                    workspace_id,
                    values,
                )
                return {"ok": result.rowcount > 0, "name": values.get("name")}
            return {"ok": True}
        except Exception:
            await session.rollback()
            raise


async def list_members(workspace_id: str):
    wid = _to_uuid(workspace_id)
    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceMember, User.email)
            .join(User, WorkspaceMember.user_id == User.id)
            .where(WorkspaceMember.workspace_id == wid)
        )
        rows = result.all()
        return [
            {
                "user_id": str(r[0].user_id),
                "email": r[1],
                "role": r[0].role,
                "joined_at": r[0].joined_at,
                "created_at": r[0].joined_at,
            }
            for r in rows
        ]


async def invite_user(workspace_id: str, email: str, role: str, inviter_id: str):
    wid = _to_uuid(workspace_id)
    uid = _to_uuid(inviter_id)
    if role not in ["admin", "member"]:
        raise HTTPException(400, "Invalid role for invite")

    async with async_session() as session:
        # Check if user is already a member
        user_exists = await session.execute(select(User).where(User.email == email))
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

        token = generate_invite_code()
        expires = datetime.now(timezone.utc) + timedelta(days=7)

        # Query existing invite for this workspace + email
        existing = await session.execute(
            select(WorkspaceInvite).where(
                WorkspaceInvite.workspace_id == wid,
                WorkspaceInvite.email == email,
            )
        )
        invite = existing.scalar_one_or_none()

        if invite:
            invite.role = role
            invite.token = token
            invite.invited_by = uid
            invite.expires_at = expires
            invite.accepted_at = None
        else:
            invite = WorkspaceInvite(
                workspace_id=wid,
                email=email,
                role=role,
                token=token,
                invited_by=uid,
                expires_at=expires,
            )
            session.add(invite)

        try:
            await session.commit()

            # Fetch workspace name for email
            ws = await session.get(Workspace, wid)
            if ws:
                await send_workspace_invite_email(email, ws.name, token)

            await log_activity(
                workspace_id,
                inviter_id,
                "member.invited",
                "member",
                str(invite.id),
                {"email": email, "role": role},
            )
            return {
                "id": str(invite.id),
                "email": invite.email,
                "role": invite.role,
                "token": invite.token,
                "expires_at": invite.expires_at,
            }
        except IntegrityError:
            await session.rollback()
            raise HTTPException(400, "Could not process invite")


async def update_member_role(
    workspace_id: str,
    target_user_id: str,
    role: str,
    actor_id: str | None = None,
    actor_role: str = "admin",
):
    wid = _to_uuid(workspace_id)
    tuid = _to_uuid(target_user_id)
    if role not in ["admin", "member"]:
        raise HTTPException(400, "Invalid role")

    role_rank = {"member": 1, "admin": 2, "owner": 3}
    actor_rank = role_rank.get(actor_role, 0)
    if actor_rank < role_rank["admin"]:
        raise HTTPException(403, "Insufficient permissions")

    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == tuid
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(404, "Member not found")

        target_rank = role_rank.get(member.role, 0)
        # Callers may only modify members strictly below their own rank.
        if target_rank >= actor_rank:
            raise HTTPException(
                403, "Cannot change the role of a member at or above your own level"
            )
        if role_rank.get(role, 0) >= actor_rank:
            raise HTTPException(403, "Cannot assign a role at or above your own level")

        if member.role == "owner" and role != "owner":
            owners_count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == wid,
                    WorkspaceMember.role == "owner",
                )
            )
            if owners_count <= 1:
                raise HTTPException(
                    400, "Cannot change role of the sole workspace owner"
                )

        member.role = role
        await session.commit()
        await log_activity(
            workspace_id,
            actor_id,
            "member.role_updated",
            "member",
            target_user_id,
            {"new_role": role},
        )
        return {"ok": True}


async def remove_member(workspace_id: str, target_user_id: str):
    wid = _to_uuid(workspace_id)
    tuid = _to_uuid(target_user_id)
    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == wid, WorkspaceMember.user_id == tuid
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise HTTPException(404, "Member not found")

        if member.role == "owner":
            owners_count = await session.scalar(
                select(func.count())
                .select_from(WorkspaceMember)
                .where(
                    WorkspaceMember.workspace_id == wid,
                    WorkspaceMember.role == "owner",
                )
            )
            if owners_count <= 1:
                raise HTTPException(400, "Cannot remove the sole owner of a workspace")

        await session.delete(member)
        await session.commit()
        await log_activity(
            workspace_id, None, "member.removed", "member", target_user_id, {}
        )
        return {"ok": True}


async def get_invites(user_email: str):
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        result = await session.execute(
            select(WorkspaceInvite, Workspace.name)
            .join(Workspace, WorkspaceInvite.workspace_id == Workspace.id)
            .where(
                WorkspaceInvite.email == user_email,
                WorkspaceInvite.accepted_at.is_(None),
                WorkspaceInvite.expires_at > now,
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
    token = normalize_invite_code(token)
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

        try:
            member = WorkspaceMember(
                workspace_id=invite.workspace_id, user_id=uid, role=invite.role
            )
            invite.accepted_at = datetime.now(invite.expires_at.tzinfo)
            session.add(member)
            await session.commit()
            await log_activity(
                str(invite.workspace_id),
                user_id,
                "member.joined",
                "member",
                user_id,
                {"role": invite.role},
            )
            return {"ok": True, "workspace_id": str(invite.workspace_id)}
        except IntegrityError:
            await session.rollback()
            raise HTTPException(400, "User is already a member of this workspace")
