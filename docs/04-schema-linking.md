# 4. Schema linking — choosing which tables the AI sees

**File:** `backend/app/schema_link.py` · **Main function:** `link_relevant_tables()`

## Why not just send everything?

Two reasons, and they both matter:

1. **Cost.** Every table description in the prompt costs tokens on every
   single question. A 40-table schema sent 100 times a day adds up.
2. **Accuracy.** This is the counterintuitive one: irrelevant tables actively
   *hurt* the AI. Given 40 tables, the model is more likely to join the wrong
   ones or pick a similarly-named column from the wrong table. The research
   behind the Spider text-to-SQL benchmark (the academic gold standard for
   this problem) identified schema linking — matching question words to the
   right tables/columns, with special weight on primary/foreign keys — as the
   core skill separating good systems from bad ones.

So BoloDB sends the *few tables that matter*, plus whatever is needed to join
them.

## How a table earns its place — the scoring

Every table gets a score against the question. The weights are constants at
the top of `schema_link.py` (`_W_TABLE_NAME`, `_W_KEY_COLUMN`, …) so tuning
them is a one-line change:

| Signal | Weight | Example |
|---|---|---|
| Question word matches the **table name** | 3.0 per word | "show me all **orders**" → table `orders` |
| Question word matches a **key column** (primary key or foreign key) | 1.5 per word | "revenue by **customer**" → `orders.customer_id` |
| Question word matches an **ordinary column** | 1.0 per word | "sort by **price**" → `products.price` |
| Question word matches a **known cell value** | 2.0 per match | "**laptops**" → `products.category` contains `laptops` |
| Table appears in a **verified similar answer** | +5.0 | You confirmed a similar question before, and its SQL used this table |
| Table was used by the **previous query** in this conversation | +8.0 | "now filter this for 2023" keeps working on the same tables |
| Table was picked by the **LLM shortlist pass** (big schemas only) | +6.0 | See "Two-stage linking" below |

Implementation notes (all in `schema_link.py`):

- **Singular/plural matching.** "order" matches table `orders`, "categories"
  matches `category` — a tiny stemmer, `_stem()`, normalizes both sides.
- **Glossary expansion — but only when mentioned.** If your glossary says
  `revenue = sum of total_amount on completed orders`, then a question
  containing "revenue" also matches on "total_amount", "completed", "orders".
  Glossary terms *not* mentioned in the question add nothing — so unrelated
  business terms can't drag in unrelated tables. Code: `_question_stems()`.
- **Caps.** Column and value points are capped (`_MAX_COLUMN_POINTS`,
  `_MAX_VALUE_POINTS`) so a very wide table can't win on width alone.
- **Per-table scoring** lives in `_score_table()`; verified-answer detection
  in `_tables_in_verified_sql()`.

## After scoring: making the selection JOIN-able

Taking the top N scorers isn't enough — you might select `orders` and
`products` but drop the `order_items` table that connects them. So after
seeding with the top scorers (up to the budget), `link_relevant_tables()`
adds:

1. **Foreign-key parents** (`_fk_parents()`): every selected table's FK
   targets come along. If `orders.customer_id → customers.id`, then
   `customers` is included whenever `orders` is.
2. **Junction tables**: any table whose foreign keys point at **two or more
   selected tables** is included — that's the classic many-to-many bridge
   (`order_items` connecting `orders` and `products`).

FK expansion may add at most 4 tables beyond the budget
(`_FK_EXTRA_SLOTS`).

**Fallback:** if *nothing* matches (a very vague question), the largest
tables by row count are used — they're usually the fact tables questions end
up needing.

**Small databases skip all of this:** if the database has fewer tables than
the budget allows, every table is sent and no scoring happens (first lines of
`link_relevant_tables()`).

## The budget — how many tables are allowed

`model_budget()` in the same file. Bigger models handle more context well, so
they get more tables:

| Model tier | Max tables (before FK expansion) | Sample rows per table | Verified examples in prompt |
|---|---|---|---|
| `lite` (deepseek-v4-flash) | 12 | 1 | 3 |
| `flash` (default) | 20 | 2 | 5 |
| `pro` | 25 | 2 | 5 |

## Two-stage linking — big schemas get an AI assist

Word matching has a blind spot: a question about "clients" won't find a table
called `customers` unless the glossary or verified history bridges the gap.
On big databases (more than 30 tables — `_SHORTLIST_MIN_TABLES` in
`backend/app/controllers/query.py`), BoloDB adds a cheap first AI pass:

1. A **names-only catalog** of every table (`orders(id, customer_id, …)` — a
   few tokens per table even for hundreds of tables) is sent to OpenRouter with
   thinking disabled, asking "which tables might matter for this question?"
   *Code:* `backend/app/llm.py` → `shortlist_tables()`.
2. The picks come back into local scoring as a **+6 boost** — never as a
   replacement. If the call fails or the model picks nonsense (invented names
   are dropped), linking silently falls back to local-only scoring. The
   shortlist can only ever add signal, not remove it.

Small databases skip this entirely — local scoring alone is accurate there
and the extra call isn't worth the latency.

## Schema-retry — the AI as a linking-error detector

Even good scoring sometimes drops a table the question needed. The self-repair
loop (chapter 5) turns that miss into a one-round-trip fix:

- When a generated query **fails** (validation or execution), BoloDB parses
  the failed SQL for table names. If the model referenced a table that
  **really exists in the database** but wasn't shown to it, that's not a
  hallucination — it's the model telling us the linking missed something.
- The table (plus its FK parents) is added to the linked set, and the next
  repair attempt sees the widened schema.
- *Code:* `expand_linked_tables()` in `schema_link.py`, wired via the
  `on_failure` hook of `run_repair_loop` in `controllers/query.py` →
  `_on_failure()`. Additions show up in the response's `tables_used` and are
  logged as `schema-retry: added [...]`.

## How the whole database stays visible (introspection)

Schema linking can only pick from tables it can see. Introspection
(`backend/app/database.py` → `get_schema()`) therefore collects **structure —
columns and primary/foreign keys — for every table, however many there are**.
Only the expensive enrichment (sample rows, per-table row counts, known cell
values) is capped, at 40 tables (`ENRICH_MAX`), preferring the largest tables
when row counts are known. A 200-table database is fully linkable and fully
visible to the AI; the smallest 160 tables just don't carry example values.

## The output format the AI reads

`compact_schema()` renders each selected table as one dense line — far fewer
tokens than a CREATE TABLE statement, but everything the AI needs:

```text
orders(id PK, customer_id->customers.id, status[completed,pending,cancelled], total_amount, created_at) ~38104 rows
  e.g. {'id': 1, 'customer_id': 17, 'status': 'completed', ...}
```

Reading guide: `PK` = primary key · `->customers.id` = foreign key ·
`[completed,pending,…]` = actual values that occur in that column (collected
during schema introspection, `backend/app/database.py` → `get_schema()`, only
for small text columns) · `~38104 rows` = approximate size.

Those `[values]` matter more than they look: they're why the AI writes
`WHERE status = 'completed'` instead of guessing `WHERE status = 'complete'`.

## Debugging: which tables were picked, and why?

- Every `/api/query` response includes `tables_used` — the exact list that
  was sent to the AI.
- Set the backend log level to DEBUG and `link_relevant_tables()` logs each
  question's selected tables **with their scores**.
- Tests demonstrating each behaviour: `tests/test_schema_link.py`
  (singular/plural, glossary expansion, FK parents, junction tables,
  context boosts, budgets).
