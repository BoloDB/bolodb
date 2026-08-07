"""Add a wrong-guess counter to otp_codes

Revision ID: d4c8b17e6a20
Revises: f7a2c1934d80
Create Date: 2026-08-05 17:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d4c8b17e6a20"
down_revision: Union[str, None] = "f7a2c1934d80"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default so the column can be NOT NULL over rows that already exist;
    # dropped straight after so the application default is the only writer and a
    # future insert cannot quietly rely on the database filling it in.
    op.add_column(
        "otp_codes",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("otp_codes", "attempts", server_default=None)


def downgrade() -> None:
    op.drop_column("otp_codes", "attempts")
