"""Tests for the read-only execution guard and helpers in app.database."""

import pytest
from backend.app.database import DatabaseManager, sanitize_url, db_id_for


@pytest.fixture
def db():
    mgr = DatabaseManager(readonly=True, max_rows=5)
    result = mgr.connect("sqlite:///:memory:")
    assert result["ok"]
    from sqlalchemy import text

    with mgr.engine.connect() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        for i in range(8):
            conn.execute(text("INSERT INTO items(name) VALUES (:n)"), {"n": f"item{i}"})
        conn.commit()
    return mgr


def test_select_allowed(db):
    res = db.execute("SELECT * FROM items")
    assert "error" not in res
    assert res["columns"] == ["id", "name"]


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO items(name) VALUES ('x')",
        "UPDATE items SET name='x' WHERE id=1",
        "DELETE FROM items WHERE id=1",
        "DROP TABLE items",
        "ALTER TABLE items ADD COLUMN extra TEXT",
        "CREATE TABLE other (id INTEGER)",
    ],
)
def test_write_statements_rejected(db, sql):
    res = db.execute(sql)
    assert "error" in res


def test_stacked_statement_rejected(db):
    res = db.execute("SELECT * FROM items\nDROP TABLE items")
    assert "error" in res


def test_data_modifying_cte_rejected(db):
    res = db.execute("WITH gone AS (DELETE FROM items RETURNING *) SELECT * FROM gone")
    assert "error" in res


def test_select_into_rejected(db):
    res = db.execute("SELECT * INTO backup FROM items")
    assert "error" in res


def test_pragma_rejected(db):
    res = db.execute("PRAGMA table_info(items)")
    assert "error" in res


def test_keyword_inside_identifier_is_not_blocked(db):
    """Column/table names that merely contain a write keyword must still work."""
    from sqlalchemy import text

    with db.engine.connect() as conn:
        conn.execute(
            text("CREATE TABLE updates_log (id INTEGER PRIMARY KEY, created_at TEXT)")
        )
        conn.commit()
    res = db.execute("SELECT created_at FROM updates_log")
    assert "error" not in res


def test_keyword_inside_string_literal_is_not_blocked(db):
    """A write keyword inside a string literal must not cause a false rejection.

    The AST guard inspects the parse tree, so 'DELETE' as data is allowed where a
    naive keyword regex would have wrongly blocked the whole query.
    """
    res = db.execute("SELECT * FROM items WHERE name = 'please DELETE this later'")
    assert "error" not in res


def test_explain_select_allowed(db):
    res = db.execute("EXPLAIN SELECT * FROM items")
    assert "error" not in res


def test_truncation_flag_is_exact(db):
    res = db.execute("SELECT * FROM items LIMIT 5")
    assert res["row_count"] == 5
    assert res["truncated"] is False

    res = db.execute("SELECT * FROM items")
    assert res["row_count"] == 5
    assert res["truncated"] is True


@pytest.mark.parametrize(
    "url,expected",
    [
        ("postgresql://user:secret@host:5432/db", "postgresql://user:***@host:5432/db"),
        ("sqlite:///C:/path/to/file.db", "sqlite:///C:/path/to/file.db"),
        ("postgresql://user@host/db", "postgresql://user:***@host/db"),
        ("postgresql://:password@host/db", "postgresql://:***@host/db"),
        ("postgresql://user:pass:word@host/db", "postgresql://user:***@host/db"),
        ("just_a_string", "just_a_string"),
    ],
)
def test_sanitize_url_masks_password(url, expected):
    assert sanitize_url(url) == expected


def test_db_id_is_stable_and_ignores_password():
    # db_id is derived from the sanitized URL, so the password isn't part of identity
    a = db_id_for("postgresql://user:secret@host/db")
    b = db_id_for("postgresql://user:other@host/db")
    assert a == b
    assert a == db_id_for("postgresql://user:secret@host/db")


def test_db_id_differs_for_different_targets():
    a = db_id_for("postgresql://user:secret@host/db")
    b = db_id_for("postgresql://user:secret@otherhost/db")
    assert a != b


def test_q_escapes_embedded_quotes(db):
    assert db._q("normal_table") == '"normal_table"'
    assert db._q('bad"table') == '"bad""table"'
    db.dialect = "mysql"
    assert db._q("normal_table") == "`normal_table`"
    assert db._q("bad`table") == "`bad``table`"
    db.dialect = "sqlite"  # restore
