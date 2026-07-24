# 9. Cost Optimization — High Accuracy without Burning Tokens

BoloDB follows a clear design rule: **(1) the user's experience is never compromised, (2) every avoidable token is avoided.**

Because OpenRouter bills per token, optimizing prompt construction and output format directly reduces operational cost while simultaneously improving model accuracy.

---

## 1. Where AI Cost Comes From

Query generation cost is governed by:

$$\text{Cost} = \left( \text{Tokens}_{\text{prompt}} + \text{Tokens}_{\text{output}} \right) \times \text{Attempts}_{\text{repair}}$$

Where:
- **Prompt Tokens**: System instructions + compact schema + business glossary + semantic catalog rules + verified worked examples + conversation turns.
- **Output Tokens**: Structured JSON containing SQL, plain-English restatement, assumptions, and chart specification.
- **Attempts**: Number of self-repair retries (1 attempt for clean executions, up to 3 for repaired queries).

---

## 2. Optimization Mechanisms

| # | Mechanism | Effect | Implementation File |
|---|---|---|---|
| 1 | **Schema Linking** | Sends only relevant tables instead of dumping full database schema | `backend/app/schema_link.py` → `link_relevant_tables()` |
| 2 | **Compact Schema Rendering** | Compresses table definitions into 1 line per table | `schema_link.py` → `compact_schema()` |
| 3 | **Structured Output Contract** | Forces exact JSON schema (`SQL_SCHEMA`); eliminates rambling prose | `backend/app/llm.py` → `OpenRouterProvider` |
| 4 | **Streaming Responses** | Streams chunks in real time, giving immediate user feedback without polling overhead | `backend/app/routes/query.py` & `frontend/src/lib/api.ts` |
| 5 | **Bounded Self-Repair** | Enforces max 3 repair attempts and 60-second execution deadline | `backend/app/controllers/query.py` → `_MAX_ATTEMPTS` |
| 6 | **PostgreSQL Verified Answer Reuse** | Injects verified Q&A pairs as few-shot prompt examples, maximizing first-pass success | `backend/app/pgdatabase/knowledge.py` → `retrieve_similar()`, `set_glossary()`, `set_catalog()` |
| 7 | **Two-Stage Linking for Large Schemas** | Pre-filters candidate tables via cheap names-only shortlist on schemas with 30+ tables | `llm.py` → `shortlist_tables()` |
| 8 | **Schema Introspection Caching** | Caches table introspections per workspace database connection | `backend/app/database.py` → `get_schema()` |

---

## 3. Deliberate Trade-Offs

- **No Over-Trimming**: Foreign key parents and junction tables are retained even beyond the initial table budget (`_FK_EXTRA_SLOTS`) to avoid broken SQL JOINs.
- **Fail Fast**: Non-retryable errors (e.g., authentication or permissions) fail immediately to avoid wasting tokens.

---

## 4. Benchmarking Cost and Accuracy

The benchmark suite (`benchmarks/README.md`) measures schema linking recall, execution accuracy, and average token consumption against standard benchmark datasets like Spider.
