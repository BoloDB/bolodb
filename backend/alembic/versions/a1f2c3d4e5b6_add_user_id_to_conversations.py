"""Add user_id to conversations (user + workspace scoping)

Conversations become private to the user that created them, scoped within their
workspace. Existing conversations were workspace-shared and have no owner, so
they are cleared out (along with their query_history turns) before the NOT NULL
owner column is added.

Revision ID: a1f2c3d4e5b6
Revises: e8f901a23b4c
Create Date: 2026-07-24 00:00:00.000000
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1f2c3d4e5b6"
down_revision: Union[str, None] = "e8f901a23b4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Legacy conversations were workspace-shared with no owner; there is no
    # correct user to attribute them to, so clear them (and their turns) before
    # adding the NOT NULL owner column.
    op.execute("DELETE FROM query_history WHERE conversation_id IS NOT NULL")
    op.execute("DELETE FROM conversations")

    op.add_column(
        "conversations",
        sa.Column("user_id", sa.UUID(), nullable=False),
    )
    op.create_foreign_key(
        "fk_conversations_user_id_users",
        "conversations",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # Swap the list index to include the owner: the list query filters by
    # (workspace_id, user_id) and orders by updated_at. Use IF EXISTS/IF NOT
    # EXISTS so the swap is resilient to databases where the old index was
    # never created (older initial-schema revisions did not have it).
    op.execute("DROP INDEX IF EXISTS ix_conversations_workspace_updated")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_workspace_user_updated "
        "ON conversations (workspace_id, user_id, updated_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_conversations_workspace_user_updated")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_conversations_workspace_updated "
        "ON conversations (workspace_id, updated_at)"
    )
    op.drop_constraint(
        "fk_conversations_user_id_users", "conversations", type_="foreignkey"
    )
    op.drop_column("conversations", "user_id")
