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


def test_db_id_is_hashed_before_normalisation():
    """db_id is persisted — a workspace's glossary, verified queries and
    catalog all hang off it — so it must not move when normalisation changes.
    Here the scheme is normalised (SQLITE -> sqlite) on the way to
    create_engine while the identity stays with what the caller passed in."""
    mgr = DatabaseManager(readonly=True)
    typed = "SQLITE:///:memory:"
    result = mgr.connect(TEST_USER, typed)
    assert result["ok"]
    assert result["db_id"] == db_id_for(typed)
    # The engine still got a scheme SQLAlchemy can actually load.
    assert mgr._connections[(TEST_USER, result["db_id"])]["url"].startswith("sqlite:")


def test_db_id_is_hashed_after_the_docker_host_rewrite(monkeypatch, tmp_path):
    """The other half of where that line sits, and the half that predates this
    change: containerised deployments have always had their identity hashed
    from the rewritten host, so hashing the caller's URL instead would move
    db_id for every one of them that ever connected to localhost."""
    monkeypatch.setenv("RUNNING_IN_DOCKER", "true")
    mgr = DatabaseManager(readonly=True)
    typed = f"sqlite:///{tmp_path}/localhost.db"
    rewritten = typed.replace("localhost", "host.docker.internal")

    result = mgr.connect(TEST_USER, typed)
    assert result["ok"]
    assert result["db_id"] == db_id_for(rewritten)
    assert result["db_id"] != db_id_for(typed)


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


def test_q_uses_the_named_connections_dialect(db, tmp_path):
    """A workspace can hold several databases of different types. Without a
    db_id, quoting falls back to whichever connected first, so an Oracle table
    would come back wrapped in the first connection's quote character."""
    second = db.connect(TEST_USER, f"sqlite:///{tmp_path / 'other.db'}")
    assert second["ok"]
    other_id = second["db_id"]
    db._connections[(TEST_USER, other_id)]["dialect"] = "oracle"

    assert db._q(TEST_USER, "employees", other_id) == '"EMPLOYEES"'
    # The first connection is untouched and still quotes for itself.
    assert db._q(TEST_USER, "employees") == '"employees"'


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


@pytest.mark.parametrize(
    "url",
    [
        # The target rides in a query parameter, so urlparse reports no
        # hostname at all and every host check above passes vacuously — but
        # SQLAlchemy hands the parameter straight to the driver.
        "oracle+oracledb://user:pass@/?dsn=127.0.0.1:1521/xe",
        "oracle+oracledb://user:pass@/?dsn=169.254.169.254:1521/xe",
        # Same trick with a full connect descriptor in place of the host.
        (
            "oracle+oracledb://user:pass@"
            "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)(HOST=127.0.0.1)(PORT=1521)))/"
        ),
        # A bare TNS alias: with no service_name or SID, SQLAlchemy stops
        # building a host:port DSN and passes the host through as one.
        "oracle+oracledb://user:pass@SOMEALIAS",
    ],
)
def test_validate_db_url_rejects_oracle_dsn_style_targets(url):
    """The host field is not the only place an Oracle URL can name a target."""
    with pytest.raises(ValueError):
        _validate_db_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:pass@/db",
        "mysql://user:pass@/db",
    ],
)
def test_validate_db_url_requires_a_host(url):
    """Without a host the driver falls back to a local socket."""
    with pytest.raises(ValueError, match="hostname is required"):
        _validate_db_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:pass@127.0.0.2:5432/db",
        "postgresql://user:pass@[::1]:5432/db",
    ],
)
def test_validate_db_url_rejects_every_loopback_address(url):
    """The blocklist only names 127.0.0.1; the rest of the range is caught by
    the IP check, which used to raise inside its own except ValueError."""
    with pytest.raises(ValueError, match="loopback"):
        _validate_db_url(url)


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
        (
            "MERGE INTO employees e USING staging s ON (e.id = s.id) "
            "WHEN MATCHED THEN UPDATE SET e.salary = s.salary"
        ),
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


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg2://scott:tiger@h:5432/db",
        "postgres+psycopg2://scott:tiger@h:5432/db",
        "mysql+pymysql://scott:tiger@h:3306/db",
        "mssql+pyodbc://scott:tiger@h:1433/db",
        "oracle+oracledb://scott:tiger@h:1521/XE",
        # Validation lower-cases the scheme before checking it, so an
        # upper-case one reaches the connection layer too.
        "POSTGRESQL+PSYCOPG2://scott:tiger@h:5432/db",
        "MySQL://scott:tiger@h:3306/db",
    ],
)
def test_credentials_are_redacted_whatever_driver_the_url_names(url):
    """A URL reaches the driver in its canonical, driver-suffixed form, so that
    is the form an exception quotes back — a pattern anchored on the bare
    scheme walks straight past the password in it."""
    msg = _sanitize_db_error(f"could not connect: {url}")
    assert "tiger" not in msg
    assert "scott" not in msg
