import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base, _utcnow, _uuid7

# Delivery gating. "always" mails every run; the rest let a schedule behave as an
# alert that stays quiet until the data says otherwise.
SEND_CONDITIONS = ("always", "non_empty", "row_count_gte", "row_count_lte")

RUN_STATUSES = ("success", "failed", "skipped")

# Ceiling on rows rendered inline in the email body. The full result still goes
# out in the CSV attachment when one is requested — this only bounds the HTML,
# which mail clients start truncating well before this anyway.
MAX_INLINE_ROWS = 500


class ScheduledQuery(Base):
    """A saved SQL statement that re-runs on a cron schedule and emails results.

    The SQL is frozen at creation and executed verbatim on every run: a report
    that quietly rewrote itself against a drifting schema would be worse than one
    that fails loudly. ``question`` is kept only so the UI can show what was
    originally asked.

    Scoped to a workspace like saved queries and dashboards, so a schedule
    outlives the member who set it up (``created_by`` is SET NULL on user
    deletion). Times are UTC throughout.
    """

    __tablename__ = "scheduled_queries"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    question: Mapped[str | None] = mapped_column(Text, nullable=True)
    sql: Mapped[str] = mapped_column(Text, nullable=False)
    # The db_id the SQL was written against, matching SavedQuery.database_id.
    database_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # ── When it runs ────────────────────────────────────────────────
    cron: Mapped[str] = mapped_column(String(120), nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── What gets delivered ─────────────────────────────────────────
    recipients: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Supports {{name}}, {{date}}, {{time}}, {{row_count}} and {{workspace}}.
    subject_template: Mapped[str | None] = mapped_column(String(300), nullable=True)
    intro: Mapped[str | None] = mapped_column(Text, nullable=True)
    footer: Mapped[str | None] = mapped_column(Text, nullable=True)
    # null means "every column, in the order the query returned them".
    display_columns: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    max_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    attach_csv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    send_condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="always"
    )
    condition_value: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Bookkeeping the scheduler owns ──────────────────────────────
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "send_condition IN ('always','non_empty','row_count_gte','row_count_lte')",
            name="ck_scheduled_queries_send_condition",
        ),
        CheckConstraint(
            "max_rows > 0 AND max_rows <= 500",
            name="ck_scheduled_queries_max_rows",
        ),
        # The scheduler's hot path: "active schedules that are due".
        Index("ix_scheduled_queries_due", "is_active", "next_run_at"),
        Index("ix_scheduled_queries_workspace", "workspace_id"),
    )


class ScheduleRun(Base):
    """One execution of a ScheduledQuery — the execution history.

    Written for every attempt including skips, so "why didn't I get an email?"
    always has an answer on the schedule's history tab.
    """

    __tablename__ = "schedule_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("scheduled_queries.id", ondelete="CASCADE"),
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Populated on failure, and on skips to say which condition held it back.
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Addresses the mail provider actually accepted, so a partial delivery is
    # visible rather than being flattened into "success".
    delivered_to: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # True when this run was started from "Run now" rather than by the cron tick.
    manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint(
            "status IN ('success','failed','skipped')",
            name="ck_schedule_runs_status",
        ),
        Index("ix_schedule_runs_schedule_started", "schedule_id", "started_at"),
    )
