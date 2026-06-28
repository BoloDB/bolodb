# Contributing to BoloDB

First off, thank you for checking out BoloDB! We welcome contributions to make text-to-SQL database auditing and natural language queries safe, fast, and easy for everyone.

This document outlines the guidelines and procedures for contributing to BoloDB.

---

## Architecture Overview

BoloDB is built using a modern containerized stack designed for ease of local deployment and scalability:
- **Backend:** FastAPI (Python 3.10+) utilizing SQLAlchemy for database connectivity, and `sqlglot` for secure AST-based read-only validation.
- **Frontend:** A SvelteKit application utilizing TypeScript and Tailwind CSS (or CSS variables) for a polished, responsive user interface.
- **Database / Knowledge Base:** MongoDB container storing user settings, verified queries, session history, and platform glossary.
- **Reverse Proxy:** Nginx configured to route traffic seamlessly between the frontend and backend services while handling proxy configurations.
- **LLM Connectors:** Support for local Ollama instances and APIs (Anthropic, OpenAI, Groq).

---

## Directory Structure

```text
bolodb/
├── backend/
│   ├── app/              # FastAPI application core logic, database managers, LLM logic
│   ├── main.py           # FastAPI server entry point
│   ├── requirements.txt  # Core + dev Python dependencies
│   ├── sample_data.py    # Helper to seed a dummy SQLite database (TechStore)
│   └── DOCKERFILE        # Backend container build instructions
├── frontend/
│   ├── src/              # SvelteKit components, routes, and lib folder
│   ├── static/           # Static assets
│   ├── package.json      # Node.js dependencies
│   ├── vite.config.ts    # Vite bundler configuration
│   └── DOCKERFILE        # Frontend container build instructions
├── nginx/
│   ├── default.conf      # Nginx routing and proxy configuration
│   └── DOCKERFILE        # Nginx container build instructions
├── tests/                # Pytest test suite for backend logic
├── docker-compose.yml    # Orchestrates the multi-container environment (Frontend, Backend, Nginx, MongoDB)
└── LICENSE               # MIT License
```

---

## Setting Up Your Development Environment

The easiest and recommended way to run BoloDB during development is using Docker Compose, which automatically sets up all dependent services.

### 1. Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or Docker Engine installed and running.
- (Optional) [Ollama](https://ollama.ai) installed locally if you want to test with a fully local model. Pull a model: `ollama pull llama3.2`.

### 2. Run the Application via Docker (Recommended)

To start the full stack:
```bash
docker compose up --build
```
This will start MongoDB, the FastAPI Backend, the SvelteKit Frontend, and Nginx. The application will be accessible at `http://localhost:5173`.

### 3. Running Services Locally (Without Docker)

If you need to run specific services directly on your host machine for debugging:

#### Backend Development
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```
*Note: Ensure you have a MongoDB instance running locally on `localhost:27017` or configure the connection string via environment variables, as the backend relies on MongoDB.*

#### Frontend Development
```bash
cd frontend
npm install
npm run dev
```

---

## Running Tests

All core backend logic is covered by a test suite using `pytest`. Make sure `PYTHONPATH` is set appropriately when executing tests from the root directory.

```bash
# Ensure backend requirements are installed, then from the root directory:
PYTHONPATH=./backend pytest tests/
```

Ensure all tests pass before making a pull request.

---

## Guidelines for Contributions

### Core Backend (`backend/app/`)
- **Read-Only Safety:** The AST-based read-only verification in `app/database.py` is BoloDB's primary defense line. If you modify database execution paths, verify that no write queries (`INSERT`, `UPDATE`, `DROP`, `SELECT INTO`, etc.) can be executed unless explicitly permitted via a bypass flag.
- **LLM Compatibility:** Ensure prompts are concise and token-efficient. BoloDB supports smaller local models (e.g., Llama 3.2 3B). Test prompt changes against both small local models and larger cloud APIs.
- **Typing:** Provide Python 3 type hints where possible to keep the codebase easy to read and maintain.
- **Async Code:** The FastAPI backend relies on asynchronous operations. Avoid introducing blocking synchronous calls, especially in endpoints handling database or LLM interactions.

### Frontend (`frontend/src/`)
- **Component Design:** Utilize Svelte's reactive stores for state management and keep components small and modular.
- **Styling:** Follow the established CSS custom properties (design tokens) and dark mode paradigms to ensure the interface maintains its polished layout and premium aesthetic.
- **API Connectivity:** Ensure any new frontend features gracefully handle potential backend connectivity issues and display appropriate error states or loading indicators.

---

## Pull Request Process

1. **Create a branch:** Create a descriptive branch name from `main` (e.g., `feature/custom-db-timeout` or `bugfix/fix-postgres-schema`).
2. **Write clean code:** Keep changes focused. Avoid large refactors unless discussed beforehand.
3. **Verify tests:** Run `PYTHONPATH=./backend pytest tests/` and ensure they pass. Write new tests in `tests/` for new features or bug fixes.
4. **Open a PR:** Describe your changes, why they are needed, and how they were tested.
