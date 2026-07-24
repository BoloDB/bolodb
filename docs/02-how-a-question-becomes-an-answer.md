# 2. How a question becomes an answer

This chapter follows **one question** through the entire BoloDB system, in order, with exact code locations for every step.

Our example question:

> **"How much revenue did we make from laptops last month?"**

---

## Step 0 — The browser sends the question

You type into the chat screen (`frontend/src/lib/components/AskScreen.svelte`) and submit.

- **Request**: Sends `POST /api/query` containing:
  - Natural language question
  - Conversation context (previous question/SQL pairs for follow-up resolution)
  - `X-Workspace-Id` and `X-Db-Id` headers (Workspace and Database selection)
  - JWT authentication cookie (`backend/app/dependencies.py` → `get_current_user`)
- **Route**: `backend/app/routes/query.py` → `query()`, which invokes `backend/app/controllers/query.py` → `run_query()`.

---

## Step 1 — Knowledge Lookup & Semantic Layer Injection

BoloDB queries the PostgreSQL workspace knowledge base (`backend/app/pgdatabase/knowledge.py` → `KnowledgeService`):

1. **Business Glossary**: Confirmed business term definitions (e.g., `revenue = sum of total_amount on completed orders`).
2. **Semantic Layer Catalog**: Active metrics (`CatalogMetric`), join paths (`CatalogJoin`), synonyms (`CatalogSynonym`), and value mappings (`CatalogValueMapping`).
3. **Verified Answer Examples**: Up to 3 similar verified question→SQL pairs retrieved via similarity scoring (`retrieve_similar()`).

---

## Step 2 — Schema Linking (Table Selection)

To optimize cost and avoid confusing the AI, BoloDB filters the database schema down to only the relevant tables.

- **Location**: `backend/app/schema_link.py` → `link_relevant_tables()`.
- Tables matching "revenue" (via glossary `total_amount`), "laptops" (via product category value match), and "orders" are selected.
- Foreign keys and junction tables (e.g. `order_items`) are expanded (`expand_linked_tables()`).
- On large databases (30+ tables), a cheap pre-pass shortlists candidates (`llm.py` → `shortlist_tables()`).
- Selected tables are formatted into compact text representations via `compact_schema()`.

---

## Step 3 — Generation, Validation, Execution & Self-Repair

Orchestrated by `backend/app/repair.py` → `run_repair_loop()`:

1. **Generate**: OpenRouter AI is invoked (`backend/app/llm.py` → `generate_sql()`). The system prompt is constructed by `build_sql_system_prompt()`. The response returns structured JSON containing:
   - `sql`: The generated query
   - `restatement`: Plain English summary of what was computed
   - `assumptions`: List of assumptions made by the model
   - `chart`: Inferred visualization specification (chart type, x/y columns, title)
2. **Validate**: The SQL is parsed into an AST via `sqlglot` (`backend/app/sqlvalidate.py` → `validate_sql()`) to verify that all referenced tables and columns exist.
3. **Execute**: The query runs in **read-only** mode with statement timeouts and SSRF protection (`backend/app/database.py` → `DatabaseManager.execute()`).
4. **Self-Repair (if step 2 or 3 failed)**: The exact error is appended to the prompt (`_feedback()`), and the loop retries (up to 3 attempts within a 60-second window).

---

## Step 4 — Confidence Scoring, Logging & Visualization

- **Confidence**: Derived from real runtime signals (`schema_link.py` → `compute_confidence()`).
- **Persistence**: Recorded in PostgreSQL query history (`backend/app/pgdatabase/history.py`) and workspace activity log.
- **Rendering**: Returned as JSON (or streamed via Server-Sent Events). The frontend renders an `AnswerCard.svelte` (`frontend/src/lib/components/AnswerCard.svelte`) featuring:
  - Plain English restatement
  - Interactive data table
  - **ECharts visualization** (`frontend/src/lib/components/ChartPanel.svelte`) based on the inferred `chart` spec
  - Confidence pill and SQL view toggle
  - **"Save to Dashboard"** button (`frontend/src/lib/components/SaveQueryDialog.svelte`)

---

## Step 5 — Feedback & Verification Flywheel

If a user clicks **"Yes, correct"** or **"Verify"**:
1. Frontend calls `POST /api/feedback` → `backend/app/routes/query.py` → `controllers/query.py`.
2. The question-and-SQL pair is added to PostgreSQL via `KnowledgeService.add_verified()`.
3. Subsequent similar queries retrieve this verified example during Step 1.
