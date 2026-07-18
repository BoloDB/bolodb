"""Tests for the alembic migration that adds the knowledge tables and the
users.tour_completed column (backend/alembic/versions/0005_add_knowledge_tables.py).

The migration module is loaded directly via importlib (its filename starts
with a digit, so it can't be imported with a normal ``import`` statement),
and ``alembic.op`` is monkeypatched so ``upgrade()``/``downgrade()`` can be
exercised without a real database connection.
"""

import importlib

import pytest

pytest.importorskip("alembic")

from unittest.mock import Mock

MODULE_PATH = "backend.alembic.versions.0005_add_knowledge_tables"

NEW_TABLES = [
    "verified_qas",
    "glossary_terms",
    "catalog_columns",
    "catalog_metrics",
    "catalog_joins",
    "catalog_synonyms",
    "catalog_value_mappings",
]

NEW_INDEXES = [
    ("ix_verified_qa_user_db", "verified_qas"),
    ("ix_glossary_user_db", "glossary_terms"),
    ("ix_cat_col_user_db", "catalog_columns"),
    ("ix_cat_met_user_db", "catalog_metrics"),
    ("ix_cat_join_user_db", "catalog_joins"),
    ("ix_cat_syn_user_db", "catalog_synonyms"),
    ("ix_cat_val_user_db", "catalog_value_mappings"),
]


@pytest.fixture
def migration():
    return importlib.import_module(MODULE_PATH)


@pytest.fixture
def fake_op(monkeypatch, migration):
    op = Mock()
    monkeypatch.setattr(migration, "op", op)
    return op


def test_revision_metadata(migration):
    assert migration.revision == "0005"
    assert migration.down_revision == "0004"


def test_upgrade_adds_tour_completed_column(fake_op, migration):
    migration.upgrade()

    add_column_calls = fake_op.add_column.call_args_list
    assert len(add_column_calls) == 1
    table_name, column = add_column_calls[0][0]
    assert table_name == "users"
    assert column.name == "tour_completed"
    assert column.nullable is False


def test_upgrade_creates_all_new_tables(fake_op, migration):
    migration.upgrade()

    created = [call.args[0] for call in fake_op.create_table.call_args_list]
    assert created == NEW_TABLES


def test_upgrade_creates_all_composite_indexes_on_user_and_db(fake_op, migration):
    migration.upgrade()

    created = [
        (call.args[0], call.args[1], call.args[2])
        for call in fake_op.create_index.call_args_list
    ]
    for (name, table), (created_name, created_table, cols) in zip(NEW_INDEXES, created):
        assert created_name == name
        assert created_table == table
        assert cols == ["user_id", "db_id"]
    assert len(created) == len(NEW_INDEXES)


def test_upgrade_creates_one_index_per_new_table(fake_op, migration):
    migration.upgrade()

    indexed_tables = {call.args[1] for call in fake_op.create_index.call_args_list}
    assert indexed_tables == set(NEW_TABLES)


def test_downgrade_drops_new_tables_in_reverse_order(fake_op, migration):
    migration.downgrade()

    dropped_tables = [call.args[0] for call in fake_op.drop_table.call_args_list]
    assert dropped_tables == list(reversed(NEW_TABLES))


def test_downgrade_drops_tour_completed_column(fake_op, migration):
    migration.downgrade()

    fake_op.drop_column.assert_called_once_with("users", "tour_completed")


def test_downgrade_drops_column_after_all_tables(fake_op, migration):
    """The users.tour_completed column has no FK dependency on the new
    tables, but downgrade should still finish table cleanup first."""
    migration.downgrade()

    # Calls to any child of `fake_op` (drop_table, drop_column, ...) are
    # automatically recorded on fake_op.mock_calls in chronological order.
    call_names = [c[0] for c in fake_op.mock_calls]
    assert call_names[-1] == "drop_column"
    assert call_names[0] == "drop_constraint"
    assert call_names[1:-1] == ["drop_table"] * len(NEW_TABLES)
