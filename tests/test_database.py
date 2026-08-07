"""Tests for the read-only execution guard and helpers in app.database."""

import base64

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


# Every rejection the read-only guard itself can produce. Tests assert against
# this set rather than merely "an error happened": SQLite rejects some of the
# statements below on its own syntax grounds, so a bare `"error" in res` would
# still pass if the guard had waved the statement through and the database
# happened to refuse it. Only these messages prove the guard is what stopped it.
READONLY_GUARD_ERRORS = {
    "Only SELECT queries are allowed (read-only mode).",
    "Only read-only SELECT queries are allowed.",
    "Only one statement is allowed (no stacked queries).",
    "SELECT INTO is not allowed.",
    "Empty statement.",
}


def test_explain_analyze_delete_does_not_delete(db):
    """EXPLAIN ANALYZE runs the statement it is given — it must not be a way in.

    sqlglot keeps everything after EXPLAIN as one opaque string, so the guard
    used to see a bare Command with no DELETE node in it and wave the whole
    thing through. On Postgres and MySQL that executes the DELETE for real.
    """
    res = db.execute(TEST_USER, "EXPLAIN ANALYZE DELETE FROM items")
    assert res.get("error") in READONLY_GUARD_ERRORS
    # The rows are the actual claim; the error message alone would still hold if
    # the statement had run and then failed on something else.
    assert db.execute(TEST_USER, "SELECT COUNT(*) AS n FROM items")["rows"][0]["n"] == 8


@pytest.mark.parametrize(
    "sql",
    [
        "EXPLAIN ANALYZE DELETE FROM items",
        "EXPLAIN ANALYZE UPDATE items SET name = 'x'",
        "EXPLAIN ANALYZE INSERT INTO items(name) VALUES ('x')",
        "EXPLAIN (ANALYZE, BUFFERS) DELETE FROM items",
        "EXPLAIN VERBOSE DROP TABLE items",
        "EXPLAIN ANALYZE CREATE TABLE t (id INT)",
        "EXPLAIN ANALYZE TRUNCATE items",
        # Nested past the unwrap limit must fail closed, not fall through.
        "EXPLAIN EXPLAIN EXPLAIN EXPLAIN EXPLAIN DELETE FROM items",
        # An EXPLAIN with nothing to explain tells us nothing — reject it.
        "EXPLAIN",
    ],
)
def test_explain_wrapping_a_write_is_rejected(db, sql):
    assert db.execute(TEST_USER, sql).get("error") in READONLY_GUARD_ERRORS


@pytest.mark.parametrize("dialect", ["postgres", "mysql", "sqlite", "duckdb"])
@pytest.mark.parametrize(
    "sql",
    [
        "EXPLAIN ANALYZE DELETE FROM users",
        "EXPLAIN ANALYZE UPDATE users SET a = 1",
        "EXPLAIN ANALYZE INSERT INTO users VALUES (1)",
    ],
)
def test_explain_write_rejected_on_every_dialect(dialect, sql):
    """The bypass is dialect-independent, so the fix has to be too.

    Checked against the parser directly rather than through a live connection —
    the guard picks its sqlglot dialect from the connection, and there is no
    Postgres or MySQL to connect to in this suite.
    """
    import sqlglot

    from backend.app.database import _statement_violation

    stmts = [s for s in sqlglot.parse(sql, dialect=dialect) if s is not None]
    assert len(stmts) == 1
    assert _statement_violation(stmts[0], dialect) is not None


