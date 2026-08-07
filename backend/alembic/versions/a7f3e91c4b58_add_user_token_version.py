"""Add users.token_version so sessions can be revoked

Revision ID: a7f3e91c4b58
Revises: f7a2c1934d80
Create Date: 2026-08-05 17:45:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a7f3e91c4b58"
down_revision: Union[str, None] = "f7a2c1934d80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Everyone starts at 0, which is also what a token missing the claim is read
    # as — so this migration revokes nothing on its own. Only a password change
    # or reset raises it.
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("users", "token_version", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "token_version")
