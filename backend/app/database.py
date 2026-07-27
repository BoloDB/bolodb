"""Database connection, schema introspection (guarded), read-only execution."""

import hashlib
import ipaddress
import re
import logging
import sqlglot
import sqlglot.expressions as exp
from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from fastapi.exceptions import HTTPException

from backend.app.dialects import (
    allowed_schemes,
    denormalize_ident,
    glot_dialect,
    limit_clause,
    normalize_driver,
    normalize_ident,
    quote_ident,
    traits_for,
)

logger = logging.getLogger(__name__)

# Conservative keyword guard, used as a fallback when a statement cannot be
# parsed into an AST (see _readonly_violation). The AST check is the primary
# defence; this regex only runs when sqlglot can't understand the SQL.
WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"ATTACH|DETACH|EXEC|EXECUTE|MERGE|PRAGMA|VACUUM|CALL|INTO)\b",
    re.IGNORECASE,
)

# AST node types that mutate data/schema and must never run in read-only mode
_MODIFYING_NODES = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.Command,
)


def sanitize_url(url):
    if "@" not in url:
        return url
    head, tail = url.split("@", 1)
    if "://" in head:
        scheme, creds = head.split("://", 1)
        return f"{scheme}://{creds.split(':')[0]}:***@{tail}"
    return url


def _sanitize_db_error(err_msg: str) -> str:
    """Strip driver-specific details (hostnames, ports, connection strings) from
    database error messages before returning them to the client."""
    import re

    msg = str(err_msg)
    msg = re.sub(r"host(?:name)?[=:]\s*\S+", "host=***", msg, flags=re.IGNORECASE)
    msg = re.sub(r"port[=:]\s*\d+", "port=***", msg, flags=re.IGNORECASE)
    msg = re.sub(r"password[=:]\s*\S+", "password=***", msg, flags=re.IGNORECASE)
    msg = re.sub(r"dbname[=:]\s*\S+", "dbname=***", msg, flags=re.IGNORECASE)
    msg = re.sub(r"database[=:]\s*\S+", "database=***", msg, flags=re.IGNORECASE)
    # The "+driver" suffix has to be optional on every scheme, not just Oracle:
    # a URL reaches the driver in its canonical form, so the string in an
    # exception is "mysql+pymysql://user:pass@..." and a pattern anchored on a
    # bare "mysql://" walks straight past the credentials in it.
    msg = re.sub(
        r"\b(postgresql|postgres|mysql|mssql|oracle)(?:\+\w+)?://\S+",
        r"\1://***",
        msg,
    )
    msg = re.sub(r"sqlite:///?\S+", "sqlite://***", msg)
    # Oracle DSNs also appear bare (host:port/service_name) in driver errors.
    msg = re.sub(
        r"service_name\s*=\s*\S+", "service_name=***", msg, flags=re.IGNORECASE
    )
    msg = re.sub(r"\bsid\s*=\s*\S+", "sid=***", msg, flags=re.IGNORECASE)
    return msg


_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",
    "metadata.google.internal",
    "instance-data",
    "100.100.100.200",
}


# A host we are willing to check. Anything a hostname, an IPv4 literal or a
# bracket-less IPv6 literal can contain — and nothing that could smuggle a
# target past the checks below, such as the "(" "=" ")" of an Oracle
# DESCRIPTION connect descriptor.
_PLAIN_HOST = re.compile(r"^[A-Za-z0-9._:%\-]+$")


