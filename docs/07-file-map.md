# 7. File map — what lives where

Use this as an index: find the thing you care about, open the file next to it.

## Backend (`backend/`) — Python, FastAPI

### Entry points

| File | What it does |
|---|---|
| `backend/app/server.py` | Main FastAPI server entry point — builds the app (`create_app()`), initializes shared objects (config, ProviderManager, DatabaseManager, KnowledgeService, SessionLog), runs Alembic migrations at startup, mounts all route modules, applies CORS + rate limiting + body-limit middleware. |
| `backend/sample_data.py` | Builds the "Try with sample data" demo database (PostgreSQL webshop dataset). |

### The AI + question pipeline (the heart of the product)

| File | What it does |
|---|---|
| `backend/app/llm.py` | **The only file that talks to an AI model.** `OpenRouterProvider` (HTTP calls via openai SDK, retries, error taxonomy, streaming), the structured-output schemas (`SQL_SCHEMA`, `CHART_TYPES`), `suggest_catalog()`, and the AI operations: `generate_sql`, `explain_sql`, `suggest_catalog`, `generate_starters`. Now produces a `chart` spec alongside SQL. → [chapter 3](03-the-ai-layer-openrouter.md) |
| `backend/app/schema_link.py` | Scores tables against the question and picks which ones the AI sees (`link_relevant_tables`), renders them compactly (`compact_schema`), sets per-model budgets (`model_budget`), expands FK/junction tables (`expand_linked_tables`), computes the confidence badge (`compute_confidence`). → [chapter 4](04-schema-linking.md) |
| `backend/app/sqlvalidate.py` | Static validation: parses generated SQL and checks every table/column against the real schema before execution. → [chapter 5](05-safety-validation-and-self-repair.md) |
| `backend/app/repair.py` | The generate→validate→execute→repair loop that auto-fixes broken SQL by feeding the exact error back to the AI. → [chapter 5](05-safety-validation-and-self-repair.md) |
| `backend/app/controllers/query.py` | **`run_query()`** — orchestrates the whole pipeline: knowledge lookup → schema linking → generate/validate/execute/repair → confidence scoring → chart inference → logging. → [chapter 2](02-how-a-question-becomes-an-answer.md) |
| `backend/app/semantic.py` | Semantic catalog helpers: `suggest_from_schema()` derives joins and value maps from the schema, `merge_catalog_suggestions()` combines them with LLM enrichment, `filter_catalog()` scopes entries to linked tables. → [chapter 12](12-semantic-layer.md) |
| `backend/app/database.py` | `DatabaseManager` — connects to *your* database (SQLAlchemy), introspects schema (tables, columns, PKs, FKs, sample rows, row counts, distinct values), read-only guard via AST parsing, SSRF validation, statement timeout. Keyed per workspace+db_id. |
| `backend/app/config.py` | In-memory only. API key read from `OPENROUTER_API_KEY` env var. Activity log retention settings also live here. |
| `backend/app/utils.py` | `_tokens()` — the cached word tokenizer used by schema linking and similarity scoring. |

### Routes and controllers

Routes (`backend/app/routes/`) are thin — they parse the request, enforce permissions, and call a controller (`backend/app/controllers/`) where the logic lives.

