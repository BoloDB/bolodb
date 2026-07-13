"""Per-database knowledge base: verified Q->SQL pairs, glossary, trust."""

import sqlite3
import threading
import time
from difflib import SequenceMatcher
from pathlib import Path

from backend.app.i18n.translator import _
from backend.app.utils import _tokens


def _similarity(a, b, tb=None, b_lower=None):
    ta = _tokens(a)
    if tb is None:
        tb = _tokens(b)
    jacc = len(ta & tb) / len(ta | tb) if ta or tb else 0.0
    if b_lower is None:
        b_lower = b.lower()
    seq = SequenceMatcher(None, a.lower(), b_lower).ratio()
    return 0.6 * jacc + 0.4 * seq


class KnowledgeBase:
    def __init__(self, db_path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db_path = str(db_path)
        self._local = threading.local()
        self._init_schema()

    def _get_conn(self):
        """Return a thread-local SQLite connection, creating one if needed."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_schema(self):
        conn = self._get_conn()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS verified (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, question TEXT NOT NULL,
                sql TEXT NOT NULL, restatement TEXT, created_at REAL);
            CREATE TABLE IF NOT EXISTS glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, term TEXT, maps_to TEXT, sql_hint TEXT);
            -- Semantic catalog (issue #90): a curated per-database catalog that
            -- maps business language to schema entities, filters and joins.
            CREATE TABLE IF NOT EXISTS column_descriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, table_name TEXT NOT NULL,
                column_name TEXT NOT NULL, description TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS metric_definitions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, name TEXT NOT NULL,
                description TEXT, sql_expression TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS join_paths (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, tables TEXT NOT NULL,
                join_condition TEXT NOT NULL, description TEXT);
            CREATE TABLE IF NOT EXISTS synonyms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, term TEXT NOT NULL,
                entity_type TEXT NOT NULL, entity_name TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS value_mappings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, table_name TEXT NOT NULL,
                column_name TEXT NOT NULL, db_value TEXT NOT NULL,
                business_label TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS ix_v ON verified(db_id);
            CREATE INDEX IF NOT EXISTS ix_g ON glossary(db_id);
            CREATE INDEX IF NOT EXISTS ix_cd ON column_descriptions(db_id);
            CREATE INDEX IF NOT EXISTS ix_md ON metric_definitions(db_id);
            CREATE INDEX IF NOT EXISTS ix_jp ON join_paths(db_id);
            CREATE INDEX IF NOT EXISTS ix_sy ON synonyms(db_id);
            CREATE INDEX IF NOT EXISTS ix_vm ON value_mappings(db_id);
        """
        )
        conn.commit()

    def add_verified(self, db_id, question, sql, restatement=""):
        conn = self._get_conn()
        tb = _tokens(question)
        b_lower = question.lower()
        for e in self.get_verified(db_id):
            if _similarity(e["question"], question, tb, b_lower) > 0.92:
                return
        conn.execute(
            "INSERT INTO verified(db_id,question,sql,restatement,created_at) VALUES(?,?,?,?,?)",
            (db_id, question, sql, restatement, time.time()),
        )
        conn.commit()

    def get_verified(self, db_id):
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT question,sql,restatement FROM verified WHERE db_id=? ORDER BY created_at DESC",
            (db_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_verified(self, db_id):
        conn = self._get_conn()
        return conn.execute(
            "SELECT COUNT(*) FROM verified WHERE db_id=?", (db_id,)
        ).fetchone()[0]

    def retrieve_similar(self, db_id, question, k=3, threshold=0.25):
        scored = []
        tb = _tokens(question)
        b_lower = question.lower()
        for c in self.get_verified(db_id):
            s = _similarity(c["question"], question, tb, b_lower)
            if s >= threshold:
                scored.append({**c, "similarity": round(s, 3)})
        scored.sort(key=lambda x: -x["similarity"])
        return scored[:k]

    def set_glossary(self, db_id, terms):
        conn = self._get_conn()
        conn.execute("DELETE FROM glossary WHERE db_id=?", (db_id,))
        for t in terms:
            conn.execute(
                "INSERT INTO glossary(db_id,term,maps_to,sql_hint) VALUES(?,?,?,?)",
                (db_id, t.get("term", ""), t.get("maps_to", ""), t.get("sql_hint", "")),
            )
        conn.commit()

    def get_glossary(self, db_id):
        conn = self._get_conn()
        return [
            dict(r)
            for r in conn.execute(
                "SELECT term,maps_to,sql_hint FROM glossary WHERE db_id=?", (db_id,)
            ).fetchall()
        ]

    # ── Semantic catalog (issue #90) ─────────────────────────────────
    #
    # The catalog is a dict with these five lists (all optional):
    #   column_descriptions: {table, column, description}
    #   metrics:             {name, description, sql_expression}
    #   joins:               {tables, join_condition, description}
    #   synonyms:            {term, entity_type, entity_name}
    #   value_maps:          {table, column, db_value, business_label}
    # It is stable per connected database, so it is cheap to read on every
    # query and ideal to feed into schema linking and the generation prompt.

    _CATALOG_TABLES = {
        "column_descriptions": (
            "column_descriptions",
            ("table_name", "column_name", "description"),
            ("table", "column", "description"),
        ),
        "metrics": (
            "metric_definitions",
            ("name", "description", "sql_expression"),
            ("name", "description", "sql_expression"),
        ),
        "joins": (
            "join_paths",
            ("tables", "join_condition", "description"),
            ("tables", "join_condition", "description"),
        ),
        "synonyms": (
            "synonyms",
            ("term", "entity_type", "entity_name"),
            ("term", "entity_type", "entity_name"),
        ),
        "value_maps": (
            "value_mappings",
            ("table_name", "column_name", "db_value", "business_label"),
            ("table", "column", "db_value", "business_label"),
        ),
    }

    def set_catalog(self, db_id, catalog):
        """Replace the whole catalog for a database.

        Each of the five categories present in ``catalog`` is cleared and
        re-inserted; a category absent from ``catalog`` is left untouched, so
        callers can save one section at a time.
        """
        conn = self._get_conn()
        for key, (table, cols, in_keys) in self._CATALOG_TABLES.items():
            if key not in catalog:
                continue
            conn.execute(f"DELETE FROM {table} WHERE db_id=?", (db_id,))
            placeholders = ",".join(["?"] * (len(cols) + 1))
            col_list = ",".join(("db_id", *cols))
            for entry in catalog[key] or []:
                values = (db_id, *(str(entry.get(k, "") or "") for k in in_keys))
                conn.execute(
                    f"INSERT INTO {table}({col_list}) VALUES({placeholders})", values
                )
        conn.commit()

    def get_catalog(self, db_id):
        """Return the full catalog for a database as a dict of five lists."""
        conn = self._get_conn()
        out = {}
        for key, (table, cols, out_keys) in self._CATALOG_TABLES.items():
            rows = conn.execute(
                f"SELECT {','.join(cols)} FROM {table} WHERE db_id=?", (db_id,)
            ).fetchall()
            out[key] = [{ok: r[c] for c, ok in zip(cols, out_keys)} for r in rows]
        return out

    def catalog_is_empty(self, db_id):
        """True when no catalog entry of any kind exists for this database."""
        catalog = self.get_catalog(db_id)
        return not any(catalog.values())

    def trust_level(self, db_id):
        n = self.count_verified(db_id)
        if n >= 7:
            return {
                "level": _("Trusted"),
                "verified": n,
                "pct": 100,
                "note": _("Answers shown directly; reasoning on tap."),
            }
        if n >= 3:
            return {
                "level": _("Assisted"),
                "verified": n,
                "pct": 55,
                "note": _("Confident answers shown; novel ones get a second look."),
            }
        return {
            "level": _("Supervised"),
            "verified": n,
            "pct": max(8, n * 7),
            "note": _("Every answer waits for your confirmation while it learns."),
        }
