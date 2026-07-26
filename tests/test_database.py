"""Tests for the read-only execution guard and helpers in app.database."""

import pytest
from backend.app.database import (
    DatabaseManager,
    _sanitize_db_error,
    _validate_db_url,
    db_id_for,
    sanitize_url,
)

TEST_USER = "test-user-123"


@pytest.fixture
def db():
    mgr = DatabaseManager(readonly=True, max_rows=5)
    result = mgr.connect(TEST_USER, "sqlite:///:memory:")
    assert result["ok"]
    from sqlalchemy import text

    with mgr._connections[TEST_USER]["engine"].connect() as conn:
        conn.execute(text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        for i in range(8):
            conn.execute(text("INSERT INTO items(name) VALUES (:n)"), {"n": f"item{i}"})
        conn.commit()
    return mgr


def test_select_allowed(db):
    res = db.execute(TEST_USER, "SELECT * FROM items")
    assert "error" not in res
    assert res["columns"] == ["id", "name"]


def test_cross_user_isolation(db):
    user_a = TEST_USER
    user_b = "test-user-456"

    # user_a is already connected via the db fixture. Connect user_b.
    res_b = db.connect(user_b, "sqlite:///:memory:")
    assert res_b["ok"]

    from sqlalchemy import text

    with db._connections[user_b]["engine"].connect() as conn:
        conn.execute(text("CREATE TABLE b_items (id INTEGER PRIMARY KEY, b_name TEXT)"))
        conn.execute(text("INSERT INTO b_items(b_name) VALUES ('B')"))
        conn.commit()

    # Verify execution isolation
    res_a = db.execute(user_a, "SELECT * FROM items")
    assert "error" not in res_a
    assert res_a["row_count"] == 5
    assert res_a["truncated"] is True

    res_b_exec = db.execute(user_b, "SELECT * FROM b_items")
    assert "error" not in res_b_exec
    assert res_b_exec["row_count"] == 1

    # Cross query should fail
    assert "error" in db.execute(user_a, "SELECT * FROM b_items")
    assert "error" in db.execute(user_b, "SELECT * FROM items")

    # Verify dialect isolation
    assert db.get_dialect(user_a) == "sqlite"
    assert db.get_dialect(user_b) == "sqlite"

    db._connections[user_a]["dialect"] = "mysql"
    assert db.get_dialect(user_a) == "mysql"
    assert db.get_dialect(user_b) == "sqlite"
    db._connections[user_a]["dialect"] = "sqlite"  # revert

    # Verify disconnect isolation
    db.disconnect(user_a)
    assert not db.connected(user_a)
    assert db.connected(user_b)


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
    res = db.execute(TEST_USER, sql)
    assert "error" in res


def test_stacked_statement_rejected(db):
    res = db.execute(TEST_USER, "SELECT * FROM items\nDROP TABLE items")
    assert "error" in res


def test_data_modifying_cte_rejected(db):
    res = db.execute(
        TEST_USER, "WITH gone AS (DELETE FROM items RETURNING *) SELECT * FROM gone"
    )
    assert "error" in res


def test_select_into_rejected(db):
    res = db.execute(TEST_USER, "SELECT * INTO backup FROM items")
    assert "error" in res


def test_pragma_rejected(db):
    res = db.execute(TEST_USER, "PRAGMA table_info(items)")
    assert "error" in res


def test_keyword_inside_identifier_is_not_blocked(db):
    """Column/table names that merely contain a write keyword must still work."""
    from sqlalchemy import text

    with db._connections[TEST_USER]["engine"].connect() as conn:
        conn.execute(
            text("CREATE TABLE updates_log (id INTEGER PRIMARY KEY, created_at TEXT)")
        )
        conn.commit()
    res = db.execute(TEST_USER, "SELECT created_at FROM updates_log")
    assert "error" not in res


def test_keyword_inside_string_literal_is_not_blocked(db):
    """A write keyword inside a string literal must not cause a false rejection.

    The AST guard inspects the parse tree, so 'DELETE' as data is allowed where a
    naive keyword regex would have wrongly blocked the whole query.
    """
    res = db.execute(
        TEST_USER, "SELECT * FROM items WHERE name = 'please DELETE this later'"
    )
    assert "error" not in res


def test_explain_select_allowed(db):
    res = db.execute(TEST_USER, "EXPLAIN SELECT * FROM items")
    assert "error" not in res


def test_truncation_flag_is_exact(db):
    res = db.execute(TEST_USER, "SELECT * FROM items LIMIT 5")
    assert res["row_count"] == 5
    assert res["truncated"] is False

    res = db.execute(TEST_USER, "SELECT * FROM items")
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
    assert db._q(TEST_USER, "normal_table") == '"normal_table"'
    assert db._q(TEST_USER, 'bad"table') == '"bad""table"'
    db._connections[TEST_USER]["dialect"] = "mysql"
    assert db._q(TEST_USER, "normal_table") == "`normal_table`"
    assert db._q(TEST_USER, "bad`table") == "`bad``table`"
    db._connections[TEST_USER]["dialect"] = "sqlite"  # restore


def test_q_uppercases_oracle_identifiers(db):
    """SQLAlchemy lower-cases the upper-case names Oracle actually stores, so a
    reflected name quoted verbatim would not resolve."""
    db._connections[TEST_USER]["dialect"] = "oracle"
    assert db._q(TEST_USER, "employees") == '"EMPLOYEES"'
    assert db._q(TEST_USER, "MixedCase") == '"MixedCase"'
    db._connections[TEST_USER]["dialect"] = "sqlite"  # restore


# --- URL validation ---------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "oracle+oracledb://user:pass@db.example.com:1521/?service_name=ORCLPDB1",
        "oracle://user:pass@db.example.com:1521/XEPDB1",
        "postgresql://user:pass@db.example.com:5432/db",
    ],
)
def test_validate_db_url_accepts_supported_schemes(url):
    assert _validate_db_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "oracle+oracledb://user:pass@127.0.0.1:1521/?service_name=X",
        "oracle+oracledb://user:pass@localhost:1521/?service_name=X",
        "oracle+oracledb://user:pass@169.254.169.254:1521/?service_name=X",
    ],
)
def test_validate_db_url_applies_ssrf_guard_to_oracle(url):
    """The driver suffix must not let a URL slip past the host checks."""
    with pytest.raises(ValueError):
        _validate_db_url(url)