| Route file | Endpoints | Controller |
|---|---|---|
| `routes/query.py` | `POST /api/query`, `POST /api/query/stream`, `/api/feedback`, `/api/verify`, `/api/execute`, `/api/explain` | `controllers/query.py` — `run_query()` is the whole pipeline |
| `routes/system.py` | `GET /api/health`, `GET /api/state`, `GET /api/config`, `POST /api/config`, `POST /api/tour-complete` | `controllers/system.py` |
| `routes/database.py` | `GET /api/databases`, `POST /api/connect`, `POST /api/connect-sample`, `POST /api/disconnect`, `GET /api/schema` | `controllers/database.py` |
| `routes/onboard.py` | `POST /api/onboard/save`, `POST /api/onboard/generate-starters` | `controllers/onboard.py` |
| `routes/auth.py` | `POST /api/auth/signup`, `/login`, `/logout`, `/refresh`, `/api/auth/me`, `/api/auth/change-password`, `/api/auth/supabase-google`, email verification, forgot password | `controllers/auth.py` |
| `routes/history.py` | `GET/DELETE /api/history` (per-user query history) | `controllers/query.py` |
| `routes/connections.py` | `GET/DELETE /api/connections` (recent databases, encrypted at rest) | `controllers/database.py` |
| `routes/catalog.py` | `GET /api/catalog`, `POST /api/catalog`, `POST /api/catalog/suggest` | `controllers/catalog.py` |
| `routes/conversations.py` | `GET/POST/PATCH/DELETE /api/conversations` | `controllers/conversations.py` |
| `routes/workspaces.py` | `GET/POST/PATCH/DELETE /api/workspaces`, invites, members | `controllers/workspaces.py` |
| `routes/dashboards.py` | `GET/POST/PATCH/DELETE /api/dashboards`, panel batch update | `controllers/dashboards.py` |
| `routes/saved_queries.py` | `GET/POST/DELETE /api/saved-queries` | `controllers/dashboards.py` |
| — | Activity logs controller | `controllers/activity.py` |

### Auth, permissions, and dependencies

| File | What it does |
|---|---|
| `backend/app/dependencies.py` | FastAPI dependency injection: `get_current_user` (JWT cookie), `get_current_workspace` (X-Workspace-Id header + membership check), `get_current_db_id` (X-Db-Id header), `require_role()`, `require_permission()`, `get_db()`, `get_kb()`, `get_providers()`, `get_cfg()`. |
| `backend/app/secrets.py` | Centralized secret management: `get_jwt_secret()`, `get_supabase_jwt_secret()`, `get_resend_api_key()`, `get_frontend_url()`, `get_cookie_secure()`. |
| `backend/app/permissions.py` | RBAC permission registry — 21 fine-grained capabilities across 7 resources (members, connections, catalog, dashboards, queries, activity, workspace_management). `resolve_role_permissions()`, `has_permission()`. |
| `backend/app/ratelimit.py` | Shared slowapi `Limiter` instance with X-Forwarded-For-aware client key. |

### PostgreSQL persistence (`backend/app/pgdatabase/`)

| File | What it does |
|---|---|
| `pgdatabase/engine.py` | Async SQLAlchemy engine and session factory. `get_engine()`, `DATABASE_URL` env var → `create_async_engine()`. `async_session`, `dispose_db()`. |
| `pgdatabase/knowledge.py` | `KnowledgeService` — verified Q&A storage, glossary, semantic catalog (column descriptions, metrics, joins, synonyms, value maps). All async, all PostgreSQL. `add_verified()`, `retrieve_similar()`, `get_glossary()`, `set_glossary()`, `get_catalog()`, `set_catalog()`. |
| `pgdatabase/users.py` | User CRUD: `create_user()`, `get_user_by_email()`, `update_user()`. |
| `pgdatabase/connections.py` | Recent connections with Fernet encryption at rest. `RECENT_CONNECTIONS_KEY` env var. `save_recent_connection()`, `get_recent_connections()`, `get_recent_connection_by_db_id()`. |
| `pgdatabase/conversations.py` | Conversation CRUD, scoped per workspace+user. |
| `pgdatabase/history.py` | Query history CRUD, scoped per workspace+user+db. |
| `pgdatabase/dashboards.py` | Dashboard and panel CRUD. |
| `pgdatabase/saved_queries.py` | Saved query CRUD. |
| `pgdatabase/otp.py` | One-time password/pin for invite acceptance. |
| `pgdatabase/serialization.py` | UUID helpers and serialization utilities. |

### Support & Models (`backend/app/models/`)

