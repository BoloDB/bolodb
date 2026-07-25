"""create slack_installations

Revision ID: f7a2c1934d80
Revises: a1f2c3d4e5b6
Create Date: 2026-07-26 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "f7a2c1934d80"
down_revision: Union[str, None] = "a1f2c3d4e5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "slack_installations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("team_id", sa.String(), nullable=False),
        sa.Column("team_name", sa.String(), nullable=False),
        sa.Column("bot_token", sa.String(), nullable=False),
        sa.Column("bot_user_id", sa.String(), nullable=False),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scopes", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("team_id", name="uq_slack_installations_team_id"),
    )
    op.create_index(
        "ix_slack_installations_workspace_id",
        "slack_installations",
        ["workspace_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_slack_installations_workspace_id", table_name="slack_installations"
    )
    op.drop_table("slack_installations")
