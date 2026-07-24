# 12. The Semantic Layer

The **Semantic Layer** bridges the gap between raw database schemas and business domain concepts. It ensures that business terminology, complex metrics, and implicit table relationships are correctly interpreted by the AI during SQL generation.

---

## 1. Core Concepts & Data Models

The semantic layer is stored in PostgreSQL via `KnowledgeService` (`set_catalog` / `get_catalog` in `backend/app/pgdatabase/knowledge.py`) and modeled in `backend/app/models/catalog.py`.

### 1. Metric Definitions (`CatalogMetric`)
Pre-defined SQL expressions for business metrics so the AI doesn't miscalculate key KPIs.
- *Example*: `ARR = SUM(annual_contract_value) WHERE status = 'active'`

### 2. Join Paths (`CatalogJoin`)
Explicit join rules between tables when foreign keys are missing or when non-standard join conditions are required.
- *Example*: `orders.customer_id = customers.id AND customers.is_deleted = false`

### 3. Synonyms (`CatalogSynonym`)
Mapping business slang or alternative names to actual database table or column names.
- *Example*: `"client"` → `customers`, `"gross sales"` → `orders.total_amount`

### 4. Value Mappings (`CatalogValueMapping`)
Translating user concepts into specific column value filters.
- *Example*: `"VIP customers"` → `customers.tier = 'VIP'` or `customers.total_spend > 10000`

### 5. Column Descriptions (`CatalogColumn`)
Human-readable context and notes attached to specific database columns.

---

## 2. Automatic Inference & Schema Enrichment

BoloDB automatically assists in building the semantic layer using `backend/app/semantic.py` and `backend/app/llm.py`:

1. **`suggest_from_schema(schema)`**: Inspects foreign keys, column names, and sample values to propose join paths and value mappings deterministically.
2. **`suggest_catalog(provider, schema_text)`**: Uses LLM enrichment (`backend/app/llm.py`) to generate descriptions, metrics, synonyms, and business labels from schema text.
3. **`merge_catalog_suggestions(existing, suggested)`**: Merges automatic schema suggestions with human overrides.
4. **`filter_catalog(catalog, linked_tables)`**: Scopes the semantic catalog so only relevant metrics, joins, and synonyms are included in the prompt for the tables selected by schema linking.

---

## 3. How the AI Uses the Semantic Layer

During Step 1 and 2 of the question pipeline (`backend/app/controllers/query.py`), BoloDB fetches the workspace's semantic catalog for the active database connection:

```text
Question ──▶ Schema Linking (picks relevant tables)
                │
                ▼
          filter_catalog() (filters metrics/joins for selected tables)
                │
                ▼
          Prompt Assembly (appends Semantic Rules block to OpenRouter prompt)
                │
                ▼
          LLM generates accurate, domain-aware SQL
```

### Prompt Integration Example
In `backend/app/llm.py`, the semantic context is injected directly into the prompt:

```text
[SEMANTIC RULES & METRICS]
- When user asks for "ARR", use expression: SUM(annual_contract_value) WHERE status = 'active'
- Always join orders to customers using: orders.customer_id = customers.id
- "VIP customer" means: tier = 'VIP'
```

---

## 4. Semantic Catalog Management

Workspace admins and owners can view, edit, and AI-suggest the semantic layer via the Data Catalog endpoints (`GET /api/catalog`, `POST /api/catalog`, `POST /api/catalog/suggest`), handled by `backend/app/routes/catalog.py` and `backend/app/controllers/catalog.py`.

### Request Context Headers
All catalog endpoints require workspace and database context propagation headers:
- `X-Workspace-Id`: Target workspace identifier.
- `X-Db-Id`: Target database connection identifier.

Saving catalog entries executes `set_catalog()` on `KnowledgeService` (`backend/app/pgdatabase/knowledge.py`), replacing or updating stored entries for the active workspace and database. Changes take effect immediately for all subsequent queries.
