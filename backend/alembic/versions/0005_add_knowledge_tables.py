"""add knowledge tables and tour_completed

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-17 19:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("tour_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "verified_qas",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sql", sa.Text(), nullable=False, server_default=""),
        sa.Column("restatement", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_verified_qa_user_db", "verified_qas", ["user_id", "db_id"])

    op.create_table(
        "glossary_terms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("maps_to", sa.String(), nullable=False),
        sa.Column("sql_hint", sa.String(), nullable=False, server_default=""),
    )
    op.create_index("ix_glossary_user_db", "glossary_terms", ["user_id", "db_id"])

    op.create_table(
        "catalog_columns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("column_name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )
    op.create_index("ix_cat_col_user_db", "catalog_columns", ["user_id", "db_id"])

    op.create_table(
        "catalog_metrics",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("sql_expression", sa.Text(), nullable=False),
    )
    op.create_index("ix_cat_met_user_db", "catalog_metrics", ["user_id", "db_id"])

    op.create_table(
        "catalog_joins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("tables", sa.String(), nullable=False),
        sa.Column("join_condition", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_cat_join_user_db", "catalog_joins", ["user_id", "db_id"])

    op.create_table(
        "catalog_synonyms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("term", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("entity_name", sa.String(), nullable=False),
    )
    op.create_index("ix_cat_syn_user_db", "catalog_synonyms", ["user_id", "db_id"])

    op.create_table(
        "catalog_value_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("db_id", sa.String(), nullable=False),
        sa.Column("table_name", sa.String(), nullable=False),
        sa.Column("column_name", sa.String(), nullable=False),
        sa.Column("db_value", sa.String(), nullable=False),
        sa.Column("business_label", sa.String(), nullable=False),
    )
    op.create_index("ix_cat_val_user_db", "catalog_value_mappings", ["user_id", "db_id"])


def downgrade() -> None:
    op.drop_table("catalog_value_mappings")
    op.drop_table("catalog_synonyms")
    op.drop_table("catalog_joins")
    op.drop_table("catalog_metrics")
    op.drop_table("catalog_columns")
    op.drop_table("glossary_terms")
    op.drop_table("verified_qas")
    op.drop_column("users", "tour_completed")
