# BoloDB

**Ask your data. Trust the answer.**

A text-to-SQL product for non-technical users. Connect any SQL database, ask questions in plain English, get answers with a plain-English explanation and a confidence level. Every answer you confirm teaches it your database - accuracy improves with use.

## Quick Start (Docker)

The easiest and recommended way to run BoloDB is using Docker. This ensures all services (FastAPI Backend, SvelteKit Frontend, Nginx, and MongoDB) run seamlessly.

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/Mac) or Docker Engine (Linux).
2. Open a terminal in the project directory.
3. Start the application:
   ```bash
   docker compose up -d
   ```
4. Open [http://localhost:5173](http://localhost:5173) in your browser.
5. Pick your AI engine, connect a database (or click "Try with sample data"), and start asking!

## Choose your AI engine

| Engine | Privacy | Cost | Setup |
|---|---|---|---|
| Local (Ollama) | Fully private, nothing leaves your machine | Free | Install Ollama + `ollama pull llama3.2` |
| Claude API | Schema + question sent to Anthropic | Pay per use | Paste API key in Settings |
| OpenAI API | Schema + question sent to OpenAI | Pay per use | Paste API key in Settings |
| Groq API | Schema + question sent to Groq | Pay per use | Paste API key in Settings |

With any API engine, only the schema and your question are sent - never your actual row data.

### Local AI setup

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama3.2` (4GB RAM) or `ollama pull phi4-mini` (low RAM)
3. **Important for Linux users:** Docker containers need permission to reach your host's Ollama instance.
   - Configure Ollama to listen on all interfaces:
     ```bash
     sudo systemctl edit ollama.service
     # Add this under [Service]:
     # Environment="OLLAMA_HOST=0.0.0.0"
     
     sudo systemctl daemon-reload
     sudo systemctl restart ollama
     ```
   - If you have a firewall (UFW), allow Docker networks to reach port 11434:
     ```bash
     sudo ufw allow from 172.16.0.0/12 to any port 11434 proto tcp
     ```

## Database connection strings

| Database | Format |
|---|---|
| SQLite | `sqlite:///C:/path/to/file.db` |
| PostgreSQL | `postgresql://user:pass@host:5432/dbname` |
| MySQL | `mysql+pymysql://user:pass@host:3306/dbname` |
| SQL Server | `mssql+pyodbc://user:pass@server/db?driver=ODBC+Driver+17+for+SQL+Server` |

Tip: connect with a **read-only database account** for safety.

## How it works

1. **Connect** a database and pick an AI engine
2. **Onboard** (first time) - BoloDB profiles the tables, confirms business-term meanings with you, and runs a few starter questions for you to verify
3. **Ask** questions in plain English. Every answer includes:
   - A plain-English restatement ("I summed completed orders for this month")
   - A confidence level (High/Medium/Low) based on real signals
   - The results table and SQL on a toggle
4. **Verify** - click "Yes, correct" to save the answer. Similar future questions reuse it and show higher confidence. The trust level climbs from Supervised to Assisted to Trusted

## Useful Docker Commands

```bash
docker compose up -d           # Start the application in the background
docker compose logs -f         # View live logs from all services
docker compose down            # Stop all services
docker compose build --no-cache # Rebuild all images from scratch
```

## Running tests

```bash
pip install -r requirements.txt
pytest
```

## Privacy

- All learned knowledge is stored locally in `~/.bolodb/`
- With a local model (Ollama), nothing leaves your machine
- With an API model, only the schema and your question are sent to generate SQL
- No telemetry, no cloud sync
- Delete `~/.bolodb/` to wipe everything BoloDB has learned

## License

MIT &mdash; see [LICENSE](LICENSE).
