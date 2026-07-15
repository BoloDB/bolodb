"""Database connection, schema introspection (guarded), read-only execution."""

import hashlib
import ipaddress
import re
import logging
import sqlglot
import sqlglot.expressions as exp
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError
from fastapi.exceptions import HTTPException

logger = logging.getLogger(__name__)

# Conservative keyword guard, used as a fallback when a statement cannot be
# parsed into an AST (see _readonly_violation). The AST check is the primary
# defence; this regex only runs when sqlglot can't understand the SQL.
WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"ATTACH|DETACH|EXEC|EXECUTE|MERGE|PRAGMA|VACUUM|CALL|INTO)\b",
    re.IGNORECASE,
)

# sqlalchemy dialect name -> sqlglot dialect name (only where they differ)
_GLOT_DIALECT = {"postgresql": "postgres", "mssql": "tsql"}

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
    msg = re.sub(r"postgresql://\S+", "postgresql://***", msg)
    msg = re.sub(r"postgres://\S+", "postgres://***", msg)
    msg = re.sub(r"mysql://\S+", "mysql://***", msg)
    msg = re.sub(r"mssql://\S+", "mssql://***", msg)
    msg = re.sub(r"sqlite:///?\S+", "sqlite://***", msg)
    return msg


_ALLOWED_SCHEMES = {"postgresql", "postgres", "mysql", "mssql", "sqlite"}
_BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "169.254.169.254",
    "metadata.google.internal",
    "instance-data",
    "100.100.100.200",
}


def _validate_db_url(url: str) -> str:
    """Validate a database URL to prevent SSRF attacks.

    Checks:
    1. Scheme must be an allowed SQL dialect (postgresql, mysql, mssql, sqlite)
    2. Hostname must not be a blocked internal/metadata address
    3. No file:// or other non-SQL schemes

    Returns the URL if valid, raises ValueError otherwise.
    """
    from urllib.parse import urlparse

    parsed = urlparse(url)
    scheme = (parsed.scheme or "").split("+")[0].lower()

    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Unsupported database scheme '{scheme}'. "
            f"Allowed: {', '.join(sorted(_ALLOWED_SCHEMES))}"
        )

    if scheme != "sqlite":
        hostname = (parsed.hostname or "").lower()
        if hostname in _BLOCKED_HOSTS:
            raise ValueError(f"Connection to '{hostname}' is not allowed")
        if hostname.startswith("169.254.") or hostname.startswith("100.100."):
            raise ValueError("Connection to metadata endpoints is not allowed")
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_loopback:
                raise ValueError(
                    f"Connection to loopback address '{hostname}' is not allowed"
                )
        except ValueError:
            pass

    return url


def db_id_for(url):
    return hashlib.sha256(sanitize_url(url).encode()).hexdigest()[:16]


class DatabaseManager:
    def __init__(self, readonly=True, sample_rows=3, max_rows=500):
        self._connections = {}
        self.readonly = readonly
        self.sample_rows = sample_rows
        self.max_rows = max_rows

    def connected(self, user_id):
        return user_id in self._connections

    def _get(self, user_id):
        try:
            return self._connections[user_id]
        except KeyError:
            raise HTTPException(409, "No Database Connected")

    def disconnect(self, user_id):
        """Reset all connection state so the server accepts a new connect call."""
        if user_id not in self._connections:
            return
        try:
            self._connections[user_id]["engine"].dispose()  # release pooled connections
        except Exception as e:
            logger.warning("Error disposing engine on disconnect: %s", e)
        del self._connections[user_id]

    def connect(self, user_id, url):
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

        try:
            engine = create_engine(url)
            with engine.connect() as c:
                c.execute(text("SELECT 1"))
            tables = len(inspect(engine).get_table_names())
            old_connection = self._connections.get(user_id)
            self._connections[user_id] = {
                "engine": engine,
                "url": url,
                "db_id": db_id_for(url),
                "dialect": url.split(":")[0].split("+")[0],
                "_schema_cache": None,
                "_table_count": tables,
            }
            if old_connection:
                old_connection["engine"].dispose()
            return {
                "ok": True,
                "dialect": self._connections[user_id]["dialect"],
                "tables": tables,
                "db_id": self._connections[user_id]["db_id"],
                "url": sanitize_url(url),
            }
        except Exception as e:
            return {"ok": False, "error": _sanitize_db_error(e)}

    def _q(self, user_id, n):
        c = self._get(user_id)
        n = str(n)
        if c["dialect"] == "mysql":
            return f"`{n.replace('`', '``')}`"
        return f'"{n.replace(chr(34), chr(34) * 2)}"'

    def get_schema(self, user_id, refresh=False):
        """Introspect the connected database into the schema dict.

        STRUCTURE (columns, primary/foreign keys) is collected for EVERY table
        — schema linking must be able to see the whole database, however big.
        Only the expensive ENRICHMENT (sample rows, per-table row counts,
        distinct values) is capped, at ENRICH_MAX tables, preferring the
        largest tables when row counts are known.
        """
        c = self._get(user_id)
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
            # Fetch approximate row counts from DB stats tables in one shot (postgres/mysql/mssql)
            bulk_counts = {}
            try:
                if c["dialect"] == "postgresql":
                    r = conn.execute(
                        text(
                            "SELECT relname, reltuples FROM pg_class WHERE relkind IN ('r','p')"
                        )
                    )
                    bulk_counts = {row[0]: max(0, int(row[1])) for row in r}
                elif c["dialect"] == "mysql":
                    r = conn.execute(
                        text(
                            "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE()"
                        )
                    )
                    bulk_counts = {
                        row[0]: int(row[1]) if row[1] is not None else 0 for row in r
                    }
                elif c["dialect"] == "mssql":
                    r = conn.execute(
                        text(
                            "SELECT t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p ON t.object_id=p.object_id WHERE p.index_id IN (0,1) GROUP BY t.name"
                        )
                    )
                    bulk_counts = {
                        row[0]: int(row[1]) if row[1] is not None else 0 for row in r
                    }
            except Exception:
                pass

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
                            f"SELECT * FROM {self._q(user_id, tbl)} LIMIT {self.sample_rows}"
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
                            text(f"SELECT COUNT(*) FROM {self._q(user_id, tbl)}")
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
                                        f"SELECT DISTINCT {self._q(user_id, col['name'])} FROM {self._q(user_id, tbl)} LIMIT 12"
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

    def schema_as_text(self, user_id):
        c = self._get(user_id)
        schema = self.get_schema(user_id)
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

    def _readonly_violation(self, user_id, cleaned):
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
        c = self._get(user_id)
        glot_dialect = _GLOT_DIALECT.get(c["dialect"], c["dialect"])
        try:
            stmts = sqlglot.parse(cleaned, dialect=glot_dialect)
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

    def execute(self, user_id, sql):
        c = self._get(user_id)
        cleaned = sql.strip().rstrip(";").strip()
        if self.readonly:
            violation = self._readonly_violation(user_id, cleaned)
            if violation:
                return {"error": violation, "sql": cleaned}
        try:
            with c["engine"].connect() as conn:
                res = conn.execute(text(cleaned).execution_options(timeout=30))
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
            return {"error": _sanitize_db_error(e), "sql": cleaned}

    def get_db_id(self, user_id):
        return self._get(user_id)["db_id"]

    def get_dialect(self, user_id):
        return self._get(user_id)["dialect"]

    def get_info(self, user_id):
        c = self._get(user_id)
        return {
            "url": sanitize_url(c["url"]),
            "dialect": c["dialect"],
            "tables": c["_table_count"],
            "db_id": c["db_id"],
        }