| File | What it does |
|---|---|
| `backend/app/models/api.py` | Pydantic request/response models: `QueryReq`, `ConfigUpdate`, `ConnectReq`, `FeedbackReq`, `VerifyReq`, etc. |
| `backend/app/models/workspace_api.py` | Pydantic request/response models for workspace API operations (workspace creation, updating, membership, permission matrix updates). |
| `backend/app/models/user.py` | User Pydantic model. |
| `backend/app/models/orm_user.py` | SQLAlchemy ORM User model. |
| `backend/app/models/workspace.py` | Workspace + WorkspaceMember ORM models. |
| `backend/app/models/workspace_settings.py` | WorkspaceSettings ORM model — role permissions overrides. |
| `backend/app/models/catalog.py` | VerifiedQA, Glossary, CatalogColumn, CatalogMetric, CatalogJoin, CatalogSynonym, CatalogValueMapping ORM models. |
| `backend/app/models/conversation.py` | Conversation ORM model. |
| `backend/app/models/activity.py` | WorkspaceActivityLog ORM model. |
| `backend/app/models/dashboard.py` | Dashboard + DashboardPanel ORM models. |
| `backend/app/models/saved_query.py` | SavedQuery ORM model. |
| `backend/app/models/recent_connection.py` | RecentConnection ORM model. |
| `backend/app/models/auth_token.py` | AuthToken ORM model. |
| `backend/app/models/base.py` | Base ORM model class with `_uuid7()` helper. |
| `backend/app/logbook.py` | `SessionLog` — thin class that mints per-query IDs. Durable records live in PostgreSQL (`query_history`). |
| `backend/app/services/email.py` | Email sending via Resend API. |
| `backend/app/services/email_verification.py` | Email verification + forgot-password token flows. |
| `backend/requirements.txt` | Python dependencies. |
| `backend/alembic/` | Alembic migration files for schema versioning. Automatically runs `upgrade head` on server start. |
| `backend/alembic.ini` | Alembic configuration. |
| `backend/DOCKERFILE` | Backend Docker image. |
| `backend/docker-entrypoint.sh` | Container entrypoint. |

## Frontend (`frontend/src/`) — SvelteKit 5

### Routes

| Route | Component(s) | What it does |
|---|---|---|
| `frontend/src/routes/(marketing)/+page.svelte` | — | Marketing/landing page (9 sections, GSAP+Lenis animations). Prerendered, heavily SEO-optimised (JSON-LD, OG tags, sitemap). |
| `routes/auth/callback/+page.svelte` | — | Supabase / OAuth callback page. |
| `routes/signup/+page.svelte` | `SignupScreen.svelte` | Sign up with email+password or Google OAuth. |
| `routes/login/+page.svelte` | `LoginScreen.svelte` | Login form. |
| `routes/connect/+page.svelte` | `ConnectScreen.svelte` | Connect a database (form/URL/sample) within a workspace context. |
| `routes/chat/+page.svelte` | `AskScreen.svelte`, `AppShell.svelte` | Main chat screen: input (natural language + SQL), answer feed, sidebar. |
| `routes/dashboards/+page.svelte` | — | Dashboard list view. |
| `routes/dashboards/[id]/+page.svelte` | `DashboardEditor.svelte` | Single dashboard with panels and charts. |
| `routes/dashboards/[id]/edit/+page.svelte` | `DashboardEditor.svelte` | Dashboard edit mode. |
| `routes/workspaces/+page.svelte` | — | Workspace list. |
| `routes/workspaces/setup/+page.svelte` | — | Workspace setup wizard. |
| `routes/profile/+page.svelte` | `ProfileStep.svelte` | Account profile & settings. |
| `routes/verify-email/+page.svelte` | — | Email verification page. |
| `routes/forgot-password/+page.svelte` | — | Forgot password form. |
| `routes/reset-password/+page.svelte` | — | Password reset form. |
| `routes/privacy/+page.svelte` | — | Privacy policy page. |
| `routes/terms/+page.svelte` | — | Terms of service page. |

### Key components (`frontend/src/lib/components/`)

