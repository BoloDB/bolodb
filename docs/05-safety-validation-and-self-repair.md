# 5. Safety, validation, and self-repair

AI-generated SQL fails in two ways: it can be **dangerous** (tries to change data) or **broken** (references non-existent columns, syntax errors). Furthermore, database connections must be protected against network exploits.

BoloDB handles safety and reliability through multiple defense-in-depth layers.

```text
 Database Connection Attempt
      │
      ▼
  [0] SSRF & Network Security ── host allowlist, loopback blocking   database.py
      │
 AI writes SQL
      │
      ▼
  ① Static validation  ──────── does every table/column exist?       sqlvalidate.py
      │ pass
      ▼
  ② Read-only guard    ──────── is this a pure SELECT statement?     database.py
      │ pass
      ▼
  ③ Exec & Statement Timeout ── 5s timeout & execution safety        database.py
      │ any failure at ①/③
      ▼
  ↻ Self-repair loop   ──────── feed exact error back to AI          repair.py
```

---

## Layer 0 — Network Security & SSRF Protection (`backend/app/database.py`)

**Function:** `_validate_db_url(db_url)`

Before a database connection is established, the target URL undergoes strict Server-Side Request Forgery (SSRF) validation:
- **Loopback & Private Address Blocking**: Requests targeting `localhost`, `127.0.0.1`, `0.0.0.0`, `::1`, or link-local / cloud metadata IPs (`169.254.169.254`) are strictly blocked.
- **Host Allowlisting**: Connection hosts are validated to prevent internal infrastructure scanning.
- **Encrypted Credentials at Rest**: Connection details stored in PostgreSQL are encrypted using Fernet symmetric keys (`backend/app/pgdatabase/connections.py`).

---

## Layer ① — Static validation (`backend/app/sqlvalidate.py`)

**Function:** `validate_sql(sql, schema, dialect)`

Before generated SQL touches your database, it is parsed into a syntax tree (using `sqlglot`) and every table and column referenced is checked against your *actual* schema. This catches column hallucinations instantly:

> `Unknown column: 'revenue' does not exist in table 'orders'.`

The validator is deliberately conservative: it only complains when certain something is wrong. Columns coming from CTEs, subqueries, or aliases are preserved.

---

## Layer ② — Read-only Guard (`backend/app/database.py`)

**Function:** `DatabaseManager._readonly_violation()`, called from `execute()` on **every** query.

Enforced on the parsed syntax tree:
- Single statement restriction (blocks stacked queries like `SELECT ...; DROP ...`).
- Statement root must be `SELECT`, `UNION`, or `EXPLAIN`.
- **No modifying node anywhere in the tree** — catches mutations inside CTEs (`WITH x AS (DELETE ...)`).
- Blocked node types: `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `CREATE`, `TRUNCATE`, `SELECT INTO`.
- Keyword fallback blocklist if AST parsing fails.

---

## Layer ③ — Execution Safety & Statement Timeout

**Function:** `_apply_statement_timeout(engine, dialect)` in `backend/app/database.py`.

- **Statement Timeouts**: Every connection applies statement timeouts (e.g., `SET statement_timeout = 5000` on PostgreSQL / MySQL `max_execution_time`) to prevent runaway long-running queries from overwhelming the target database.
- **Row Caps**: Execution results are capped at 500 rows (`max_rows`) to prevent memory exhaustion.
- **Error Recycling**: Execution errors are returned cleanly to supply fuel for self-repair.

---

## Layer ↻ — Self-Repair Loop (`backend/app/repair.py`)

**Function:** `run_repair_loop()`

When static validation (Layer ①) or database execution (Layer ③) fails:
1. BoloDB constructs a targeted correction prompt (`_feedback()`).
2. The exact error message is fed back to OpenRouter in `generate_sql(..., feedback=...)`.
3. **Schema-retry**: If the failed SQL references a real table that schema linking missed, that table is added to the context prompt for the next attempt.
4. **Limits**: Maximum 3 attempts, with a hard 60-second total execution deadline.
