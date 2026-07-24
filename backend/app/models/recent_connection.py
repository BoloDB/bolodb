import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Text, UniqueConstraint, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, _utcnow, _uuid7


class RecentConnection(Base):
    __tablename__ = "recent_connections"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_url: Mapped[str] = mapped_column(Text, nullable=False)
    display_url: Mapped[str] = mapped_column(String, nullable=False)
    alias_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dialect: Mapped[str] = mapped_column(String, nullable=False)
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (UniqueConstraint("workspace_id", "db_id"),)