@pytest.mark.parametrize(
    "dialect,sql",
    [
        ("postgres", "EXPLAIN SELECT * FROM items"),
        ("postgres", "EXPLAIN ANALYZE SELECT * FROM items"),
        ("postgres", "EXPLAIN VERBOSE SELECT 1"),
        ("postgres", "EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM items"),
        ("sqlite", "EXPLAIN QUERY PLAN SELECT * FROM items"),
        ("sqlite", "EXPLAIN SELECT * FROM items"),
        # Snowflake's output-format clause. Unwrapping has to know every
        # dialect's option syntax or it rejects valid read-only plans.
        ("snowflake", "EXPLAIN USING TABULAR SELECT * FROM items"),
        ("snowflake", "EXPLAIN USING JSON SELECT * FROM items"),
        ("snowflake", "EXPLAIN USING TEXT SELECT * FROM items"),
    ],
)
def test_explain_select_still_allowed_after_the_fix(dialect, sql):
    """Reading a plan is the point of the feature — don't regress it."""
    import sqlglot

    from backend.app.database import _statement_violation

    stmts = [s for s in sqlglot.parse(sql, dialect=dialect) if s is not None]
    assert _statement_violation(stmts[0], dialect) is None


@pytest.mark.parametrize(
    "sql",
    [
        "EXPLAIN USING TABULAR DELETE FROM items",
        "EXPLAIN USING JSON UPDATE items SET name = 'x'",
        "EXPLAIN USING TEXT DROP TABLE items",
    ],
)
def test_snowflake_explain_options_do_not_smuggle_a_write(sql):
    """Teaching the unwrapper an option must not turn it into a way past the guard."""
    import sqlglot

    from backend.app.database import _statement_violation

    stmts = [s for s in sqlglot.parse(sql, dialect="snowflake") if s is not None]
    assert _statement_violation(stmts[0], "snowflake") is not None


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
        _validate_db_url("teradata://user:pass@host/db")


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


# --- private and internal addresses -----------------------------------------


@pytest.mark.parametrize(
    "host",
    [
        "10.0.0.5",
        "192.168.1.20",
        "172.16.4.1",
        "172.31.255.254",
        "[fd00::1]",
    ],
)
def test_a_private_address_is_refused_by_default(host):
    """A connection URL is user input. On a shared deployment, letting one
    workspace point it at 10.0.0.5 turns "add a database" into a scan of
    whatever else shares the network."""
    with pytest.raises(ValueError, match="private"):
        _validate_db_url(f"postgresql://user:pass@{host}:5432/db")


@pytest.mark.parametrize("host", ["10.0.0.5", "192.168.1.20"])
def test_a_private_address_is_allowed_when_the_operator_says_so(host, monkeypatch):
    """Self-hosted installs whose database genuinely sits on a LAN. Only the
    operator can know that, which is why it is an env var and not a setting."""
    monkeypatch.setenv("ALLOW_PRIVATE_DB_HOSTS", "true")
    url = f"postgresql://user:pass@{host}:5432/db"
    assert _validate_db_url(url) == url


def test_loopback_stays_blocked_even_when_private_hosts_are_allowed(monkeypatch):
    """The escape hatch is for a LAN, not for reaching back into this server."""
    monkeypatch.setenv("ALLOW_PRIVATE_DB_HOSTS", "true")
    # 127.0.0.2 rather than 127.0.0.1: the latter is caught by name from
    # _BLOCKED_HOSTS, which would pass this test without the IP check running.
    with pytest.raises(ValueError, match="loopback"):
        _validate_db_url("postgresql://user:pass@127.0.0.2:5432/db")


@pytest.mark.parametrize(
    "host",
    [
        # IPv4 wrapped in IPv6 reports none of the flags for the address it
        # actually reaches.
        "[::ffff:127.0.0.1]",
        "[::ffff:10.0.0.5]",
    ],
)
def test_an_ipv4_mapped_address_is_checked_as_the_address_it_reaches(host):
    with pytest.raises(ValueError):
        _validate_db_url(f"postgresql://user:pass@{host}:5432/db")


def test_a_public_address_is_accepted():
    url = "postgresql://user:pass@8.8.8.8:5432/db"
    assert _validate_db_url(url) == url


def test_a_hostname_that_resolves_into_a_private_range_is_refused(monkeypatch):
    """The text of a hostname says nothing about where it points, which is the
    whole SSRF shape: the caller picks the name, the resolver picks the address.
    "10.0.0.5.nip.io" walks past every check that only reads the string."""
    import ipaddress

    monkeypatch.setattr(
        "backend.app.database._resolve_all",
        lambda hostname: [ipaddress.ip_address("10.0.0.5")],
    )
    with pytest.raises(ValueError, match="private"):
        _validate_db_url("postgresql://user:pass@db.example.com:5432/db")


