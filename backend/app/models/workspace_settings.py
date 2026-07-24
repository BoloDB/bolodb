import uuid
from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, _utcnow


class WorkspaceSettings(Base):
    __tablename__ = "workspace_settings"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
    )
    default_invite_role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="member"
    )
    invite_expiry_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    activity_retention_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=30
    )
    role_permissions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    def __init__(self, **kw):
        kw.setdefault("default_invite_role", "member")
        kw.setdefault("invite_expiry_days", 7)
        kw.setdefault("activity_retention_days", 30)
        kw.setdefault("role_permissions", {})
        super().__init__(**kw)
