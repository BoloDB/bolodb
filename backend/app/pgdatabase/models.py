"""SQLAlchemy ORM models for application state."""

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    String,
    Integer,
    UniqueConstraint,
    ForeignKey,
    Text,
    DateTime,
    Index,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid7():
    try:
        return uuid.uuid7()
    except AttributeError:
        pass
    ts = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    rand_a = rand >> 68
    rand_b = rand & ((1 << 62) - 1)
    return uuid.UUID(
        int=(ts << 80) | (0x7 << 76) | (rand_a << 64) | (0x2 << 62) | rand_b
    )


class Base(DeclarativeBase):
    pass


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
    tour_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
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
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[str] = mapped_column(String, nullable=False, default="low")
    restatement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class RecentConnection(Base):
    __tablename__ = "recent_connections"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_url: Mapped[str] = mapped_column(Text, nullable=False)
    display_url: Mapped[str] = mapped_column(String, nullable=False)
    dialect: Mapped[str] = mapped_column(String, nullable=False)
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (UniqueConstraint("user_id", "db_id"),)


class VerifiedQA(Base):
    __tablename__ = "verified_qas"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    restatement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (
        UniqueConstraint("user_id", "db_id", "question", name="uq_verified_qa_user_db_question"),
        Index("ix_verified_qa_user_db", "user_id", "db_id"),
    )


class Glossary(Base):
    __tablename__ = "glossary_terms"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    maps_to: Mapped[str] = mapped_column(String, nullable=False)
    sql_hint: Mapped[str] = mapped_column(String, nullable=False, default="")
    __table_args__ = (Index("ix_glossary_user_db", "user_id", "db_id"),)


class CatalogColumn(Base):
    __tablename__ = "catalog_columns"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_cat_col_user_db", "user_id", "db_id"),)


class CatalogMetric(Base):
    __tablename__ = "catalog_metrics"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql_expression: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_cat_met_user_db", "user_id", "db_id"),)


class CatalogJoin(Base):
    __tablename__ = "catalog_joins"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    tables: Mapped[str] = mapped_column(String, nullable=False)
    join_condition: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (Index("ix_cat_join_user_db", "user_id", "db_id"),)


class CatalogSynonym(Base):
    __tablename__ = "catalog_synonyms"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_name: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("ix_cat_syn_user_db", "user_id", "db_id"),)


class CatalogValueMapping(Base):
    __tablename__ = "catalog_value_mappings"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    db_value: Mapped[str] = mapped_column(String, nullable=False)
    business_label: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("ix_cat_val_user_db", "user_id", "db_id"),)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    jti_hash: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class OtpCode(Base):
    __tablename__ = "otp_codes"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String, nullable=False)
    purpose: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (
        UniqueConstraint("user_id", "purpose", name="uq_otp_user_purpose"),
    )
