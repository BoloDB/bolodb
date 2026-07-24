import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, String, DateTime
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, _utcnow, _uuid7


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_pass: Mapped[str] = mapped_column(String, nullable=False, default="")
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    google_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    supabase_id: Mapped[Optional[str]] = mapped_column(
        String, unique=True, nullable=True
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column(
        "metadata", JSONB, nullable=True, default=dict
    )
    tour_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
