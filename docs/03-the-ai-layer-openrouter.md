# 3. The AI Layer — OpenRouter

BoloDB relies exclusively on **OpenRouter** (`deepseek/deepseek-v4-flash`) for all language-model operations.

---

## 1. Responsibilities of the AI Layer

All AI interactions flow through a single module: `backend/app/llm.py`. The AI layer is responsible for:
1. **SQL Generation** (`generate_sql`): Translating plain English questions into valid database SQL queries, plain-English restatements, and chart visualization specs.
2. **SQL Explanation** (`explain_sql`): Translating raw SQL back into plain English for auditing.
3. **Semantic Catalog Suggestion** (`suggest_catalog`): Proposing domain-specific business terms, metrics, joins, and value maps based on database schema introspection.
4. **Starter Question Generation** (`generate_starters`): Generating sample questions and SQL pairs during onboarding to seed the knowledge base.
5. **Semantic Layer Enrichment**: Assisting in identifying joins, synonyms, and value mappings.
6. **Two-Stage Schema Linking**: Shortlisting tables on large schemas (30+ tables) before full schema linking.

---

## 2. OpenRouter Architecture

### Provider & Client (`backend/app/llm.py`)
- **`OpenRouterProvider`**: Wraps the `openai.AsyncOpenAI` SDK configured with base URL `https://openrouter.ai/api/v1`.
- **`ProviderManager`**: Thread-safe manager that maintains and caches the active provider instance.
- **Model**: `deepseek/deepseek-v4-flash` running with low temperature (`temperature=0.1`) for maximum determinism and code precision.
- **Configuration**: The API key is read strictly from the `OPENROUTER_API_KEY` environment variable.

---

## 3. Structured Output Contract

To ensure 100% reliable parsing without markdown wrapping or hallucinated structures, BoloDB uses OpenAI JSON Schema enforcement (`response_format={"type": "json_schema", ...}`).

### `SQL_SCHEMA` Contract
The model returns a JSON object adhering to the following schema:

```json
{
  "sql": "SELECT category_name, SUM(total_amount) AS revenue FROM orders JOIN products ON ... GROUP BY 1",
  "restatement": "Computes total revenue for each product category from completed orders.",
  "assumptions": ["Assumed completed orders means status = 'completed'."],
  "chart": {
    "type": "bar",
    "x_axis": "category_name",
    "y_axis": "revenue",
    "title": "Revenue by Category",
    "reason": "Bar chart compares revenue across product categories."
  }
}
```

### Tolerant Parsing (`parse_json`)
If a model returns JSON wrapped in markdown code blocks (` ```json ... ``` `) or trailing whitespace, `llm.py`'s `parse_json()` utility strips code fences and extracts clean JSON.

---

## 4. Streaming & Real-Time Responses

For fast user feedback during query generation:
- The backend serves chunked Server-Sent Events (SSE) streaming responses on `POST /api/query/stream`.
- `frontend/src/lib/api.ts` provides `streamApiCall()`, which reads the SSE response stream chunk by chunk to display thinking state and partial output in real-time (`Thinking.svelte`).

---

## 5. System Prompt Assembly

The system prompt is assembled dynamically in `build_sql_system_prompt()` (`backend/app/llm.py`). It includes:
1. **Database Dialect**: e.g., PostgreSQL, MySQL, SQLite, DuckDB syntax rules.
2. **Linked Schema**: Compact table definitions produced by `compact_schema()` in `schema_link.py`.
3. **Glossary Terms**: Verified business definitions.
4. **Semantic Layer Context**: Metrics, join paths, synonyms, and value mappings from `pgdatabase/knowledge.py`.
5. **Verified Examples**: Similar past question/SQL pairs retrieved from PostgreSQL knowledge base.
6. **Conversation Context**: Last 2-3 chat turns for follow-up resolution.

---

## 6. Error Handling & Retries

- **Unified Exception**: All LLM operations raise a unified `LLMError(user_message, detail)` exception on failure. User-facing friendly messages (such as `HIGH_TRAFFIC_MESSAGE` for rate limits or provider downtime) are stored in `user_message`, while raw provider details or redacted errors are preserved in `detail`.
- **Retries**: Network failures or transient API errors trigger up to 2 retries with exponential backoff before raising `LLMError`.