| Component | What it does |
|---|---|
| `lib/components/AppShell.svelte` | Main layout wrapper — sidebar + content area. |
| `lib/components/AskScreen.svelte` | Main chat: message input, answer feed, streaming responses. |
| `lib/components/AnswerCard.svelte` | One answer: restatement, results table, chart, SQL toggle, confidence badge, verify buttons, "Save to Dashboard". |
| `lib/components/AuthChoiceModal.svelte` | Modal component for choosing authentication method (email vs Google sign-in). |
| `lib/components/ChartPanel.svelte` | ECharts visualization panel component. |
| `lib/components/DataCatalog.svelte` | Data catalog management component for glossary, metrics, and value mappings. |
| `lib/components/ExitIntentModal.svelte` | Modal overlay for capturing landing page exit intent. |
| `lib/components/Flywheel.svelte` | Interactive animated flywheel component for workflow visual presentation. |
| `lib/components/GoogleSignIn.svelte` | Google OAuth sign-in button component. |
| `lib/components/ProfileStep.svelte` | Profile setup and account details step component. |
| `lib/components/SettingsTab.svelte` | Tabbed settings sub-component for workspace configuration. |
| `lib/components/Sidebar.svelte` | Schema browser, conversation list, database switcher, trust meter, settings button. |
| `lib/components/Settings.svelte` | OpenRouter model picker + API key management. |
| `lib/components/ConnectScreen.svelte` | Database connection form (workspace-aware, split layout). |
| `lib/components/DashboardEditor.svelte` | Dashboard grid with draggable/resizable panels. |
| `lib/components/SaveQueryDialog.svelte` | Modal to save a query to a dashboard. |
| `lib/components/ProductTour.svelte` | Interactive onboarding tour overlay. |
| `lib/components/ActivityLog.svelte` | Workspace activity log viewer. |
| `lib/components/Stepper.svelte` | Step progress component for setup and onboarding flows. |
| `lib/components/Thinking.svelte` | Indicator displaying real-time query generation and reasoning progress. |
| `lib/components/TrustToast.svelte` | Toast notification component for displaying database trust status updates. |
| `lib/components/charts/ChartCard.svelte` | Card container component wrapping chart visualizations. |
| `lib/components/charts/ResultChart.svelte` | High-level chart component for rendering query results using ECharts. |
| `lib/components/charts/chartUtils.ts` | Utilities for ECharts configuration, data formatting, and color palettes. |

### State, API, and utilities

| File | What it does |
|---|---|
| `lib/appState.svelte.ts` | Global client state (Svelte 5 runes): user, active workspace, engine/model, connection info, trust count, navigation flow. |
| `lib/api.ts` | `apiCall()` and `streamApiCall()` — fetch wrappers with auth headers (workspace + db). Typed endpoint functions. |
| `lib/data.ts` | Static data: provider entries, trust-level definitions, human-friendly error translations (`humanError`). |
| `lib/types.ts` | TypeScript interfaces shared across components. |
| `lib/i18n/` | Localized strings (`typesafe-i18n` with server-detect locale + cookie persistence). |
| `hooks.server.ts` | Server hooks: posthog analytics, locale resolution. |
| `hooks.client.ts` | Client hooks: app initialization, auth redirect. |
| `app.html` | HTML shell. |
| `app.d.ts` | TypeScript declarations. |

## Tests (`tests/`)

The repository includes a 37-file backend unit and integration test suite:

