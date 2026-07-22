import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, UniqueConstraint, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, _utcnow, _uuid7


class VerifiedQA(Base):
    __tablename__ = "verified_qas"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    restatement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "db_id", "question", name="uq_verified_qa_user_db_question"
        ),
        Index("ix_verified_qa_user_db", "workspace_id", "db_id"),
    )


class Glossary(Base):
    __tablename__ = "glossary_terms"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    maps_to: Mapped[str] = mapped_column(String, nullable=False)
    sql_hint: Mapped[str] = mapped_column(String, nullable=False, default="")
    __table_args__ = (Index("ix_glossary_user_db", "workspace_id", "db_id"),)


class CatalogColumn(Base):
    __tablename__ = "catalog_columns"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_cat_col_user_db", "workspace_id", "db_id"),)


class CatalogMetric(Base):
    __tablename__ = "catalog_metrics"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql_expression: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_cat_met_user_db", "workspace_id", "db_id"),)


class CatalogJoin(Base):
    __tablename__ = "catalog_joins"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    tables: Mapped[str] = mapped_column(String, nullable=False)
    join_condition: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (Index("ix_cat_join_user_db", "workspace_id", "db_id"),)


class CatalogSynonym(Base):
    __tablename__ = "catalog_synonyms"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_name: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("ix_cat_syn_user_db", "workspace_id", "db_id"),)


class CatalogValueMapping(Base):
    __tablename__ = "catalog_value_mappings"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    db_value: Mapped[str] = mapped_column(String, nullable=False)
    business_label: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("ix_cat_val_user_db", "workspace_id", "db_id"),)
