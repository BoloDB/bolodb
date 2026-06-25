"""Per-database knowledge base: verified Q->SQL pairs, glossary, trust."""
import sqlite3
import time
from difflib import SequenceMatcher
from pathlib import Path

from backend.app.utils import _tokens

def _similarity(a, b, tb=None, b_lower=None):
    ta = _tokens(a)
    if tb is None:
        tb = _tokens(b)
    jacc = len(ta & tb) / len(ta | tb) if ta or tb else 0.0
    if b_lower is None:
        b_lower = b.lower()
    seq  = SequenceMatcher(None, a.lower(), b_lower).ratio()
    return 0.6 * jacc + 0.4 * seq

class KnowledgeBase:
    def __init__(self, db_path):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init()

    def _init(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS verified (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, question TEXT NOT NULL,
                sql TEXT NOT NULL, restatement TEXT, created_at REAL);
            CREATE TABLE IF NOT EXISTS glossary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                db_id TEXT NOT NULL, term TEXT, maps_to TEXT, sql_hint TEXT);
            CREATE INDEX IF NOT EXISTS ix_v ON verified(db_id);
            CREATE INDEX IF NOT EXISTS ix_g ON glossary(db_id);
        """)
        self.conn.commit()

    def add_verified(self, db_id, question, sql, restatement=""):
        tb = _tokens(question)
        b_lower = question.lower()
        for e in self.get_verified(db_id):
            if _similarity(e["question"], question, tb, b_lower) > 0.92: return
        self.conn.execute(
            "INSERT INTO verified(db_id,question,sql,restatement,created_at) VALUES(?,?,?,?,?)",
            (db_id, question, sql, restatement, time.time()))
        self.conn.commit()

    def get_verified(self, db_id):
        rows = self.conn.execute(
            "SELECT question,sql,restatement FROM verified WHERE db_id=? ORDER BY created_at DESC",
            (db_id,)).fetchall()
        return [dict(r) for r in rows]

    def count_verified(self, db_id):
        return self.conn.execute("SELECT COUNT(*) FROM verified WHERE db_id=?", (db_id,)).fetchone()[0]

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
        self.conn.execute("DELETE FROM glossary WHERE db_id=?", (db_id,))
        for t in terms:
            self.conn.execute(
                "INSERT INTO glossary(db_id,term,maps_to,sql_hint) VALUES(?,?,?,?)",
                (db_id, t.get("term",""), t.get("maps_to",""), t.get("sql_hint","")))
        self.conn.commit()

    def get_glossary(self, db_id):
        return [dict(r) for r in self.conn.execute(
            "SELECT term,maps_to,sql_hint FROM glossary WHERE db_id=?", (db_id,)).fetchall()]

    def trust_level(self, db_id):
        n = self.count_verified(db_id)
        if n >= 7: return {"level":"Trusted",  "verified":n,"pct":100,
            "note":"Answers shown directly; reasoning on tap."}
        if n >= 3: return {"level":"Assisted", "verified":n,"pct":55,
            "note":"Confident answers shown; novel ones get a second look."}
        return      {"level":"Supervised","verified":n,"pct":max(8,n*7),
            "note":"Every answer waits for your confirmation while it learns."}