| File | Covers |
|---|---|
| `tests/test_activity_cleanup.py` | Retention and automated cleanup of workspace activity logs. |
| `tests/test_catalog_controller.py` | Data catalog endpoints (read, save, AI suggest). |
| `tests/test_config.py` | Config defaults, env-var key fallback, secret protection. |
| `tests/test_connection_encryption.py` | Encryption and decryption of database connection secrets at rest. |
| `tests/test_connection_rehydration.py` | Rehydration of saved connection parameters into live database engines. |
| `tests/test_database.py` | `DatabaseManager`: connection pooling, schema introspection, SSRF validation. |
| `tests/test_database_controller.py` | Database controller routes: connect, disconnect, sample database. |
| `tests/test_dependencies.py` | FastAPI dependency injection, auth validation, and header scoping. |
| `tests/test_email_verification.py` | Email verification token generation, verification endpoints, and password resets. |
| `tests/test_history.py` | Query history endpoints and CRUD persistence per user/workspace/db. |
| `tests/test_invite_codes.py` | Workspace invitation PIN/code generation, validation, and acceptance. |
| `tests/test_knowledge_service.py` | `KnowledgeService`: verified Q&A, glossary, semantic catalog, and similarity scoring. |
| `tests/test_llm.py` | `OpenRouterProvider`: JSON fence stripping, response parsing, and error mapping. |
| `tests/test_m2_permissions_adversarial.py` | Adversarial security tests for RBAC permission checks across endpoints. |
| `tests/test_onboard_controller.py` | Onboarding wizard controller routes: auto-glossary, starter generation, connection testing. |
| `tests/test_openrouter.py` | OpenRouter provider requests, structured outputs, retries, and health checks. |
| `tests/test_permissions_and_workspace_settings.py` | RBAC role evaluation and custom workspace permission matrix overrides. |
| `tests/test_pgdatabase_users.py` | User persistence and CRUD operations in PostgreSQL. |
| `tests/test_phase4_e2e_suite.py` | End-to-end integration tests for query execution, repair loop, and catalog lookup. |
| `tests/test_query_db_scoping.py` | Strict scoping of query execution to specified workspace and database IDs. |
| `tests/test_query_feedback_verify.py` | User query feedback logging and verified Q&A promotion endpoints. |
| `tests/test_query_pipeline.py` | End-to-end pipeline execution (`run_query()`), schema linking, and self-repair. |
| `tests/test_query_stream.py` | Server-Sent Events (SSE) streaming query endpoint (`POST /api/query/stream`). |
| `tests/test_repair.py` | Isolated SQL self-repair loop: feedback generation, time and iteration bounds. |
| `tests/test_sample_data.py` | Sample database seeding, schema introspection, and pre-populated Q&A verification. |
| `tests/test_schema_link.py` | Table relevance scoring, FK expansion, schema compression, and confidence badge calculation. |
| `tests/test_semantic.py` | Automatic catalog inference from schema, suggestion merging, and table catalog filtering. |
| `tests/test_sqlvalidate.py` | AST-based static SQL parsing and safety validation against live database schemas. |
| `tests/test_structured_output.py` | JSON output schema validation (`SQL_SCHEMA`) and tolerant LLM payload extraction. |
| `tests/test_supabase_auth.py` | Integration with Supabase JWT authentication and OAuth sign-in. |
| `tests/test_system_controller.py` | System diagnostics, health check, and runtime configuration routes. |
| `tests/test_workspace_api_models.py` | Pydantic validation models for workspace API requests and responses. |
| `tests/test_workspace_defaults_empirical.py` | Default settings, role assignments, and capabilities for newly created workspaces. |
| `tests/test_workspace_lifecycle.py` | Workspace lifecycle management: creation, update, member roles, and deletion. |
| `tests/test_workspace_permission_defaults.py` | Verification of initial default permission matrices across Owner, Admin, and Member roles. |
| `tests/test_workspace_settings_api.py` | API endpoints for updating workspace settings and permission overrides. |
| `tests/test_workspace_settings_empirically.py` | Empirical testing of workspace settings resolution and capability evaluation. |

Run: `pytest tests` from the repository root (with `backend/requirements.txt` installed).

## Everything else

| Path | What it is |
|---|---|
| `benchmarks/` | Spider-based evaluation of schema-linking recall and end-to-end accuracy (`benchmarks/README.md`). |
| `docker-compose.yml`, `nginx/`, `backend/DOCKERFILE`, `frontend/DOCKERFILE`, `DOCKERFILE.render` | Docker deployment: backend + frontend + nginx + PostgreSQL. Port 8080. |
| `docker-compose.dev.yml` | Dev overrides — Vite HMR, source mounts. |
| `data/` | Drop SQLite/DuckDB files here to use from Docker (`/app/data/...`). |
| `.github/workflows/` | CI (tests/lint), CodeQL, OpenRouter-powered PR review workflows. |
| `postgres/` | PostgreSQL init scripts. |
| `nginx.conf.render`, `nginx/` | Nginx configs for production and Coolify. |
| `docs/` | Comprehensive user and developer documentation. |
| `memory/` | Product requirements and design docs. |