def _validate_db_url(url: str) -> str:
    """Validate a database URL to prevent SSRF attacks.

    Checks:
    1. Scheme must be a dialect we support (see backend/app/dialects.py)
    2. The URL must name its target as a plain host, not smuggle it past the
       host field the way Oracle's DSN forms can
    3. Hostname must not be a blocked internal/metadata address
    4. No file:// or other non-SQL schemes

    The URL is parsed with SQLAlchemy's own ``make_url``, so what gets checked
    is what ``create_engine`` will actually dial — ``urlparse`` reports no
    hostname at all for the Oracle DSN forms, which let a target through.

    Returns the URL if valid, raises ValueError otherwise.
    """
    try:
        parsed = make_url(url)
    except Exception:
        raise ValueError("Could not parse the database URL")

    # Strip any driver suffix: "oracle+oracledb" -> "oracle".
    scheme = (parsed.drivername or "").split("+")[0].lower()

    allowed = allowed_schemes()
    if scheme not in allowed:
        raise ValueError(
            f"Unsupported database scheme '{scheme}'. "
            f"Allowed: {', '.join(sorted(allowed))}"
        )

    if scheme != "sqlite":
        # Oracle accepts the connect target in places that are not the host
        # field: a "dsn" query parameter, and a bare TNS name or DESCRIPTION
        # descriptor in place of a hostname. Both are handed straight to the
        # driver, so neither can be host-checked — refuse them and require
        # host/port/service_name, which is the only form we document.
        if scheme == "oracle":
            if "dsn" in {k.lower() for k in parsed.query}:
                raise ValueError(
                    "The 'dsn' parameter is not allowed; connect with "
                    "host, port and service_name instead"
                )
            # With neither, SQLAlchemy stops building a host:port/service DSN
            # and passes the host field through as a connect string of its own.
            if not parsed.database and not parsed.query.get("service_name"):
                raise ValueError(
                    "An Oracle URL needs a service_name parameter or a SID "
                    "path, e.g. oracle+oracledb://user:pass@host:1521/"
                    "?service_name=ORCLPDB1"
                )

        hostname = (parsed.host or "").lower()
        if not hostname:
            raise ValueError("A hostname is required for this database")
        if not _PLAIN_HOST.match(hostname):
            # Also where an unescaped credential lands: SQLAlchemy splits on the
            # first "@", so a raw "@" in a password pushes the rest of it into
            # the host. Say so — the alternative is a baffling DNS failure.
            raise ValueError(
                "The host must be a plain hostname or IP address. If the "
                "password contains @ : / or #, percent-encode it. Connect "
                "descriptors and TNS aliases are not supported."
            )
        if hostname in _BLOCKED_HOSTS:
            raise ValueError(f"Connection to '{hostname}' is not allowed")
        if hostname.startswith("169.254.") or hostname.startswith("100.100."):
            raise ValueError("Connection to metadata endpoints is not allowed")
        try:
            # Not an IP literal at all — a name, which we cannot resolve here.
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None
        # Raised outside the try: inside it, the except would swallow it.
        if ip is not None and ip.is_loopback:
            raise ValueError(
                f"Connection to loopback address '{hostname}' is not allowed"
            )

    return url


def db_id_for(url):
    return hashlib.sha256(sanitize_url(url).encode()).hexdigest()[:16]


class _ConnectionsDict(dict):
    def __getitem__(self, key):
        if key in self:
            return super().__getitem__(key)
        if isinstance(key, str):
            for k, v in self.items():
                if k == key or (isinstance(k, tuple) and k[0] == key):
                    return v
        raise KeyError(key)


