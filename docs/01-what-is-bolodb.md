# 1. What is BoloDB?

**BoloDB lets you talk to your database in plain English.**

It is a multi-tenant web application. You sign up for an account, create or join a workspace, connect a database (PostgreSQL, MySQL, SQLite, SQL Server, DuckDB), and then instead of writing SQL you just ask questions the way you'd ask a colleague:

> "How many orders were completed last month?"
>
> "Which product category brings in the most revenue?"

BoloDB translates the question into SQL using OpenRouter AI (deepseek/deepseek-v4-flash), runs it against your database, and shows you:

1. **The answer** — a table of results (and the raw SQL, one tap away). Many results also show a **chart** — the AI decides whether a bar, line, area, pie, or big-number visualization fits best.
2. **A restatement** — one plain sentence describing what was actually computed. This is how you check the AI understood you.
3. **A confidence badge** — High / Medium / Low, based on real signals (did the query run? does it match something you verified before?), not on the AI's self-assessment.

## The three promises

### 1. Your data is safe

- BoloDB opens your database in **read-only mode**. Every query is checked twice — once by parsing it into a syntax tree and rejecting anything that isn't a plain SELECT (code: `backend/app/database.py` → `_readonly_violation()`), and we recommend connecting with a read-only database account as a third layer.
- Database URLs are validated against an allowlist to **prevent SSRF attacks** — no localhost, no loopback, no cloud metadata endpoints (`backend/app/database.py` → `_validate_db_url()`).
- When the AI is asked to write SQL, it is sent your **question** plus context: the **database structure** (table and column names, keys), a few **sample values and sample rows** per table, your confirmed **glossary terms**, the **semantic catalog** (metrics, joins, synonyms, value maps), previously **verified question→SQL examples**, and the last couple of conversation turns. The prompt **never** includes bulk table contents, query results, or credentials. See chapter 3 for the exact prompt contents.
- Connection credentials saved to the workspace are **encrypted at rest** using Fernet symmetric encryption (`backend/app/pgdatabase/connections.py`).

### 2. You can trust the answers — and check them

Non-technical users can't audit SQL, so BoloDB gives you tools that don't require reading code:

- The **restatement** tells you in English what was computed.
- The **chart** gives you a visual check — if the bar chart looks reasonable, the SQL probably is too.
- The **Explain** feature can translate any SQL back into plain English (code: `backend/app/llm.py` → `explain_sql()`, exposed at the `/api/explain` endpoint).
- The **confidence badge** is computed from signals, not vibes (code: `backend/app/schema_link.py` → `compute_confidence()`).
- Broken SQL never silently produces a wrong answer: every generated query is validated against your real schema before it runs, and automatically repaired if it fails (code: `backend/app/repair.py`).

### 3. It gets better the more you use it

When you click **"Yes, correct"** on an answer, that question-and-SQL pair is saved into the workspace's knowledge base in PostgreSQL (code: `backend/app/pgdatabase/knowledge.py`). The next time you — or a teammate — asks something similar, BoloDB finds your verified example and includes it in the prompt, which is the single strongest accuracy boost we have.

## Accounts, workspaces, and permissions

BoloDB is a **multi-tenant** application:

- **Sign up** with email/password or Google OAuth.
- Create or join **workspaces**. Each workspace has its own databases, knowledge base, dashboards, and members.
- Each member has a **role**: *Owner*, *Admin*, or *Member*. Roles control fine-grained **permissions**: who can connect databases, who can manage the catalog, who can create dashboards, and more. See chapter 10 for the full permission matrix.

## What happens the first time you log in

1. **Sign up** — create an account (or continue with Google).
2. **Create or join a workspace** — workspaces are where your databases and knowledge live.
3. **Set up the AI** — paste an OpenRouter API key (get one at https://openrouter.ai/keys). Or if the workspace admin already configured it, skip this step.
4. **Connect a database** — or click *"Try with sample data"* to explore a realistic demo store.
5. **Confirm business terms** — BoloDB reads your schema and suggests business terms and their meanings. You confirm or correct them (`backend/app/llm.py` → `suggest_catalog()`).
6. **Verify starter questions** — BoloDB proposes example questions with answers; each one you confirm seeds the knowledge base (`backend/app/llm.py` → `generate_starters()`).

After onboarding you land in the chat screen and just ask.

## The cast of components (30-second architecture)

```text
 Browser (SvelteKit frontend, frontend/src)
    │  HTTP calls to /api/... (JWT cookie auth)
    ▼
 FastAPI backend (backend/app)
    │
    ├── controllers/query.py ─── the question→answer pipeline (the heart)
    ├── llm.py ───────────────── the ONLY file that talks to OpenRouter
    ├── schema_link.py ───────── picks which tables the AI sees
    ├── sqlvalidate.py ───────── checks generated SQL against the real schema
    ├── repair.py ────────────── auto-fixes SQL that fails, with AI feedback
    ├── database.py ──────────── connects to YOUR database, read-only execution
    ├── pgdatabase/knowledge.py ─ remembers verified answers + glossary (PostgreSQL)
    └── auth routes ──────────── JWT auth, Google OAuth, email verification
           PostgreSQL ────────── users, workspaces, knowledge, dashboards, history
```

### Services layer

```text
 Workspace ────────── has members with roles and permissions
    │
    ├── Database connection ─── keyed per workspace+db_id
    │       └── Schema introspection → schema_link → prompt
    │
    ├── Knowledge (PostgreSQL) ─ verified Q&A, glossary, catalog
    │
    ├── Saved queries ───────── queries saved for reuse
    │
    ├── Dashboards ──────────── panels with ECharts visualizations
    │
    └── Activity log ────────── append-only audit trail
```

The next chapter walks a single question through this whole pipeline with
exact code pointers at every step.