def test_validate_db_url_rejects_unsupported_scheme():
    with pytest.raises(ValueError, match="Unsupported database scheme"):
        _validate_db_url("snowflake://user:pass@account/db")


# --- Oracle read-only guard -------------------------------------------------


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM employees FETCH FIRST 10 ROWS ONLY",
        "SELECT NVL(salary, 0) FROM employees",
        "SELECT * FROM employees WHERE hired > TRUNC(SYSDATE) - 30",
        "SELECT TO_CHAR(hired, 'YYYY-MM') m, COUNT(*) FROM employees GROUP BY TO_CHAR(hired, 'YYYY-MM')",
    ],
)
def test_oracle_selects_allowed(db, sql):
    db._connections[TEST_USER]["dialect"] = "oracle"
    try:
        assert db._readonly_violation(TEST_USER, sql) is None
    finally:
        db._connections[TEST_USER]["dialect"] = "sqlite"


@pytest.mark.parametrize(
    "sql",
    [
        "MERGE INTO employees e USING staging s ON (e.id = s.id) "
        "WHEN MATCHED THEN UPDATE SET e.salary = s.salary",
        "INSERT INTO employees (id) VALUES (1)",
        "DELETE FROM employees",
        "TRUNCATE TABLE employees",
        "CREATE TABLE backup AS SELECT * FROM employees",
        "SELECT * INTO backup FROM employees",
        "BEGIN NULL; END;",
    ],
)
def test_oracle_writes_rejected(db, sql):
    db._connections[TEST_USER]["dialect"] = "oracle"
    try:
        assert db._readonly_violation(TEST_USER, sql) is not None
    finally:
        db._connections[TEST_USER]["dialect"] = "sqlite"


def test_oracle_errors_are_sanitized():
    msg = _sanitize_db_error(
        "DPY-6005: cannot connect to database "
        "(CONNECTION_ID=x). oracle+oracledb://scott:tiger@10.0.0.4:1521/?service_name=PROD"
    )
    assert "tiger" not in msg
    assert "PROD" not in msg
