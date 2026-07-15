"""Add supabase_id column to users table

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-15
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("supabase_id", sa.String(), nullable=True, unique=True),
    )
    op.create_index("ix_users_supabase_id", "users", ["supabase_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_supabase_id", table_name="users")
    op.drop_column("users", "supabase_id")
