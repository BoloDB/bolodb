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
| Oracle | `oracle+oracledb://user:pass@host:1521/?service_name=ORCLPDB1` |
| SQLite | `sqlite:///C:/path/to/file.db` |
| SQL Server | `mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server` |
| DuckDB | `duckdb:///path/to/file.duckdb` |
| Snowflake | `snowflake://user:pass@myorg-myaccount/DB/SCHEMA?warehouse=COMPUTE_WH` |
| Databricks | `databricks://token:dapi***@host?http_path=/sql/1.0/warehouses/abc123` |
| BigQuery | `bigquery://my-gcp-project/my_dataset?credentials_base64=<base64 key>` |

Oracle connects by host, port and `service_name` (or a SID path, e.g.
`.../XEPDB1`). TNS aliases, `DESCRIPTION` connect descriptors and `dsn`
parameters are not supported — the host they name cannot be checked against
the SSRF guard. Percent-encode any `@ : / #` in a password.

BigQuery authenticates with a service account key rather than a password.
Paste the key JSON into the connect form and it travels as
`credentials_base64` inside the connection URL, which is encrypted at rest
alongside every other credential; it is redacted wherever the URL is
displayed, logged, or hashed, so rotating the key does not change the
database's identity. Leave it blank to use the server's ambient Google
credentials instead. Parameters that make a driver read a key off this
server's disk — `credentials_path`, `private_key_file` — are rejected.

Databricks needs the `http_path` from its SQL warehouse's connection details.
Snowflake takes the account identifier (the part before
`.snowflakecomputing.com`) in place of a host, and needs a `warehouse` unless
the user has a default one.

The Snowflake, Databricks and BigQuery drivers are large — roughly half a
gigabyte between them, mostly pyarrow, pandas, numpy, boto3 and grpcio — so
they are **not installed by default**. They live in
`backend/requirements-warehouses.txt`:

```bash
# local
pip install -r backend/requirements.txt -r backend/requirements-warehouses.txt

# docker
docker compose build --build-arg INSTALL_WAREHOUSE_DRIVERS=true backend
```

Everything BoloDB needs to *support* those dialects — URL validation, the
read-only guard, identifier quoting, prompt hints — ships in the base install;
only the drivers are optional. Connecting to one without them reports the
missing driver by name rather than failing with an import traceback. Oracle is
included by default: `python-oracledb` is small and pure Python.

By default BoloDB refuses to connect to databases on private or internal
addresses — `10.x`, `192.168.x`, `172.16–31.x`, and hostnames that resolve into
them — because on a shared deployment a connection URL is user input, and
allowing private targets turns "add a database" into a way to reach the rest of
the network. Self-hosted installs whose database really is on a LAN set
`ALLOW_PRIVATE_DB_HOSTS=true`. Loopback, link-local and cloud metadata
endpoints stay blocked either way.

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
