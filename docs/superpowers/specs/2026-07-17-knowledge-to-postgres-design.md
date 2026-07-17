# Move Knowledge Base to PostgreSQL + Per-User Product Tour

**Date:** 2026-07-17
**Status:** Design approved

## Motivation

BoloDB is a multi-user application, but the knowledge base (glossary, verified
Q&As, semantic catalog) lives in a local SQLite file (`~/.bolodb/knowledge.db`).
This causes three problems:

1. **No horizontal scaling** — SQLite is a single file; multiple backend
   containers cannot share it.
2. **Knowledge is shared across users** — the `KnowledgeBase` is keyed only by
   `db_id` (a hash of the database URL), so two users connecting to the same DB
   see each other's glossary and verified answers.
3. **Product tour is client-only** — gated by `localStorage` in the browser;
   clearing storage re-shows it, and it cannot be managed from the backend.

## Design

### High-level architecture

```
┌──────────────────────┐      ┌──────────────────────────┐
│   KnowledgeBase      │ ──→  │  KnowledgeService         │
│   (SQLite, db_id)    │      │  (PostgreSQL,             │
│                      │      │   user_id + db_id)        │
└──────────────────────┘      └──────────────────────────┘

┌──────────────────────┐      ┌──────────────────────────┐
│   ProductTour        │ ──→  │  User.tour_completed      │
│   (localStorage)     │      │  (PostgreSQL boolean)     │
└──────────────────────┘      └──────────────────────────┘
```

### 1. PostgreSQL models

Add seven new SQLAlchemy models to `backend/app/pgdatabase/models.py`:

**`VerifiedQA`** (`verified_qas`)
| column       | type     | notes             |
|--------------|----------|-------------------|
| id           | UUID PK  | default uuid7     |
| user_id      | UUID FK  | → users.id        |
| db_id        | String   | hash of DB URL    |
| question     | Text     |                   |
| sql          | Text     |                   |
| restatement  | Text     |                   |
| created_at   | DateTime |                   |

**`Glossary`** (`glossary_terms`)
| column    | type     |
|-----------|----------|
| id        | UUID PK  |
| user_id   | UUID FK  |
| db_id     | String   |
| term      | String   |
| maps_to   | String   |
| sql_hint  | String   |

**Five catalog tables** (all follow the same pattern):
- `CatalogColumn` (`catalog_columns`) — `user_id`, `db_id`, `table_name`, `column_name`, `description`
- `CatalogMetric` (`catalog_metrics`) — `user_id`, `db_id`, `name`, `description`, `sql_expression`
- `CatalogJoin` (`catalog_joins`) — `user_id`, `db_id`, `tables`, `join_condition`, `description`
- `CatalogSynonym` (`catalog_synonyms`) — `user_id`, `db_id`, `term`, `entity_type`, `entity_name`
- `CatalogValueMapping` (`catalog_value_mappings`) — `user_id`, `db_id`, `table_name`, `column_name`, `db_value`, `business_label`

**User model change:** add `tour_completed: Mapped[bool] = mapped_column(Boolean, default=False)`

All seven tables plus the User column are added in a single alembic migration
(`0005_add_knowledge_tables.py`).

### 2. KnowledgeService

New file `backend/app/pgdatabase/knowledge.py`:

```python
class KnowledgeService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def add_verified(self, user_id, db_id, question, sql, restatement="")
    async def get_verified(self, user_id, db_id) -> list[dict]
    async def count_verified(self, user_id, db_id) -> int
    async def retrieve_similar(self, user_id, db_id, q, k=3, threshold=0.25) -> list[dict]
    async def set_glossary(self, user_id, db_id, terms: list[dict])
    async def get_glossary(self, user_id, db_id) -> list[dict]
    async def set_catalog(self, user_id, db_id, catalog: dict)
    async def get_catalog(self, user_id, db_id) -> dict
    async def catalog_is_empty(self, user_id, db_id) -> bool
    async def trust_level(self, user_id, db_id) -> dict
```

Each method opens its own `async with self._session_factory() as session`,
queries using the SQLAlchemy models, and commits. The similarity scoring in
`retrieve_similar` (Jaccard + SequenceMatcher) is unchanged — fetch all
verified Q&As for the (user, db) and score in Python.

