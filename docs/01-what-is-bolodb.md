# 1. What is BoloDB?

**BoloDB lets you talk to your database in plain English.**

You connect a database (PostgreSQL, MySQL, SQLite, SQL Server, DuckDB), and
then instead of writing SQL — the technical language databases understand —
you just ask questions the way you'd ask a colleague:

> "How many orders were completed last month?"
>
> "Which product category brings in the most revenue?"

BoloDB translates the question into SQL using OpenRouter AI, runs it
against your database, and shows you:

1. **The answer** — a table of results (and the raw SQL, one tap away).
2. **A restatement** — one plain sentence describing what was actually
   computed, e.g. *"Count of orders with status 'completed' created in the
   previous calendar month."* This is how you check the AI understood you.
3. **A confidence badge** — High / Medium / Low, based on real signals
   (did the query run? does it match something you verified before?), not on
   the AI's self-assessment.

## The three promises

### 1. Your data is safe

- BoloDB opens your database in **read-only mode**. Every query is checked
  twice — once by parsing it into a syntax tree and rejecting anything that
  isn't a plain SELECT (code: `backend/app/database.py` →
  `_readonly_violation()`), and we recommend connecting with a read-only
  database account as a third layer.
- When the AI is asked to write SQL, it is sent your **question** plus the
  context BoloDB builds around it: the **database structure** (table and
  column names, keys), a few **sample values and sample rows** per table (so
  the AI matches your wording to real data), your confirmed **glossary
  terms**, previously **verified question→SQL examples**, and the last couple
  of conversation turns. The prompt **never** includes bulk table contents,
  query results, or credentials — your OpenRouter API key is used only as the
  request's authentication header. See chapter 3 for the exact prompt
  contents.

### 2. You can trust the answers — and check them

Non-technical users can't audit SQL, so BoloDB gives you tools that don't
require reading code:

- The **restatement** (above) tells you in English what was computed.
- The **Explain** feature can translate any SQL back into plain English
  (code: `backend/app/llm.py` → `explain_sql()`, exposed at the
  `/api/explain` endpoint).
- The **confidence badge** is computed from signals, not vibes (code:
  `backend/app/schema_link.py` → `compute_confidence()`).
- Broken SQL never silently produces a wrong answer: every generated query is
  validated against your real schema before it runs, and automatically
  repaired if it fails (code: `backend/app/repair.py`).

### 3. It gets better the more you use it

When you click **"Yes, correct"** on an answer, that question-and-SQL pair is
saved into a local knowledge base (code: `backend/app/knowledge.py`). The next
time you — or a colleague — asks something similar, BoloDB shows the AI your
verified example, which is the single strongest accuracy boost we have. Your
trust level climbs from *Supervised* → *Assisted* → *Trusted* as you verify
more answers.

## What happens the first time you connect (onboarding)

1. **Set up the AI** — paste a free OpenRouter API key
   (get one at https://aistudio.google.com/app/api-keys). Screen:
   `frontend/src/lib/components/ConnectScreen.svelte`.
2. **Connect a database** — or click *"Try with sample data"* to explore a
   realistic demo store database (`backend/sample_data.py`).
3. **Confirm business terms** — BoloDB reads your schema and guesses the 3
   most important business terms ("revenue", "active customer"...) and what
   they mean in *your* database. You confirm or correct them. (Code:
   `backend/app/llm.py` → `generate_glossary()`.)
4. **Verify starter questions** — BoloDB proposes 3 example questions with
   answers; each one you confirm seeds the knowledge base. (Code:
   `backend/app/llm.py` → `generate_starters()`.)

After onboarding you land in the chat screen
(`frontend/src/lib/components/AskScreen.svelte`) and just ask.

## The cast of components (30-second architecture)

```text
 Browser (SvelteKit frontend, frontend/src)
    │  HTTP calls to /api/...
    ▼
 FastAPI backend (backend/app)
    │
    ├── controllers/query.py ── the question→answer pipeline (the heart)
    ├── llm.py ──────────────── the ONLY file that talks to OpenRouter
    ├── schema_link.py ──────── picks which tables the AI sees
    ├── sqlvalidate.py ──────── checks generated SQL against the real schema
    ├── repair.py ───────────── auto-fixes SQL that fails, with AI feedback
    ├── database.py ─────────── connects to YOUR database, read-only execution
    ├── knowledge.py ────────── remembers verified answers + glossary (SQLite)
    └── config.py ───────────── settings: OpenRouter key + model (~/.bolodb/)
```

The next chapter walks a single question through this whole pipeline with
exact code pointers at every step.
