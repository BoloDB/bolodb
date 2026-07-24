"""
New: workspaces
id, name, slug, created_by (FK users), created_at

New: workspace_members — this is the crux of the whole system
id, workspace_id (FK), user_id (FK), role (enum: owner / admin / member), joined_at, invited_by
Unique constraint on (workspace_id, user_id). Index on user_id alone too — you'll query "what workspaces is this user in" constantly for the workspace switcher.

New: workspace_invites (can trail slightly behind if you want to ship core scoping first)
id, workspace_id, email, role, token, invited_by, expires_at, accepted_at

Modified (9 tables): swap user_id → workspace_id, rebuild the (user_id, db_id) indexes as (workspace_id, db_id). QueryHistory gets both workspace_id and keeps user_id.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    UniqueConstraint,
    CheckConstraint,
    ForeignKey,
    DateTime,
    Index,
)
from typing import Optional
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base, _utcnow, _uuid7


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_workspace_member"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name="ck_workspace_member_role"
        ),
        Index("ix_workspace_member_user", "user_id"),
    )


class WorkspaceInvite(Base):
    __tablename__ = "workspace_invites"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    __table_args__ = (
        UniqueConstraint("workspace_id", "email", name="uq_workspace_invite_email"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'member')", name="ck_workspace_invite_role"
        ),
    )


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
