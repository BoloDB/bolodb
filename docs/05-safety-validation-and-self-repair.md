# 5. Safety, validation and self-repair

AI-generated SQL fails in two ways: it can be **dangerous** (tries to change
data) or **broken** (references things that don't exist, wrong syntax).
BoloDB handles both with three independent layers. Each layer lives in its
own file and is separately tested.

```text
 AI writes SQL
      │
      ▼
 ① Static validation  — does every table/column actually exist?   sqlvalidate.py
      │ pass
      ▼
 ② Read-only guard    — is this a pure SELECT? nothing else runs  database.py
      │ pass
      ▼
 ③ Execution          — did the database accept it?               database.py
      │ any failure at ①/③
      ▼
 ↻ Self-repair loop   — feed the exact error back to the AI       repair.py
```

## Layer ① — Static validation (`backend/app/sqlvalidate.py`)

**Function:** `validate_sql(sql, schema, dialect)`

Before generated SQL goes anywhere near your database, it is parsed into a
syntax tree (using the `sqlglot` library) and every table and column it
references is checked against your *actual* schema. This catches the most
common AI mistake — confidently inventing a column:

> `Unknown column: 'revenue' does not exist in table 'orders'.`

That sentence is not just an error — it's written to be **fed back to the AI**
so it can fix itself (see layer ↻ below).

Design principle stated at the top of the file: the validator is deliberately
*conservative*. It only complains when it is certain something is wrong
(unknown table, unknown column on a known table). Columns that might come
from a subquery or CTE are left alone — a false rejection of valid SQL would
be worse than missing an error, because execution (layer ③) is the final
backstop anyway.

Tests: `tests/test_sqlvalidate.py`.

## Layer ② — The read-only guard (`backend/app/database.py`)

**Function:** `DatabaseManager._readonly_violation()`, called from
`execute()` on **every** query — including raw SQL a user runs directly via
`/api/execute`.

The rules, enforced on the parsed syntax tree (not just text matching):

- Only a single statement (no stacked `SELECT …; DROP …`).
- The statement root must be SELECT / UNION / EXPLAIN.
- **No modifying node anywhere in the tree** — this catches sneaky cases
  like a DELETE hidden inside a CTE (`WITH x AS (DELETE …)`). The node
  blocklist is `_MODIFYING_NODES`.
- `SELECT … INTO` (which creates a table) is blocked explicitly.
- If the SQL can't even be parsed, a conservative keyword blocklist
  (`WRITE_KEYWORDS`) rejects anything suspicious instead of running it
  blindly.

On top of this, results are capped at 500 rows (`max_rows`) and the README
recommends connecting with a read-only database account — defense in depth.

Tests: `tests/test_database.py`.

## Layer ③ — Execution errors become repair fuel

If the database itself rejects the query (syntax quirk, type error, missing
extension), `execute()` returns `{"error": "<the database's message>"}`
rather than raising — so the error text can be recycled by the repair loop.

## Layer ↻ — The self-repair loop (`backend/app/repair.py`)

**Function:** `run_repair_loop(generate, validate, execute, …)` — wired into
the live pipeline in `backend/app/controllers/query.py` → `run_query()`.

The insight: most wrong SQL is wrong *mechanically*, and the AI can fix it
instantly **if you tell it exactly what broke**. So instead of giving up on
the first failure:

1. Generate a candidate.
2. If validation (①) or execution (③) fails, build a correction prompt —
   `_feedback()` produces:

   ```text
   The previous SQL attempt was:
   SELECT revenue FROM orders
   Problems found:
   - Unknown column: 'revenue' does not exist in table 'orders'.
   Return a corrected SQL query that fixes these problems.
   ```

3. Ask again with that feedback appended (it flows into
   `generate_sql(..., feedback=...)` in `llm.py`).
4. Repeat — **at most 3 attempts total, and no new attempt starts after 60
   seconds** (constants `_MAX_ATTEMPTS` / `_MAX_SECONDS` in
   `controllers/query.py`), so a stubborn failure can't burn tokens or leave
   the user staring at a spinner forever.

What you see as a user: usually nothing — the answer just works. The response
does carry the evidence: `attempts` (how many generations were needed) and
`repaired: true` if a fix happened mid-flight. If all attempts fail, you get
a Low-confidence answer with the final error in `execution_error` and a
suggestion to rephrase.

Tests: `tests/test_repair.py` (the loop in isolation),
`tests/test_query_pipeline.py` (the loop wired into the real pipeline —
including proof that invalid SQL **never reaches the database**).

## What still can't go wrong silently

- A query that runs but answers the *wrong question* is the one failure no
  validator can catch. That's what the plain-English **restatement**, the
  **assumptions list**, the **Explain** button and the **confidence badge**
  are for — they make it easy for a human to spot. See
  [chapter 6](06-learning-trust-and-confidence.md).