Return types match the existing `KnowledgeBase` exactly (list of dicts, dicts),
so no frontend changes are needed.

### 3. Dependency injection

In `server.py`:
```python
from backend.app.pgdatabase.knowledge import KnowledgeService
kbs = KnowledgeService(async_session)
app.state.kbs = kbs
```

In `dependencies.py`:
```python
def get_kb(request: Request):
    return request.app.state.kbs
```

All route and controller signatures stay the same — `kb` is still injected as a
dependency, just the implementation changes.

### 4. Controller changes

Every `kb.*` call in controllers adds `user_id` as the first parameter:

| Current | New |
|---------|-----|
| `kb.add_verified(db_id, q, sql, r)` | `kbs.add_verified(user_id, db_id, q, sql, r)` |
| `kb.get_glossary(db_id)` | `kbs.get_glossary(user_id, db_id)` |
| `kb.count_verified(db_id)` | `kbs.count_verified(user_id, db_id)` |
| etc. | etc. |

All controllers already have `user_id` from the auth dependency. `db_id` is
already obtained via `db.get_db_id(user_id)` at the call site. This is a
mechanical change across 35 call sites in 5 controller files:

- `controllers/database.py` (12 calls)
- `controllers/system.py` (4 calls)
- `controllers/query.py` (9 calls)
- `controllers/onboard.py` (4 calls)
- `controllers/catalog.py` (2 calls)

### 5. Product tour

**Backend:**
- `GET /api/state` includes `tour_completed: bool` from `User.tour_completed`
- New `POST /api/tour-complete` route sets `User.tour_completed = True`

**Frontend (`ProductTour.svelte`):**
- On mount, check `appState.tourCompleted` instead of `localStorage`
- On tour completion, `await apiCall("/api/tour-complete")` then `appState.tourCompleted = true`
- `appState.svelte.ts` gets a `tourCompleted` property initialized from `/api/state`

### 6. Data migration

Existing data in `~/.bolodb/knowledge.db` is keyed only by `db_id` without a
`user_id`. Since this is a multi-user application now, there is no safe way to
assign old knowledge to specific users. The SQLite file is left in place but
no longer read — users who reconnect will get fresh onboarding.

## Files changed

| File | Change |
|------|--------|
| `backend/app/pgdatabase/models.py` | Add 7 knowledge models + `User.tour_completed` |
| `backend/app/pgdatabase/knowledge.py` | **New** — `KnowledgeService` class |
| `backend/app/pgdatabase/__init__.py` | Export new models + KnowledgeService |
| `backend/app/server.py` | Instantiate `KnowledgeService` instead of `KnowledgeBase` |
| `backend/app/dependencies.py` | `get_kb` returns `KnowledgeService` |
| `backend/app/knowledge.py` | **Deleted** — replaced by `pgdatabase/knowledge.py` |
| `backend/app/controllers/database.py` | Add `user_id` to all `kb.*` calls |
| `backend/app/controllers/system.py` | Add `user_id` to all `kb.*` calls; add `tour_completed` to state |
| `backend/app/controllers/query.py` | Add `user_id` to all `kb.*` calls |
| `backend/app/controllers/onboard.py` | Add `user_id` to all `kb.*` calls |
| `backend/app/controllers/catalog.py` | Add `user_id` to all `kb.*` calls |
| `backend/app/routes/onboard.py` | (already passes kb correctly) |
| `backend/app/routes/system.py` | Add `POST /api/tour-complete` route |
| `backend/alembic/versions/0005_add_knowledge_tables.py` | **New** — migration |
| `frontend/src/lib/components/ProductTour.svelte` | Use `appState.tourCompleted` + API call |
| `frontend/src/lib/appState.svelte.ts` | Add `tourCompleted` property |
| Various test files | Update `kb` mock calls to pass `user_id` |

## Not changing

- All route signatures (still `kb=Depends(get_kb)`)
- All frontend components except `ProductTour.svelte`
- `DatabaseManager` class
- Knowledge tables are accessed asynchronously; callers remain synchronous
  (controllers call `await kb.method(...)`)
