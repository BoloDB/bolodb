import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, _utcnow, _uuid7


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Owning user. Conversations are private to the user that created them,
    # scoped within their workspace — other members cannot see them.
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False, default="")
    database_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class QueryHistory(Base):
    __tablename__ = "query_history"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[str] = mapped_column(String, nullable=False, default="low")
    restatement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # The model's chart choice for this result. Null for turns recorded before
    # charts were part of the SQL generation output.
    chart: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
