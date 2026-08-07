"""create scheduled_queries and schedule_runs

Backs the scheduled reports feature: a workspace-scoped SQL statement that
re-runs on a cron schedule and emails its results, plus a row per execution so
the UI can show why a report did or didn't arrive.

Also merges the two heads left behind by the token-version and OTP-attempt
migrations, which were authored in parallel off the same parent. Both only add
a column, to different tables, so they carry no ordering between them — this
revision just rejoins them so ``upgrade head`` resolves to one revision again.

Revision ID: d5c8b41a97e2
Revises: a7f3e91c4b58, d4c8b17e6a20
Create Date: 2026-08-01 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d5c8b41a97e2"
down_revision: Union[str, Sequence[str], None] = ("a7f3e91c4b58", "d4c8b17e6a20")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_queries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("sql", sa.Text(), nullable=False),
        sa.Column("database_id", sa.String(), nullable=True),
        sa.Column("cron", sa.String(length=120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "recipients",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("subject_template", sa.String(length=300), nullable=True),
        sa.Column("intro", sa.Text(), nullable=True),
        sa.Column("footer", sa.Text(), nullable=True),
        sa.Column(
            "display_columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column("max_rows", sa.Integer(), nullable=False, server_default="50"),
        sa.Column(
            "attach_csv", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "send_condition",
            sa.String(length=20),
            nullable=False,
            server_default="always",
        ),
        sa.Column("condition_value", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(length=20), nullable=True),
        sa.Column(
            "consecutive_failures", sa.Integer(), nullable=False, server_default="0"
        ),
        # NOT NULL to match the model's Mapped[datetime]. The ORM always fills
        # these from _utcnow; the server_default is the backstop so a raw insert
        # can't trip the constraint.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "send_condition IN ('always','non_empty','row_count_gte','row_count_lte')",
            name="ck_scheduled_queries_send_condition",
        ),
        sa.CheckConstraint(
            "max_rows > 0 AND max_rows <= 500",
            name="ck_scheduled_queries_max_rows",
        ),
    )
    # The scheduler polls "active and due" every tick; this is that lookup.
    op.create_index(
        "ix_scheduled_queries_due",
        "scheduled_queries",
        ["is_active", "next_run_at"],
        unique=False,
    )
    op.create_index(
        "ix_scheduled_queries_workspace",
        "scheduled_queries",
        ["workspace_id"],
        unique=False,
    )

    op.create_table(
        "schedule_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scheduled_queries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column(
            "delivered_to", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "manual", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.CheckConstraint(
            "status IN ('success','failed','skipped')",
            name="ck_schedule_runs_status",
        ),
    )
    op.create_index(
        "ix_schedule_runs_schedule_started",
        "schedule_runs",
        ["schedule_id", "started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_schedule_runs_schedule_started", table_name="schedule_runs")
    op.drop_table("schedule_runs")
    op.drop_index("ix_scheduled_queries_workspace", table_name="scheduled_queries")
    op.drop_index("ix_scheduled_queries_due", table_name="scheduled_queries")
    op.drop_table("scheduled_queries")