def test_a_hostname_that_resolves_publicly_is_accepted(monkeypatch):
    import ipaddress

    monkeypatch.setattr(
        "backend.app.database._resolve_all",
        lambda hostname: [ipaddress.ip_address("93.184.216.34")],
    )
    url = "postgresql://user:pass@db.example.com:5432/db"
    assert _validate_db_url(url) == url


def test_a_name_that_does_not_resolve_is_left_to_the_driver(monkeypatch):
    """It may resolve from wherever the driver runs but not from here, and
    create_engine is about to give a far better message than this could."""
    monkeypatch.setattr("backend.app.database._resolve_all", lambda hostname: [])
    url = "postgresql://user:pass@nonexistent.invalid:5432/db"
    assert _validate_db_url(url) == url


def test_every_address_a_name_resolves_to_is_checked(monkeypatch):
    """A name with several A records only has to point at one internal address
    for the connection to reach it."""
    import ipaddress

    monkeypatch.setattr(
        "backend.app.database._resolve_all",
        lambda hostname: [
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("169.254.169.254"),
        ],
    )
    with pytest.raises(ValueError):
        _validate_db_url("postgresql://user:pass@db.example.com:5432/db")


def test_resolution_is_skipped_when_private_hosts_are_allowed(monkeypatch):
    """Nothing left for it to reject, so the lookup would be pure latency."""
    monkeypatch.setenv("ALLOW_PRIVATE_DB_HOSTS", "true")

    def explode(hostname):
        raise AssertionError("should not resolve when private hosts are allowed")

    monkeypatch.setattr("backend.app.database._resolve_all", explode)
    url = "postgresql://user:pass@db.example.com:5432/db"
    assert _validate_db_url(url) == url


def test_sqlite_is_not_subjected_to_host_checks(tmp_path):
    """A file path has no host at all."""
    url = f"sqlite:///{tmp_path / 'x.db'}"
    assert _validate_db_url(url) == url


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


# --- warehouse credentials --------------------------------------------------

_KEY_JSON = '{"type":"service_account","private_key":"-----BEGIN PRIVATE KEY-----AAA"}'
_KEY_B64 = base64.b64encode(_KEY_JSON.encode()).decode()
_BQ_URL = f"bigquery://my-project/my_dataset?credentials_base64={_KEY_B64}"


def test_a_service_account_key_never_reaches_the_display_url():
    """A BigQuery URL has no '@' in it, so the password masking never looks at
    it. Left alone the whole key would be written to display_url in clear and
    shown back in the UI."""
    masked = sanitize_url(_BQ_URL)
    assert _KEY_B64 not in masked
    assert "credentials_base64=***" in masked
    # Everything that is not the secret survives — this is still the URL the
    # user has to recognise in a list of connections.
    assert masked.startswith("bigquery://my-project/my_dataset?")


def test_rotating_a_service_account_key_keeps_the_database_identity():
    """db_id is hashed from the sanitized URL, so the key is not part of it.
    Were it otherwise, rotating a key would orphan that database's glossary and
    verified queries."""
    rotated = "bigquery://my-project/my_dataset?credentials_base64=QSBORVcgS0VZ"
    assert db_id_for(_BQ_URL) == db_id_for(rotated)
    # A different dataset is still a different database.
    assert db_id_for(_BQ_URL) != db_id_for(
        f"bigquery://my-project/other?credentials_base64={_KEY_B64}"
    )


def test_a_service_account_key_is_stripped_from_error_messages():
    msg = _sanitize_db_error(f"403 while connecting with {_BQ_URL}")
    assert _KEY_B64 not in msg
    assert "PRIVATE KEY" not in msg


def test_a_bare_credential_parameter_is_stripped_from_error_messages():
    """Some driver errors quote the parameter back on its own, outside a URL."""
    msg = _sanitize_db_error(f"invalid credentials_base64={_KEY_B64} supplied")
    assert _KEY_B64 not in msg


