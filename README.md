# BoloDB

[![pre-commit.ci status](https://results.pre-commit.ci/badge/github/BoloDB/bolodb/master.svg)](https://results.pre-commit.ci/latest/github/BoloDB/bolodb/master)

**Ask your data. Trust the answer.**

A text-to-SQL product for non-technical users. Connect any SQL database, ask
questions in plain English, get answers with a plain-English explanation and a
confidence level. Every answer you confirm teaches it your database — accuracy
improves with use.

**📚 Full documentation lives in [`docs/`](docs/README.md)** — written for
non-technical readers, with code pointers for developers at every step.

## Quick Start (Docker)

The easiest and recommended way to run BoloDB is using Docker. This ensures all services (FastAPI Backend, SvelteKit Frontend, Nginx, and MongoDB) run seamlessly.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux).
2. Open a terminal in the project directory.
3. Start the application:
   ```bash
   docker compose up -d
   ```
4. Open [http://localhost:5173](http://localhost:5173) in your browser.
5. Set the `OPENROUTER_API_KEY` environment variable in your docker-compose or `.env` file, connect a database (or click "Try with sample data"), and start asking!

## The AI engine

BoloDB uses **OpenRouter** (specifically the `deepseek/deepseek-v4-flash` model) for all AI operations. You only need one thing:
an OpenRouter API key.

1. Go to https://openrouter.ai/keys.
2. Click **Create Key** and copy it.
3. Set it as the `OPENROUTER_API_KEY` environment variable for your deployment.

| Model | Best for |
|---|---|
| `deepseek/deepseek-v4-flash` (default) | Best cost/accuracy balance for most uses |

**Privacy:** what's sent to the AI to generate SQL is your question plus the
context BoloDB builds around it: the database *structure* (table/column names,
keys), a few sample values and sample rows per table, your confirmed
business-term glossary, previously verified question→SQL examples, and the
last couple of conversation turns. **The prompt never includes** bulk table
contents, query results, or credentials — the OpenRouter API key travels only in
the request's authentication header. See
[docs/03-the-ai-layer-openrouter.md](docs/03-the-ai-layer-openrouter.md) for exactly
what's in every prompt.

## Database connection strings

| Database | Format |
|---|---|
| SQLite | `sqlite:///C:/path/to/file.db` |
| PostgreSQL | `postgresql://user:pass@host:5432/dbname` |
| MySQL | `mysql+pymysql://user:pass@host:3306/dbname` |
| SQL Server | `mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server` |

Tip: connect with a **read-only database account** for safety (BoloDB also
enforces read-only itself — see
[docs/05-safety-validation-and-self-repair.md](docs/05-safety-validation-and-self-repair.md)).

## How it works

1. **Connect** a database and ensure your OpenRouter API key is set in the environment.
2. **Onboard** (first time) — BoloDB profiles the tables, confirms business-term meanings with you, and runs a few starter questions for you to verify
3. **Ask** questions in plain English. Every answer includes:
   - A plain-English restatement ("I summed completed orders for this month")
   - A confidence level (High/Medium/Low) based on real signals
   - The results table and SQL on a toggle
   - Automatic self-repair: generated SQL is validated against your schema and fixed before you ever see an error
4. **Verify** — click "Yes, correct" to save the answer. Similar future questions reuse it and show higher confidence. The trust level climbs from Supervised to Assisted to Trusted

The full pipeline, step by step with code pointers:
[docs/02-how-a-question-becomes-an-answer.md](docs/02-how-a-question-becomes-an-answer.md).

## Useful Docker Commands

```bash
docker compose up -d           # Start the application in the background
docker compose logs -f         # View live logs from all services
docker compose down            # Stop all services
docker compose build --no-cache # Rebuild all images from scratch
```

## Running tests

```bash
pip install -r backend/requirements.txt
pytest tests
```

The test suite needs no network and no API key — all AI calls are faked.

## Privacy

- All learned knowledge and user settings are stored locally (`~/.bolodb/`) and in the local MongoDB container volume. The API key is read from the environment and never stored on disk.
- To generate SQL, the AI is sent your question plus context: the schema, a few sample values/rows per table, your confirmed glossary terms, verified question→SQL examples, and recent conversation turns. The prompt never includes bulk table data, query results, or credentials (the API key is used only as the request's authentication header).
- Queries run strictly read-only.
- No telemetry, no cloud sync.

## License

MIT &mdash; see [LICENSE](LICENSE).
