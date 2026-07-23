"""Add chart spec to query history

Revision ID: c1a4d7e29b58
Revises: b83664841390
Create Date: 2026-07-23 14:10:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "c1a4d7e29b58"
down_revision: Union[str, None] = "b83664841390"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: turns recorded before the model started choosing a chart have
    # none, and the UI falls back to its own heuristic for those.
    op.add_column(
        "query_history",
        sa.Column("chart", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("query_history", "chart")
