# Contributing to BoloDB

First off, thank you for checking out BoloDB! We welcome contributions to make text-to-SQL database auditing and natural language queries safe, fast, and easy for everyone.

This document outlines the guidelines and procedures for contributing to BoloDB.

---

## Architecture Overview

BoloDB is built using a lightweight stack designed for ease of local deployment:
- **Backend:** FastAPI (Python 3.10+) utilizing SQLAlchemy for database connectivity, and `sqlglot` for secure AST-based read-only validation.
- **Frontend:** A single, self-contained single-page application (`static/index.html`) using React 18, Babel (in-browser compilation), and CSS variables (no build tool required).
- **Knowledge Base:** Local SQLite database storing user-verified queries and terms.
- **LLM Connectors:** Support for local Ollama instances and APIs (Anthropic, OpenAI, Groq).

---

## Directory Structure

```text
bolodb/
├── app/
│   ├── config.py         # Config persistence (JSON) & path constants
│   ├── database.py       # Database manager, schema inspection, AST read-only guard
│   ├── knowledge.py      # SQLite-based local knowledge base (verified queries, glossary)
│   ├── llm.py            # LLM provider classes & prompt generation templates
│   ├── logbook.py        # Session activity logging (.jsonl)
│   ├── schema_link.py    # Schema linking logic & signal-based confidence scoring
│   ├── server.py         # FastAPI endpoints and API routes
│   └── utils.py          # Internal helper utilities
├── static/
│   └── index.html        # React SPA frontend (contains UI markup, styling, and logic)
├── tests/
│   ├── test_config.py
│   ├── test_database.py
│   ├── test_knowledge.py
│   ├── test_llm.py
│   └── test_schema_link.py
├── main.py               # Main CLI entry point
├── sample_data.py        # Helper to seed a dummy SQLite database (TechStore)
├── requirements.txt      # Core + dev python dependencies
├── run.bat & setup.bat   # Windows convenience launchers
└── LICENSE               # MIT License
```

---

## Setting Up Your Development Environment

### 1. Prerequisites
- Python 3.10 or higher.
- (Optional) [Ollama](https://ollama.ai) installed locally if you want to test with a fully local model. Pull a small model: `ollama pull llama3.2`.

### 2. Install Dependencies
It is highly recommended to use a virtual environment (`venv`) to isolate dependencies:

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Linux/macOS:
source .venv/bin/activate
# On Windows (cmd):
.venv\Scripts\activate.bat
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Install core and dev dependencies
pip install -r requirements.txt
```

### 3. Run the Application
Start the FastAPI server and launch the browser client:

```bash
python main.py
```

Additional CLI options:
```bash
python main.py --db sqlite:///path/to/my.db  # Pre-connect to a specific database
python main.py --port 8080                    # Run on port 8080
python main.py --no-browser                   # Do not automatically open the browser
python main.py --allow-writes                 # Disable the read-only AST safety guard (dangerous!)
```

---

## Running Tests

All logic is covered by a test suite using `pytest`. Make sure `PYTHONPATH` is set to the root directory when executing tests.

```bash
# Activate virtual environment and run tests
PYTHONPATH=. pytest
```

Ensure all tests pass before making a pull request.

---

## Guidelines for Contributions

### Core Backend (`app/`)
- **Read-Only Safety:** The AST-based read-only verification in `app/database.py` is BoloDB's primary defense line. If you modify database execution paths, verify that no write queries (`INSERT`, `UPDATE`, `DROP`, `SELECT INTO`, etc.) can be executed unless `--allow-writes` is explicitly set.
- **LLM Compatibility:** Ensure prompts are concise and token-efficient. BoloDB supports smaller local models (e.g., Llama 3.2 3B). Test prompt changes against both small local models and larger cloud APIs.
- **Typing:** Provide Python 3 type hints where possible to keep the codebase easy to read and maintain.

### Frontend (`static/index.html`)
- BoloDB uses a single-file React application to make distribution simple. Avoid adding external CDN scripts unless necessary.
- Follow the CSS custom properties (design tokens) declared in `:root` to ensure the interface maintains its polished layout and consistent themes (`crisp` / `soft`).

---

## Pull Request Process

1. **Create a branch:** Create a descriptive branch name from `main` (e.g., `feature/custom-db-timeout` or `bugfix/fix-postgres-schema`).
2. **Write clean code:** Keep changes focused. Avoid large refactors unless discussed beforehand.
3. **Verify tests:** Run `PYTHONPATH=. pytest` and ensure they pass. Write new tests in `tests/` for new features or bug fixes.
4. **Open a PR:** Describe your changes, why they are needed, and how they were tested.
