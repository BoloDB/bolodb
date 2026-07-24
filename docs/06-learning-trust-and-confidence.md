# 6. Learning, trust, and confidence

BoloDB's accuracy is not static — it improves with use, per workspace and database connection, because of a simple loop: **every answer you confirm becomes an example the AI sees next time.**

---

## 1. The Knowledge Base (`backend/app/pgdatabase/knowledge.py`)

Knowledge is persisted asynchronously in PostgreSQL via `KnowledgeService`. All entries are strictly scoped by **Workspace ID** and **Database ID** (`db_id`), ensuring data from one workspace or database never leaks to another.

### Managed Entities
1. **Verified Q&A (`VerifiedQA`)**: Question, SQL, restatement, and metadata of every answer confirmed by a workspace member (`add_verified()`). Near-duplicate questions are skipped if similarity > 0.92.
2. **Business Glossary (`Glossary`)**: Workspace-confirmed business terms (`term` → `meaning` → `sql_hint`), managed via `set_glossary()`.
3. **Semantic Layer**: Business metrics, join rules, synonyms, and value mappings (`CatalogMetric`, `CatalogJoin`, `CatalogSynonym`, `CatalogValueMapping`), managed via `set_catalog()`.

### Retrieval & Similar Question Matching
When a new question arrives, `retrieve_similar()` retrieves up to 3 similar verified Q&A entries using Jaccard word-overlap and string distance algorithms (`_similarity()`):

$$\text{similarity} = 0.6 \times \text{word-overlap} + 0.4 \times \text{sequence-similarity}$$

Matches above a 0.25 threshold are injected directly into the system prompt as worked examples (`_examples_block()` in `backend/app/llm.py`).

---

## 2. The Confidence Badge (`backend/app/schema_link.py` → `compute_confidence()`)

The High/Medium/Low badge is derived strictly from **observable runtime signals**:

| Situation | Badge | Reason shown |
|---|---|---|
| The query failed to run | **Low** | "the generated query did not run - please rephrase" |
| Best verified match ≥ 0.78 similarity | **High** | "closely matches an answer you verified before" |
| Best verified match ≥ 0.50 | **Medium** | "similar to an answer you verified before" |
| No match, query returned zero rows | **Low** | "no matching rows - the question may not match your data" |
| No match, query returned rows | **Medium** | "new question - please confirm it is right" |

---

## 3. The Trust Level (Supervised → Assisted → Trusted)

A workspace database trust summary computed in `KnowledgeService` and reflected in the UI (`frontend/src/lib/data.ts` → `trustFor()`):

| Verified answers | Level | Product behaviour |
|---|---|---|
| 0–2 | **Supervised** | Every answer prompts for confirmation while learning. |
| 3–6 | **Assisted** | Confident answers displayed; novel ones get a second look. |
| 7+ | **Trusted** | Answers displayed directly; reasoning on tap. |

---

## 4. End-to-End Feedback & Verification Flow

1. User clicks **"Yes, correct"** or **"Verify"** on an answer card (`frontend/src/lib/components/AnswerCard.svelte`).
2. Frontend issues `POST /api/feedback` or `POST /api/verify` → `backend/app/routes/query.py` → `backend/app/controllers/query.py`.
3. The verified pair is saved into PostgreSQL via `KnowledgeService.add_verified()`.
4. Workspace activity is recorded in `WorkspaceActivityLog`.

---

## 5. Persistence Map in BoloDB v2

| Entity | Storage | Managed by |
|---|---|---|
| Users & Workspaces | PostgreSQL | `backend/app/pgdatabase/users.py`, `workspaces.py` |
| Verified Q&A, Glossary, Catalog | PostgreSQL | `backend/app/pgdatabase/knowledge.py` |
| Encrypted DB Connections | PostgreSQL | `backend/app/pgdatabase/connections.py` |
| Query History | PostgreSQL | `backend/app/pgdatabase/history.py` |
| Dashboards & Saved Queries | PostgreSQL | `backend/app/pgdatabase/dashboards.py`, `saved_queries.py` |
| Audit Trail / Session Log | PostgreSQL | `backend/app/models/activity.py` |
