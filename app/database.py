"""Database connection, schema introspection (guarded), read-only execution."""
import hashlib, re
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

WRITE_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|"
    r"ATTACH|DETACH|EXEC|EXECUTE|MERGE|PRAGMA|VACUUM|CALL|INTO)\b", re.IGNORECASE)

def sanitize_url(url):
    if "@" not in url: return url
    head, tail = url.split("@", 1)
    if "://" in head:
        scheme, creds = head.split("://", 1)
        return f"{scheme}://{creds.split(':')[0]}:***@{tail}"
    return url

def db_id_for(url):
    return hashlib.sha256(sanitize_url(url).encode()).hexdigest()[:16]

class DatabaseManager:
    def __init__(self, readonly=True, sample_rows=3, max_rows=500):
        self.readonly = readonly; self.sample_rows = sample_rows; self.max_rows = max_rows
        self.engine = None; self.url = None; self.db_id = None
        self.dialect = None; self._schema_cache = None; self._table_count = 0

    @property
    def connected(self): return self.engine is not None

    def disconnect(self):
        """Reset all connection state so the server accepts a new connect call."""
        self.engine = None; self.url = None; self.db_id = None
        self.dialect = None; self._schema_cache = None; self._table_count = 0

    def connect(self, url):
        try:
            engine = create_engine(url)
            with engine.connect() as c: c.execute(text("SELECT 1"))
            self.engine = engine; self.url = url; self.db_id = db_id_for(url)
            self.dialect = url.split(":")[0].split("+")[0]; self._schema_cache = None
            tables = len(inspect(engine).get_table_names())
            self._table_count = tables
            return {"ok":True,"dialect":self.dialect,"tables":tables,"db_id":self.db_id,
                    "url":sanitize_url(url)}
        except Exception as e:
            return {"ok":False,"error":str(e)}

    def _q(self, n):
        n = str(n)
        if self.dialect == "mysql":
            return f"`{n.replace('`', '``')}`"
        return f'"{n.replace(chr(34), chr(34)*2)}"'

    def get_schema(self, refresh=False):
        if self._schema_cache and not refresh: return self._schema_cache
        inspector = inspect(self.engine)
        schema = {}
        MAX_T = 40; BIG = 100_000
        SKIP = ("date","time","name","email","phone","address","id","desc","url","note","comment","title","code")
        table_names = inspector.get_table_names()[:MAX_T]

        # Fetch column/pk/fk metadata in bulk where the dialect supports it
        try:
            schema_name = inspector.default_schema_name
            multi_cols = inspector.get_multi_columns(schema=schema_name)
            multi_pks  = inspector.get_multi_pk_constraint(schema=schema_name)
            multi_fks  = inspector.get_multi_foreign_keys(schema=schema_name)
        except Exception:
            schema_name = None; multi_cols = {}; multi_pks = {}; multi_fks = {}

        with self.engine.connect() as conn:
            # Fetch approximate row counts from DB stats tables in one shot (postgres/mysql/mssql)
            bulk_counts = {}
            try:
                if self.dialect == "postgresql":
                    r = conn.execute(text("SELECT relname, reltuples FROM pg_class WHERE relkind IN ('r','p')"))
                    bulk_counts = {row[0]: int(row[1]) for row in r}
                elif self.dialect == "mysql":
                    r = conn.execute(text("SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = DATABASE()"))
                    bulk_counts = {row[0]: int(row[1]) if row[1] is not None else 0 for row in r}
                elif self.dialect == "mssql":
                    r = conn.execute(text("SELECT t.name, SUM(p.rows) FROM sys.tables t JOIN sys.partitions p ON t.object_id=p.object_id WHERE p.index_id IN (0,1) GROUP BY t.name"))
                    bulk_counts = {row[0]: int(row[1]) if row[1] is not None else 0 for row in r}
            except Exception:
                pass

            for tbl in table_names:
                try:
                    key = (schema_name, tbl)
                    alt = (None, tbl)
                    if key in multi_cols:
                        cols_raw = multi_cols[key]
                        pk  = multi_pks.get(key, {}).get("constrained_columns", []) or []
                        fks_raw = multi_fks.get(key, [])
                    elif alt in multi_cols:
                        cols_raw = multi_cols[alt]
                        pk  = multi_pks.get(alt, {}).get("constrained_columns", []) or []
                        fks_raw = multi_fks.get(alt, [])
                    else:
                        cols_raw = inspector.get_columns(tbl)
                        pk  = inspector.get_pk_constraint(tbl).get("constrained_columns", []) or []
                        fks_raw = inspector.get_foreign_keys(tbl)
                    fks = [{"column": fk["constrained_columns"][0] if fk["constrained_columns"] else "",
                            "references": f"{fk['referred_table']}.{fk['referred_columns'][0]}" if fk["referred_columns"] else ""}
                           for fk in fks_raw]
                    columns = [{"name": c["name"], "type": str(c["type"]), "primary_key": c["name"] in pk}
                               for c in cols_raw]
                except Exception as e:
                    logger.warning("Error inspecting columns for %s: %s", tbl, e); continue

                try:
                    res = conn.execute(text(f"SELECT * FROM {self._q(tbl)} LIMIT {self.sample_rows}"))
                    names = list(res.keys())
                    samples = [dict(zip(names, row)) for row in res.fetchall()]
                    for r in samples:
                        for k, v in r.items():
                            if isinstance(v, str) and len(v) > 50: r[k] = v[:47] + "..."
                except Exception as e:
                    logger.warning("Error fetching samples for %s: %s", tbl, e); samples = []

                rc = bulk_counts.get(tbl)
                if rc is None:
                    try:
                        rc = conn.execute(text(f"SELECT COUNT(*) FROM {self._q(tbl)}")).scalar()
                    except Exception as e:
                        logger.warning("Error fetching row count for %s: %s", tbl, e); rc = None

                low_card = {}
                if rc is None or rc <= BIG:
                    for c in columns:
                        if any(s in c["name"].lower() for s in SKIP): continue
                        if any(t in c["type"].lower() for t in ("char","text","enum","varchar")):
                            try:
                                dv = conn.execute(text(f"SELECT DISTINCT {self._q(c['name'])} FROM {self._q(tbl)} LIMIT 12")).fetchall()
                                vals = [row[0] for row in dv if row[0] is not None]
                                if 0 < len(vals) <= 8: low_card[c["name"]] = vals
                            except Exception as e:
                                logger.warning("Error fetching distinct values for %s.%s: %s", tbl, c["name"], e)

                schema[tbl] = {"columns": columns, "foreign_keys": fks, "sample_rows": samples,
                               "row_count": rc, "distinct_values": low_card}
        self._schema_cache = schema
        return schema

    def schema_as_text(self):
        schema = self.get_schema()
        lines = [f"Database dialect: {self.dialect}"]
        for tbl, info in schema.items():
            rc = f"  (~{info['row_count']} rows)" if info["row_count"] is not None else ""
            lines.append(f"\nTABLE {tbl}{rc}")
            fk_map = {fk["column"]:fk["references"] for fk in info.get("foreign_keys",[]) if fk.get("column")}
            for c in info["columns"]:
                flags = " PK" if c.get("primary_key") else ""
                if c["name"] in fk_map: flags += f"->{fk_map[c['name']]}"
                dv = info["distinct_values"].get(c["name"])
                dv_str = f"[{','.join(str(v) for v in dv[:6])}]" if dv else ""
                lines.append(f"  {c['name']} {c['type']}{flags}{dv_str}")
            if info["sample_rows"]:
                lines.append(f"  sample: {info['sample_rows'][:1]}")
        return "\n".join(lines)

    def execute(self, sql):
        cleaned = sql.strip().rstrip(";").strip()
        if self.readonly:
            first = cleaned.split()[0].upper() if cleaned else ""
            if first not in ("SELECT","WITH","EXPLAIN"):
                return {"error":"Only SELECT queries are allowed (read-only mode).","sql":cleaned}
            if ";" in cleaned or WRITE_KEYWORDS.search(cleaned):
                return {"error":"Only read-only SELECT queries are allowed.","sql":cleaned}
        try:
            with self.engine.connect() as conn:
                res = conn.execute(text(cleaned))
                cols = list(res.keys())
                raw = res.fetchmany(self.max_rows + 1)
                truncated = len(raw) > self.max_rows
                rows = []
                for row in raw[:self.max_rows]:
                    d = {}
                    for c,v in zip(cols, row):
                        d[c] = v.isoformat() if hasattr(v,"isoformat") else v
                    rows.append(d)
                return {"columns":cols,"rows":rows,"row_count":len(rows),
                        "truncated":truncated,"sql":cleaned}
        except SQLAlchemyError as e:
            return {"error":str(e),"sql":cleaned}
