# 2. How a question becomes an answer

This is the most important chapter: it follows **one question** through the
entire system, in order, with the exact code location for every step. If you
ever wonder "where does X happen?" or "why did I get this answer?", start here.

Our example question, asked against a demo e-commerce database:

> **"How much revenue did we make from laptops last month?"**

## Step 0 — The browser sends the question

You type into the chat screen and press *Ask*.

- **Where:** `frontend/src/lib/components/AskScreen.svelte` → the `ask()`
  function sends `POST /api/query` with the question, plus the previous couple
  of question/SQL pairs (so follow-up questions like "now just 2023" work).
- The request lands in `backend/app/routes/query.py` → `query()`, which calls
  the pipeline: `backend/app/controllers/query.py` → `run_query()`.

Everything below happens inside `run_query()`. The step numbers here match
the numbered comments in that function — you can read them side by side.

## Step 1 — Look up what BoloDB already knows

Two lookups against the local knowledge base (a small SQLite file at
`~/.bolodb/knowledge.db`, managed by `backend/app/knowledge.py`):

1. **Glossary** — the business terms you confirmed during onboarding.
   For our question, the glossary might contain
   `revenue = sum of total_amount on completed orders`.
   *Code:* `KnowledgeBase.get_glossary()`.
2. **Similar verified answers** — up to 3 previously-confirmed
   question→SQL pairs that resemble this question, found with a text
   similarity score (word overlap + sequence similarity).
   *Code:* `KnowledgeBase.retrieve_similar()`, scoring in `_similarity()`.

Both are later placed into the AI prompt: the glossary as ground-truth term
definitions, the verified answers as worked examples to imitate.

## Step 2 — Pick which tables the AI gets to see (schema linking)

A real database may have 40+ tables. Sending them all would cost more AND
confuse the AI. So BoloDB scores every table against the question and keeps
only the relevant ones.

- **Where:** `backend/app/schema_link.py` → `link_relevant_tables()`.
- For our question, tables named `orders`, `order_items`, `products` score
  high (name/column matches on "revenue"→glossary→"total_amount",
  "laptops" matches a known value of `products.category`), and tables like
  `employees` or `audit_log` score zero and are dropped.
- Foreign keys are then followed so the chosen tables can be JOINed
  (details in [chapter 4](04-schema-linking.md)).
- How many tables are allowed depends on the Gemini model configured —
  `model_budget()` in the same file.

The chosen tables are rendered into a compact text form the AI reads —
`compact_schema()` produces lines like:

```text
orders(id PK, customer_id->customers.id, status[completed,pending,cancelled], total_amount, created_at) ~38104 rows
```

## Step 3 — Generate, validate, execute — and self-repair if needed

This is the loop that actually produces the answer. **Where:**
`backend/app/repair.py` → `run_repair_loop()`, wired up in `run_query()`.

Each iteration (at most 3, and no new attempt after 60 seconds):

1. **Generate.** The Gemini AI is asked for the SQL.
   *Code:* `backend/app/llm.py` → `generate_sql()`; the exact prompt text is
   assembled in `build_sql_system_prompt()` in the same file — open it to see
   precisely what the AI is told. The AI must reply in a fixed JSON shape
   (`SQL_SCHEMA`): the SQL, a plain-English restatement, and any assumptions
   it made.
2. **Validate.** Before anything touches your database, the SQL is parsed
   and every table and column it mentions is checked against your real
   schema. A hallucinated column like `orders.revenue` is caught here.
   *Code:* `backend/app/sqlvalidate.py` → `validate_sql()`.
3. **Execute.** The query runs against your database — read-only, with the
   safety guard described in [chapter 5](05-safety-validation-and-self-repair.md).
   *Code:* `backend/app/database.py` → `DatabaseManager.execute()`.
4. **Repair (only if 2 or 3 failed).** The specific error — "Unknown column:
   'revenue' does not exist in table 'orders'" or the database's own error
   message — is appended to the question and the loop starts over. The AI
   sees exactly what broke and fixes it. *Code:* the feedback text is built
   by `_feedback()` in `repair.py`.

The response records how many attempts were needed (`attempts` field) and
whether a repair happened (`repaired`) — useful when debugging.

## Step 4 — Score confidence, log, and answer

- **Confidence** is computed from real signals — did the query run, did it
  return rows, and how closely does the question match something you already
  verified. *Code:* `backend/app/schema_link.py` → `compute_confidence()`.
  The exact thresholds are in [chapter 6](06-learning-trust-and-confidence.md).
- The query is **logged** to the session log (`backend/app/logbook.py`) and
  the per-user history (MongoDB, `backend/app/mongodatabase.py`, called from
  `routes/query.py`).
- The JSON response goes back to the browser, which renders it as an answer
  card: `frontend/src/lib/components/AnswerCard.svelte`.

## Step 5 — You give feedback (optional but powerful)

If you click **"Yes, correct"**, the browser calls `POST /api/feedback` →
`backend/app/controllers/query.py` → `feedback()`, which saves the
question+SQL into the knowledge base (`KnowledgeBase.add_verified()`).
From now on, similar questions retrieve this example in Step 1 and show
higher confidence in Step 4. This loop — ask, verify, improve — is the
product's core flywheel.

## The full picture

```text
 Question ─▶ [1] knowledge lookup      knowledge.py
             [2] schema linking        schema_link.py
             [3] generate ◀────┐       llm.py (Gemini)
                 validate      │       sqlvalidate.py
                 execute       │       database.py
                 (repair) ─────┘       repair.py
             [4] confidence + log      schema_link.py, logbook.py
 Answer  ◀── JSON: sql, restatement, rows, confidence, attempts
```

## What the response actually contains

`POST /api/query` returns (shape assembled at the end of `run_query()`):

| Field | Meaning |
|---|---|
| `sql` | The SQL that was run (empty if generation failed entirely) |
| `restatement` | One plain sentence describing what the query computes |
| `assumptions` | Assumptions the AI made (e.g. "interpreted 'last month' as the previous calendar month") |
| `columns`, `rows` | The results (max 500 rows; `truncated` is true if capped) |
| `confidence`, `confidence_reason` | High/Medium/Low + why |
| `based_on_verified` | Whether a previously verified answer informed this one |
| `tables_used` | Which tables schema linking selected |
| `attempts`, `repaired` | How many generation attempts were needed; whether a self-repair happened |
| `execution_error` | Present only if the final attempt still failed |
| `query_id` | Handle for feedback ("Yes, correct" / "Something's wrong") |
