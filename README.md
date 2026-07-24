# BoloDB

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/BoloDB/bolodb/master.svg)](https://results.pre-commit.ci/latest/github/BoloDB/bolodb/master)

**Ask your data. Trust the answer.**

A multi-tenant text-to-SQL web application for non-technical users and teams. Connect your database, ask questions in plain English, and get instant answers with plain-English restatements, ECharts visualizations, and confidence levels. Save queries to interactive dashboards and manage multi-user workspaces with role-based access control (RBAC).

**📚 Full documentation lives in [`docs/`](docs/README.md)** — written for non-technical readers, with code pointers for developers at every step.

---

## Quick Start (Docker)

The easiest and recommended way to run BoloDB is using Docker Compose (FastAPI backend + SvelteKit frontend + Nginx + PostgreSQL).

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine.
2. Clone the repository and navigate into the root directory.
3. Copy `.env.example` to `.env` and fill in required secrets (`OPENROUTER_API_KEY`, `JWT_SECRET`, `DATABASE_URL`, `RECENT_CONNECTIONS_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`).
4. Start the application stack:

   **Production / Deployment**:
   ```bash
   docker compose up --build -d
   ```
   Open [http://localhost:8080](http://localhost:8080).

   **Local Development (Vite HMR)**:
   ```bash
   docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
   ```
   Open [http://localhost:8080](http://localhost:8080) (Nginx proxy) or [http://localhost:5174](http://localhost:5174) (Vite frontend).

---

## Key Features

- **Multi-Tenant Workspaces & RBAC**: Isolate connections, dashboards, and knowledge bases per workspace. Assign Owner, Admin, or Member roles with fine-grained capability checks.
- **OpenRouter AI Engine**: Powered by `deepseek/deepseek-v4-flash` via OpenRouter.
- **Interactive Dashboards & Charts**: Automated ECharts visual inference (Bar, Line, Area, Pie, Number, Table) with query panel customization.
- **Semantic Layer**: Define custom business metrics, explicit join paths, synonyms, and value mappings to guide AI SQL generation.
- **Safety & Defense in Depth**: Read-only AST validation, SSRF protection, host allowlisting, and 5s statement timeouts.
- **PostgreSQL Persistence**: All state (users, workspaces, connections encrypted at rest, query history, dashboards, verified Q&A) is persisted asynchronously in PostgreSQL.

---

## Supported Database Connections

| Database | Connection URL Format |
|---|---|
| PostgreSQL | `postgresql://user:pass@host:5432/dbname` |
| MySQL | `mysql+pymysql://user:pass@host:3306/dbname` |
| SQLite | `sqlite:///C:/path/to/file.db` |
| SQL Server | `mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server` |
| DuckDB | `duckdb:///path/to/file.duckdb` |

---

## Architecture & Code Map

Full file and directory index is available in [`docs/07-file-map.md`](docs/07-file-map.md).

```text
 Browser (SvelteKit 5 Frontend, frontend/src)
    │  HTTP / SSE streaming (JWT cookie auth, X-Workspace-Id and X-Db-Id headers)
    ▼
 FastAPI Backend (backend/app)
    ├── controllers/query.py ─── The query pipeline (knowledge → schema link → LLM → repair)
    ├── llm.py ───────────────── OpenRouter provider (deepseek/deepseek-v4-flash)
    ├── schema_link.py ───────── Schema linking, budget management & table scoring
    ├── sqlvalidate.py ───────── AST static SQL validation
    ├── repair.py ────────────── Self-repair loop for auto-correcting broken SQL
    ├── semantic.py ──────────── Semantic layer catalog & inference
    ├── database.py ──────────── DB introspection & read-only execution guard
    └── pgdatabase/ ──────────── Async PostgreSQL persistence (KnowledgeService, Users, Workspaces, Dashboards)
```

---

## Running Unit Tests

```bash
pip install -r backend/requirements.txt
pytest tests -v
```

The test suite runs entirely offline using mock OpenRouter providers.

---

## Privacy & Security

- Connection credentials are **encrypted at rest** using Fernet symmetric encryption key (`RECENT_CONNECTIONS_KEY`).
- AI prompts include only database structure, compact column schemas, verified Q&A examples, and business glossary definitions. Bulk data rows, query results, and credentials are **never sent** to the AI model.
- All SQL execution runs in strict **read-only** mode with statement timeout protection.

---

## License

MIT — see [LICENSE](LICENSE).