@pytest.mark.parametrize(
    "url",
    [
        "bigquery://proj/ds?credentials_path=/etc/passwd",
        "snowflake://u:p@acct/DB?private_key_file=/root/.ssh/id_rsa",
        "snowflake://u:p@acct/DB?private_key_path=/root/.ssh/id_rsa",
    ],
)
def test_parameters_that_read_server_files_are_refused(url):
    """The validator can check a host; it cannot check what is behind a path on
    this server's own disk."""
    with pytest.raises(ValueError, match="not allowed"):
        _validate_db_url(url)


def test_databricks_without_an_http_path_is_refused_up_front():
    """Better than whatever the driver says when it has no endpoint to dial."""
    with pytest.raises(ValueError, match="http_path"):
        _validate_db_url(
            "databricks://token:t@dbc-a1.cloud.databricks.com?catalog=main"
        )


@pytest.mark.parametrize(
    "url",
    [
        _BQ_URL,
        "bigquery://my-project/my_dataset",
        "snowflake://user:pass@myorg-acct/ANALYTICS/PUBLIC?warehouse=WH&role=R",
        "databricks://token:dapi1@dbc-a1.cloud.databricks.com?http_path=/sql/1.0/w/a",
    ],
)
def test_the_documented_warehouse_urls_are_accepted(url):
    assert _validate_db_url(url) == url


def test_a_missing_warehouse_driver_is_reported_by_name(monkeypatch):
    """These drivers are large enough that a deployment may trim them out; the
    user should learn which one is absent, not read an import traceback."""
    from sqlalchemy.exc import NoSuchModuleError

    def boom(*_a, **_kw):
        raise NoSuchModuleError("Can't load plugin: sqlalchemy.dialects:snowflake")

    monkeypatch.setattr("backend.app.database.create_engine", boom)
    res = DatabaseManager().connect(TEST_USER, "snowflake://u:p@acct/DB")
    assert res["ok"] is False
    assert "snowflake" in res["error"]
    assert "no driver installed" in res["error"].lower()


# --- read-only guard on the warehouse dialects ------------------------------


@pytest.mark.parametrize(
    "dialect,sql",
    [
        # Snowflake's own ways of writing, none of which look like INSERT.
        ("snowflake", "COPY INTO t FROM @my_stage"),
        ("snowflake", "PUT file:///tmp/x @my_stage"),
        (
            "snowflake",
            "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN UPDATE SET t.a = s.a",
        ),
        ("snowflake", "TRUNCATE TABLE t"),
        ("snowflake", "INSERT INTO t VALUES (1)"),
        ("databricks", "MERGE INTO t USING s ON t.id = s.id WHEN MATCHED THEN DELETE"),
        ("databricks", "CREATE TABLE x AS SELECT 1"),
        ("databricks", "DELETE FROM t"),
        # BigQuery spells its clobber CREATE OR REPLACE.
        ("bigquery", "CREATE OR REPLACE TABLE x AS SELECT 1"),
        ("bigquery", "UPDATE t SET a = 1 WHERE TRUE"),
        ("bigquery", "DELETE FROM t WHERE TRUE"),
    ],
)
def test_warehouse_writes_are_rejected(db, dialect, sql):
    db._connections[TEST_USER]["dialect"] = dialect
    try:
        assert db._readonly_violation(TEST_USER, sql) is not None
    finally:
        db._connections[TEST_USER]["dialect"] = "sqlite"


@pytest.mark.parametrize(
    "dialect,sql",
    [
        ("snowflake", "SELECT * FROM t LIMIT 10"),
        # VARIANT colon paths are Snowflake-only syntax; parsing them as generic
        # SQL would reject a perfectly ordinary read.
        ("snowflake", "SELECT col:field FROM t"),
        ("databricks", "SELECT * FROM main.default.t LIMIT 10"),
        ("bigquery", "SELECT * FROM `p.d.t` LIMIT 10"),
        ("bigquery", "SELECT FORMAT_DATE('%Y', d) FROM t"),
    ],
)
def test_warehouse_selects_allowed(db, dialect, sql):
    db._connections[TEST_USER]["dialect"] = dialect
    try:
        assert db._readonly_violation(TEST_USER, sql) is None
    finally:
        db._connections[TEST_USER]["dialect"] = "sqlite"


