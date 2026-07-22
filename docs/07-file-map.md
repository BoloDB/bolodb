# 7. File map — what lives where

Use this as an index: find the thing you care about, open the file next to it.

## Backend (`backend/`) — Python, FastAPI

### Entry points

| File | What it does |
|---|---|
| `backend/main.py` | Command-line entry point. Parses `--db/--port/...`, warns if no OpenRouter key is configured, starts the web server. |
| `backend/app/server.py` | Builds the FastAPI app: creates the shared objects (config, provider manager, database manager, knowledge base, session log) and mounts all routes. |
| `backend/sample_data.py` | Builds the "Try with sample data" demo database (TechStore e-commerce). |

### The AI + question pipeline (the heart of the product)

| File | What it does |
|---|---|
| `backend/app/llm.py` | **The only file that talks to an AI.** `OpenRouterProvider` (HTTP calls, retries, error taxonomy), the prompt builders, and the four AI operations: `generate_sql`, `explain_sql`, `generate_glossary`, `generate_starters`. → [chapter 3](03-the-ai-layer-openrouter.md) |
| `backend/app/schema_link.py` | Scores tables against the question and picks which ones the AI sees (`link_relevant_tables`), renders them compactly (`compact_schema`), sets per-model budgets (`model_budget`), computes the confidence badge (`compute_confidence`). → [chapter 4](04-schema-linking.md) |
| `backend/app/sqlvalidate.py` | Static validation: parses generated SQL and checks every table/column against the real schema before execution. → [chapter 5](05-safety-validation-and-self-repair.md) |
| `backend/app/repair.py` | The generate→validate→execute→repair loop that auto-fixes broken SQL by feeding the exact error back to the AI. → [chapter 5](05-safety-validation-and-self-repair.md) |
| `backend/app/knowledge.py` | The local knowledge base (SQLite): verified Q→SQL answers, glossary, similarity retrieval, trust level. → [chapter 6](06-learning-trust-and-confidence.md) |
| `backend/app/database.py` | Connects to *your* database (SQLAlchemy), introspects the schema (tables, columns, keys, sample values, row counts), and executes queries with the read-only guard. |
| `backend/app/config.py` | Settings on disk (`~/.bolodb/config.json`): OpenRouter model + API key, allowed model list, migration from pre-OpenRouter configs, `OPENROUTER_API_KEY` env fallback. |
| `backend/app/utils.py` | `_tokens()` — the cached word tokenizer used by schema linking and similarity scoring. |

### HTTP layer

Routes (`backend/app/routes/`) are thin — they parse the request and call a
controller (`backend/app/controllers/`) where the logic lives.

| Route file | Endpoints | Controller |
|---|---|---|
| `routes/query.py` | `POST /api/query` (ask a question), `/api/feedback`, `/api/verify`, `/api/execute` (raw SQL), `/api/explain` (SQL → English) | `controllers/query.py` — **`run_query()` is the whole pipeline** |
| `routes/system.py` | `GET /api/state`, `GET /api/health`, `POST /api/config` (model + API key) | `controllers/system.py` |
| `routes/database.py` | `/api/connect`, `/api/connect-sample`, `/api/reconnect`, `/api/disconnect`, `/api/schema` | `controllers/database.py` |
| `routes/onboard.py` | `/api/onboard/glossary`, `/api/onboard/starters`, `/api/onboard/save` | `controllers/onboard.py` |
| `routes/auth.py` | signup/login/logout/refresh/me/change-password (JWT) | `controllers/auth.py` |
| `routes/history.py` | `GET/DELETE /api/history` (per-user query history) | `controllers/history.py` |
| `routes/connections.py` | `GET/DELETE /api/connections` (recent databases) | `controllers/connections.py` |

### Support

| File | What it does |
|---|---|
| `backend/app/dependencies.py` | FastAPI dependency injection: current user from JWT, shared app-state objects. |
| `backend/app/models/api.py` | Request body shapes (pydantic): `QueryReq`, `ConfigUpdate`, `ConnectReq`, ... |
| `backend/app/models/user.py` | User model for auth. |
| `backend/app/pgdatabase/` | PostgreSQL persistence: user accounts, query history, recent connections, conversations. |
| `backend/app/logbook.py` | Append-only session log (`~/.bolodb/sessions/*.jsonl`) of every query + feedback. |

## Frontend (`frontend/src/`) — SvelteKit

| File | What it does |
|---|---|
| `routes/+page.svelte` | Marketing/landing page. |
| `routes/connect/+page.svelte` → `lib/components/ConnectScreen.svelte` | Step 1: OpenRouter API key setup. Step 2: connect a database (form/URL/sample) + recent databases. |
| `routes/onboard/+page.svelte` → `OnboardScreen.svelte`, `GlossaryStep.svelte`, `StartersStep.svelte`, `ProfileStep.svelte` | First-time onboarding: confirm business terms, verify starter questions. |
| `routes/chat/+page.svelte` → `AskScreen.svelte` | The main chat screen: input, answer feed, sidebar. |
| `lib/components/AnswerCard.svelte` | One answer: restatement, results table, SQL toggle, confidence badge, verify buttons. |
| `lib/components/Sidebar.svelte` | Schema browser, history, trust meter, engine indicator (OpenRouter), Settings button. |
| `lib/components/Settings.svelte` | OpenRouter model picker + API key management. |
| `lib/appState.svelte.ts` | Global client state: engine/model, connection info, trust count, navigation flow. |
| `lib/api.ts` | `apiCall()` — fetch wrapper with auth handling. |
| `lib/data.ts` | Static data: the OpenRouter provider entry, trust-level definitions, demo schema, human-friendly error translations (`humanError`). |
| `lib/types.ts` | TypeScript interfaces shared across components. |

## Tests (`tests/`)

| File | Covers |
|---|---|
| `tests/test_openrouter.py` | OpenRouterProvider: request shape, structured output, retries, error taxonomy, health check (fake HTTP — no network). |
| `tests/test_query_pipeline.py` | `run_query()` end-to-end with fakes: repair-on-validation-failure, repair-on-execution-error, failure paths. Proves bad SQL never reaches the database. |
| `tests/test_schema_link.py` | Table scoring, plural matching, glossary expansion, FK/junction expansion, budgets, confidence rules. |
| `tests/test_repair.py` | The repair loop in isolation: feedback content, iteration/time bounds. |
| `tests/test_sqlvalidate.py` | Static SQL validation against a schema. |
| `tests/test_structured_output.py` | The JSON output contract (`SQL_SCHEMA`) and tolerant parsing. |
| `tests/test_llm.py` | `parse_json` fence/noise stripping. |
| `tests/test_config.py` | Config defaults, old-config migration, env-var key fallback, secret never exposed. |
| `tests/test_database.py`, `test_database_controller.py` | Read-only guard, connection handling. |
| `tests/test_knowledge.py` | Knowledge base storage + similarity retrieval. |
| `tests/test_history.py` | History endpoints. |

Run them all: `pytest tests` from the repository root (install
`backend/requirements.txt` first).

## Everything else

| Path | What it is |
|---|---|
| `benchmarks/` | The Spider-based evaluation of schema-linking recall and end-to-end accuracy (`benchmarks/README.md` explains how to run it). |
| `docker-compose.yml`, `nginx/`, `*/DOCKERFILE*` | The Docker deployment: backend + frontend + nginx + PostgreSQL. |
| `data/` | Drop SQLite/DuckDB files here to use them from Docker (`/app/data/...`). |
| `.github/workflows/` | CI (tests/lint), CodeQL, OpenRouter-powered PR review bots. |
| `docs/` | These documents. |
