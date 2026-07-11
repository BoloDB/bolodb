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
| `lite` (gemini-2.5-flash-lite) | 12 | 1 | 3 |
| `flash` (default) | 20 | 2 | 5 |
| `pro` | 25 | 2 | 5 |

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

## Current limitation: the 40-table introspection cap

Schema linking can only rank tables that introspection collected, and
`get_schema()` (`backend/app/database.py`, constant `MAX_T`) currently stops
at the **first 40 tables**. On a database larger than that, tables beyond the
cap are invisible to both scoring and the AI. The fix — collecting structure
for every table and capping only the expensive sampling — is implemented in
[PR #162](https://github.com/HAAHIT/bolodb/pull/162).

## Debugging: which tables were picked, and why?

- Every `/api/query` response includes `tables_used` — the exact list that
  was sent to the AI.
- Set the backend log level to DEBUG and `link_relevant_tables()` logs each
  question's selected tables **with their scores**.
- Tests demonstrating each behaviour: `tests/test_schema_link.py`
  (singular/plural, glossary expansion, FK parents, junction tables,
  context boosts, budgets).