class DatabaseManager:
    def __init__(
        self, readonly=True, sample_rows=3, max_rows=500, statement_timeout=30
    ):
        self._connections = _ConnectionsDict()
        self.readonly = readonly
        self.sample_rows = sample_rows
        self.max_rows = max_rows
        # Seconds a single statement may run before the database server aborts
        # it. Enforced server-side per connection (see _apply_statement_timeout).
        self.statement_timeout = statement_timeout

    def connected(self, workspace_id, db_id=None):
        if db_id:
            return (workspace_id, db_id) in self._connections
        return any(k[0] == workspace_id for k in self._connections.keys())

    def _get(self, workspace_id, db_id=None):
        if db_id:
            try:
                return self._connections[(workspace_id, db_id)]
            except KeyError:
                raise HTTPException(409, "No Database Connected")

        # Fallback to the first connected database for this workspace
        for k, v in self._connections.items():
            if k[0] == workspace_id:
                return v
        raise HTTPException(409, "No Database Connected")

    def disconnect(self, workspace_id, db_id=None):
        """Reset all connection state so the server accepts a new connect call."""
        keys_to_delete = []
        for k in self._connections.keys():
            if k[0] == workspace_id and (db_id is None or k[1] == db_id):
                keys_to_delete.append(k)

        for k in keys_to_delete:
            try:
                self._connections[k]["engine"].dispose()
            except Exception as e:
                logger.warning("Error disposing engine on disconnect: %s", e)
            del self._connections[k]

    def connect(self, workspace_id, url):
        import os

        if os.environ.get("RUNNING_IN_DOCKER") == "true":
            if "localhost" in url or "127.0.0.1" in url:
                url = url.replace("localhost", "host.docker.internal").replace(
                    "127.0.0.1", "host.docker.internal"
                )

        try:
            url = _validate_db_url(url)
        except ValueError as e:
            return {"ok": False, "error": str(e)}

        # Before db_id_for below, so one target hashes to one id however the
        # user spelled its scheme.
        url = normalize_driver(url)
        dialect = url.split(":")[0].split("+")[0]
        try:
            engine = create_engine(url)
            self._install_call_timeout(engine, dialect)
            with engine.connect() as c:
                # select(1) rather than text("SELECT 1"): SQLAlchemy compiles it
                # per dialect, so Oracle gets the "SELECT 1 FROM DUAL" it
                # requires while every other dialect is unchanged.
                c.execute(select(1))
            tables = len(inspect(engine).get_table_names())
            db_id = db_id_for(url)
            old_connection = self._connections.get((workspace_id, db_id))
            self._connections[(workspace_id, db_id)] = {
                "engine": engine,
                "url": url,
                "db_id": db_id,
                "dialect": dialect,
                "_schema_cache": None,
                "_table_count": tables,
            }
            if old_connection:
                old_connection["engine"].dispose()
            return {
                "ok": True,
                "dialect": self._connections[(workspace_id, db_id)]["dialect"],
                "tables": tables,
                "db_id": self._connections[(workspace_id, db_id)]["db_id"],
                "url": sanitize_url(url),
            }
        except Exception as e:
            return {"ok": False, "error": _sanitize_db_error(e)}

    def _install_call_timeout(self, engine, dialect):
        """Bound statements on dialects with no session-level timeout setting.

        Oracle has no equivalent of ``SET statement_timeout``; the driver-level
        ``call_timeout`` is the supported way to cancel a round trip that runs
        too long, and it must be set on the DBAPI connection as it is created.

        It is a weaker bound than the name suggests: it caps each round trip,
        not the statement. A query that fetches across several round trips can
        outlast ``statement_timeout`` in wall-clock terms while no single trip
        ever exceeds it, and ``max_rows`` caps rows returned, not duration. It
        still stops the case that matters — a statement that hangs — but do not
        read it as a hard ceiling on how long an Oracle query can take.
        """
        if traits_for(dialect).timeout_style != "call_timeout":
            return
        if not self.statement_timeout:
            return
        ms = int(self.statement_timeout * 1000)

        @event.listens_for(engine, "connect")
        def _set_call_timeout(dbapi_conn, _record):  # pragma: no cover - driver hook
            try:
                dbapi_conn.call_timeout = ms
            except Exception as e:
                logger.warning("Could not set call_timeout for %s: %s", dialect, e)

    def _q(self, workspace_id, n, db_id=None):
        # db_id matters: a workspace can hold connections to different engines,
        # and quoting a name with the first connection's rules would emit
        # backticks at Oracle.
        c = self._get(workspace_id, db_id=db_id)
        return quote_ident(c["dialect"], n)

    def get_schema(self, workspace_id, db_id=None, refresh=False):
        """Introspect the connected database into the schema dict.

        STRUCTURE (columns, primary/foreign keys) is collected for EVERY table
        — schema linking must be able to see the whole database, however big.
        Only the expensive ENRICHMENT (sample rows, per-table row counts,
        distinct values) is capped, at ENRICH_MAX tables, preferring the
        largest tables when row counts are known.
        """
        c = self._get(workspace_id, db_id=db_id)
        if c["_schema_cache"] and not refresh:
            return c["_schema_cache"]
        inspector = inspect(c["engine"])
        schema = {}
        ENRICH_MAX = 40
        BIG = 100_000
        SKIP = (
            "date",
            "time",
            "name",
            "email",
            "phone",
            "address",
            "id",
            "desc",
            "url",
            "note",
            "comment",
            "title",
            "code",
        )
        table_names = inspector.get_table_names()

        # Fetch column/pk/fk metadata in bulk where the dialect supports it
        try:
            schema_name = inspector.default_schema_name
            multi_cols = inspector.get_multi_columns(schema=schema_name)
            multi_pks = inspector.get_multi_pk_constraint(schema=schema_name)
            multi_fks = inspector.get_multi_foreign_keys(schema=schema_name)
        except Exception:
            schema_name = None
            multi_cols = {}
            multi_pks = {}
            multi_fks = {}

        with c["engine"].connect() as conn:
            # Enrichment (COUNT(*), DISTINCT) can be slow on large tables; bound it.
            self._apply_statement_timeout(conn, c["dialect"])
            # Fetch approximate row counts from the server's stats tables in one
            # shot, where the dialect has such a table (see dialects.py).
            # Anything else falls back to per-table COUNT(*) below.
            bulk_counts = {}
            row_count_sql = traits_for(c["dialect"]).row_count_sql
            if row_count_sql:
                try:
                    stmt = text(row_count_sql)
                    # The catalog stores identifiers in the server's own casing,
                    # which is not what reflection handed us: bind the owner in
                    # that casing going in, and fold the table names it returns
                    # back on the way out, or nothing matches ``table_names``.
                    params = (
                        {"owner": denormalize_ident(c["dialect"], schema_name)}
                        if ":owner" in row_count_sql
                        else {}
                    )
                    r = conn.execute(stmt, params)
                    bulk_counts = {
                        normalize_ident(c["dialect"], row[0]): (
                            max(0, int(row[1])) if row[1] is not None else 0
                        )
                        for row in r
                    }
                except Exception as e:
                    logger.warning(
                        "Bulk row counts unavailable for %s: %s", c["dialect"], e
                    )

            # Determine which tables get the expensive enrichment queries: all of
            # them when the database is small; the biggest ones by row count
            # when it is not. Structure (columns/PKs/FKs) is always collected
            # for every table regardless.
            if len(table_names) <= ENRICH_MAX:
                enrich = set(table_names)
            else:

                def _sort_key(t):
                    count = bulk_counts.get(t)
                    return (count is None, -(count or 0), t)

                by_size = sorted(table_names, key=_sort_key)
                enrich = set(by_size[:ENRICH_MAX])

            for tbl in table_names:
                try:
                    key = (schema_name, tbl)
                    alt = (None, tbl)
                    if key in multi_cols:
                        cols_raw = multi_cols[key]
                        pk = multi_pks.get(key, {}).get("constrained_columns", []) or []
                        fks_raw = multi_fks.get(key, [])
                    elif alt in multi_cols:
                        cols_raw = multi_cols[alt]
                        pk = multi_pks.get(alt, {}).get("constrained_columns", []) or []
                        fks_raw = multi_fks.get(alt, [])
                    else:
                        cols_raw = inspector.get_columns(tbl)
                        pk = (
                            inspector.get_pk_constraint(tbl).get(
                                "constrained_columns", []
                            )
                            or []
                        )
                        fks_raw = inspector.get_foreign_keys(tbl)
                    fks = [
                        {
                            "column": (
                                fk["constrained_columns"][0]
                                if fk["constrained_columns"]
                                else ""
                            ),
                            "references": (
                                f"{fk['referred_table']}.{fk['referred_columns'][0]}"
                                if fk["referred_columns"]
                                else ""
                            ),
                        }
                        for fk in fks_raw
                    ]
                    columns = [
                        {
                            "name": col["name"],
                            "type": str(col["type"]),
                            "primary_key": col["name"] in pk,
                        }
                        for col in cols_raw
                    ]
                except Exception as e:
                    logger.warning("Error inspecting columns for %s: %s", tbl, e)
                    continue

                if tbl not in enrich:
                    # Structure only: still fully visible to schema linking
                    # and the AI prompt, just without samples/known values.
                    schema[tbl] = {
                        "columns": columns,
                        "foreign_keys": fks,
                        "sample_rows": [],
                        "row_count": bulk_counts.get(tbl),
                        "distinct_values": {},
                    }
                    continue

                try:
                    res = conn.execute(
                        text(
                            f"SELECT * FROM {self._q(workspace_id, tbl, db_id)} "
                            f"{limit_clause(c['dialect'], self.sample_rows)}"
                        )
                    )
                    names = list(res.keys())
                    samples = [dict(zip(names, row)) for row in res.fetchall()]
                    for r in samples:
                        for k, v in r.items():
                            if isinstance(v, str) and len(v) > 50:
                                r[k] = v[:47] + "..."
                except Exception as e:
                    logger.warning("Error fetching samples for %s: %s", tbl, e)
                    samples = []

                rc = bulk_counts.get(tbl)
                if rc is None:
                    try:
                        rc = conn.execute(
                            text(
                                "SELECT COUNT(*) FROM "
                                f"{self._q(workspace_id, tbl, db_id)}"
                            )
                        ).scalar()
                    except Exception as e:
                        logger.warning("Error fetching row count for %s: %s", tbl, e)
                        rc = None

                low_card = {}
                if rc is None or rc <= BIG:
                    for col in columns:
                        if any(s in col["name"].lower() for s in SKIP):
                            continue
                        if any(
                            t in col["type"].lower()
                            for t in ("char", "text", "enum", "varchar")
                        ):
                            try:
                                dv = conn.execute(
                                    text(
                                        "SELECT DISTINCT "
                                        f"{self._q(workspace_id, col['name'], db_id)} "
                                        f"FROM {self._q(workspace_id, tbl, db_id)} "
                                        f"{limit_clause(c['dialect'], 12)}"
                                    )
                                ).fetchall()
                                vals = [row[0] for row in dv if row[0] is not None]
                                if 0 < len(vals) <= 8:
                                    low_card[col["name"]] = vals
                            except Exception as e:
                                logger.warning(
                                    "Error fetching distinct values for %s.%s: %s",
                                    tbl,
                                    col["name"],
                                    e,
                                )

                schema[tbl] = {
                    "columns": columns,
                    "foreign_keys": fks,
                    "sample_rows": samples,
                    "row_count": rc,
                    "distinct_values": low_card,
                }
        c["_schema_cache"] = schema
        return schema

    def schema_as_text(self, workspace_id, db_id=None):
        c = self._get(workspace_id, db_id)
        schema = self.get_schema(workspace_id, db_id=db_id)
        lines = [f"Database dialect: {c['dialect']}"]
        for tbl, info in schema.items():
            rc = (
                f"  (~{info['row_count']} rows)"
                if info["row_count"] is not None
                else ""
            )
            lines.append(f"\nTABLE {tbl}{rc}")
            fk_map = {
                fk["column"]: fk["references"]
                for fk in info.get("foreign_keys", [])
                if fk.get("column")
            }
            for cc in info["columns"]:
                flags = " PK" if cc.get("primary_key") else ""
                if cc["name"] in fk_map:
                    flags += f"->{fk_map[cc['name']]}"
                dv = info["distinct_values"].get(cc["name"])
                dv_str = f"[{','.join(str(v) for v in dv[:6])}]" if dv else ""
                lines.append(f"  {cc['name']} {cc['type']}{flags}{dv_str}")
            if info["sample_rows"]:
                lines.append(f"  sample: {info['sample_rows'][:1]}")
        return "\n".join(lines)

    def _readonly_violation(self, workspace_id, cleaned, db_id=None):
        """Return an error string if `cleaned` is not a safe read-only query, else None.

        Primary check parses the SQL into an AST (sqlglot) and rejects anything
        that isn't a single SELECT/WITH/EXPLAIN or that contains a modifying node
        anywhere in the tree (e.g. a DELETE inside a CTE, or SELECT INTO). This is
        precise: identifiers that merely *contain* a keyword (e.g. `updates_log`)
        are not flagged. If the statement can't be parsed, we fall back to the
        conservative keyword regex so unparseable SQL is never executed blindly.
        """
        if not cleaned:
            return "Empty statement."
        c = self._get(workspace_id, db_id)
        try:
            stmts = sqlglot.parse(cleaned, dialect=glot_dialect(c["dialect"]))
        except Exception:
            # Fallback: couldn't build an AST — apply the conservative regex guard.
            first = cleaned.split()[0].upper() if cleaned else ""
            if first not in ("SELECT", "WITH", "EXPLAIN"):
                return "Only SELECT queries are allowed (read-only mode)."
            if ";" in cleaned or WRITE_KEYWORDS.search(cleaned):
                return "Only read-only SELECT queries are allowed."
            return None

        stmts = [s for s in stmts if s is not None]
        if len(stmts) > 1:
            return "Only one statement is allowed (no stacked queries)."
        if not stmts:
            return "Empty statement."
        stmt = stmts[0]

        # Root must be a read-only statement type.
        root = type(stmt).__name__
        is_explain = root == "Command" and str(stmt.this).upper() == "EXPLAIN"
        if root not in ("Select", "Union", "Explain") and not is_explain:
            return "Only SELECT queries are allowed (read-only mode)."

        # No modifying node may appear anywhere in the tree (catches CTE writes).
        for node in stmt.find_all(*_MODIFYING_NODES):
            if type(node).__name__ == "Command" and str(node.this).upper() == "EXPLAIN":
                continue
            return "Only read-only SELECT queries are allowed."

        # Block SELECT ... INTO (creates/overwrites a table).
        if next(stmt.find_all(exp.Into), None) is not None:
            return "SELECT INTO is not allowed."
        return None

    def _apply_statement_timeout(self, conn, dialect):
        """Best-effort server-enforced per-statement timeout on ``conn``.

        Postgres and MySQL both support a session-level statement timeout the
        server enforces, which is the only reliable way to stop a runaway query
        (a client-side cap can't cancel work already running on the server).
        Oracle has no session equivalent, so it is bounded instead by the
        driver's ``call_timeout``, set once per connection in
        ``_install_call_timeout``. Dialects with neither (sqlite, mssql) are left
        unbounded here — the row fetch cap is the remaining backstop. Failures
        are swallowed so an unsupported SET never blocks the actual query.
        """
        if not self.statement_timeout:
            return
        ms = int(self.statement_timeout * 1000)
        style = traits_for(dialect).timeout_style
        try:
            if style == "statement_timeout":
                conn.execute(text(f"SET statement_timeout = {ms}"))
            elif style == "max_execution_time":
                # Applies to read-only SELECTs, which is all we run.
                conn.execute(text(f"SET SESSION MAX_EXECUTION_TIME = {ms}"))
        except SQLAlchemyError as e:
            logger.warning("Could not set statement timeout for %s: %s", dialect, e)

    def execute(self, workspace_id, sql, db_id=None):
        c = self._get(workspace_id, db_id)
        cleaned = sql.strip().rstrip(";").strip()
        if self.readonly:
            violation = self._readonly_violation(workspace_id, cleaned, db_id)
            if violation:
                return {"error": violation, "sql": cleaned}
        try:
            with c["engine"].connect() as conn:
                self._apply_statement_timeout(conn, c["dialect"])
                res = conn.execute(text(cleaned))
                cols = list(res.keys())
                raw = res.fetchmany(self.max_rows + 1)
                truncated = len(raw) > self.max_rows
                rows = []
                for row in raw[: self.max_rows]:
                    d = {}
                    for col, val in zip(cols, row):
                        d[col] = val.isoformat() if hasattr(val, "isoformat") else val
                    rows.append(d)
                return {
                    "columns": cols,
                    "rows": rows,
                    "row_count": len(rows),
                    "truncated": truncated,
                    "sql": cleaned,
                }
        except SQLAlchemyError as e:
            low = str(e).lower()
            if (
                "statement timeout" in low
                or "maximum statement execution time" in low
                # python-oracledb raises DPY-4011 when call_timeout fires.
                or "dpy-4011" in low
                or "call timeout" in low
            ):
                return {
                    "error": (
                        f"The query took longer than {self.statement_timeout}s and was "
                        "cancelled. Try narrowing it (add a filter or a smaller range)."
                    ),
                    "sql": cleaned,
                }
            return {"error": _sanitize_db_error(e), "sql": cleaned}

    def get_db_id(self, workspace_id, db_id=None):
        return self._get(workspace_id, db_id)["db_id"]

    def get_dialect(self, workspace_id, db_id=None):
        return self._get(workspace_id, db_id)["dialect"]

    def get_info(self, workspace_id, db_id=None):
        c = self._get(workspace_id, db_id)
        return {
            "url": sanitize_url(c["url"]),
            "dialect": c["dialect"],
            "tables": c["_table_count"],
            "db_id": c["db_id"],
        }
