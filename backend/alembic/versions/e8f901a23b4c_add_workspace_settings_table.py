"""add_workspace_settings_table

Revision ID: e8f901a23b4c
Revises: c1a4d7e29b58
Create Date: 2026-07-23 18:30:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e8f901a23b4c"
down_revision: Union[str, None] = "c1a4d7e29b58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workspace_settings",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column(
            "default_invite_role",
            sa.String(length=20),
            server_default="member",
            nullable=False,
        ),
        sa.Column(
            "invite_expiry_days",
            sa.Integer(),
            server_default="7",
            nullable=False,
        ),
        sa.Column(
            "activity_retention_days",
            sa.Integer(),
            server_default="30",
            nullable=False,
        ),
        sa.Column(
            "role_permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("workspace_id"),
    )


def downgrade() -> None:
    op.drop_table("workspace_settings")