@pytest.mark.parametrize(
    "name",
    ["credentials_base64", "%63redentials_base64", "credentials%5Fbase64"],
)
def test_an_encoded_parameter_name_still_gets_redacted(name):
    """SQLAlchemy percent-decodes parameter names, so each of these reaches the
    driver as the same credential. Matching the raw text let the encoded
    spellings carry a key straight into display_url."""
    from sqlalchemy.engine import make_url

    url = f"bigquery://my-project/my_dataset?{name}={_KEY_B64}"
    # The premise, asserted rather than assumed: the driver does see it.
    assert "credentials_base64" in make_url(url).query
    assert _KEY_B64 not in sanitize_url(url)


def test_a_differently_cased_parameter_name_is_redacted_too():
    """SQLAlchemy does not case-fold names, so this one is not a credential the
    driver would read — but redacting it costs nothing and the comparison
    should not be the thing that decides a key is safe to display."""
    url = f"bigquery://p/d?CREDENTIALS_BASE64={_KEY_B64}"
    assert _KEY_B64 not in sanitize_url(url)


def test_an_encoded_key_does_not_change_the_database_identity():
    """The redaction is what keeps the secret out of db_id, so a spelling that
    slipped past it would also make rotation orphan the workspace's data."""
    plain = f"bigquery://p/d?credentials_base64={_KEY_B64}"
    encoded = f"bigquery://p/d?credentials%5Fbase64={_KEY_B64}"
    assert db_id_for(encoded) == db_id_for(
        "bigquery://p/d?credentials%5Fbase64=A_DIFFERENT_KEY"
    )
    assert db_id_for(plain) == db_id_for("bigquery://p/d?credentials_base64=OTHER")


def test_a_multiline_credential_is_redacted_past_the_first_space():
    """credentials_info is decoded JSON — its value has spaces in it, and the
    private key sits well past the first one."""
    blob = '{"type": "service_account", "private_key": "-----BEGIN AAA-----"}'
    msg = _sanitize_db_error(f"failed: credentials_info={blob} rejected")
    assert "BEGIN AAA" not in msg
    assert "service_account" not in msg


def test_a_driver_whose_own_dependency_is_broken_is_not_called_missing(monkeypatch):
    """An installed driver that fails to import something of its own is a
    different problem from an absent one, and telling that user to install what
    they already have sends them the wrong way."""

    def boom(*_a, **_kw):
        raise ImportError("cannot import name 'X' from 'pyarrow.lib'")

    monkeypatch.setattr("backend.app.database.create_engine", boom)
    res = DatabaseManager().connect(TEST_USER, "snowflake://u:p@acct/DB")
    assert res["ok"] is False
    assert "no driver installed" not in res["error"].lower()
    assert "pyarrow" in res["error"]


@pytest.mark.parametrize(
    "err",
    [
        "000630 (57014): Statement reached its statement or warehouse timeout "
        "of 30 second(s) and was canceled.",
        "SQL execution canceled",
    ],
)
def test_a_snowflake_timeout_reads_as_a_timeout(db, err):
    """The server names whichever timeout fired — statement or warehouse — so
    matching the full sentence missed the real message."""
    from sqlalchemy.exc import SQLAlchemyError

    db._connections[TEST_USER]["dialect"] = "snowflake"
    try:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                db, "_apply_statement_timeout", lambda *_a, **_kw: None, raising=False
            )
            engine = db._connections[TEST_USER]["engine"]

            class _Boom:
                def __enter__(self):
                    raise SQLAlchemyError(err)

                def __exit__(self, *_a):
                    return False

            mp.setattr(engine, "connect", lambda *_a, **_kw: _Boom())
            res = db.execute(TEST_USER, "SELECT 1")
        assert "took longer than" in res["error"]
    finally:
        db._connections[TEST_USER]["dialect"] = "sqlite"
