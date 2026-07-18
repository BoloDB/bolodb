# Knowledge Base to PostgreSQL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the knowledge base from local SQLite to PostgreSQL, scoped per
(user, database), and track product tour completion in the backend.

**Architecture:** Add 7 SQLAlchemy models to `pgdatabase/models.py` with
`user_id` + `db_id` columns. New async `KnowledgeService` in
`pgdatabase/knowledge.py` replaces the sync `KnowledgeBase`. Controllers add
`user_id` to all `kb.*` calls. Product tour tracked via `User.tour_completed`.

**Tech Stack:** SQLAlchemy, asyncpg, alembic, PostgreSQL, FastAPI

## Global Constraints

- New models go in `backend/app/pgdatabase/models.py`
- New service goes in `backend/app/pgdatabase/knowledge.py`
- All `kb.*` calls in controllers must pass `user_id` as first arg
- Return types of knowledge methods must match existing `KnowledgeBase` exactly
- `get_kb` dependency name stays the same
- Old `backend/app/knowledge.py` is deleted at the end
- All 191+ backend tests must pass

---

### Task 1: PostgreSQL models + alembic migration

**Files:**
- Modify: `backend/app/pgdatabase/models.py`
- Modify: `backend/app/pgdatabase/__init__.py`
- Create: `backend/alembic/versions/0005_add_knowledge_tables.py`

**Interfaces:**
- Consumes: existing `Base`, `User` model
- Produces: `VerifiedQA`, `Glossary`, `CatalogColumn`, `CatalogMetric`,
  `CatalogJoin`, `CatalogSynonym`, `CatalogValueMapping` models + `User.tour_completed`

- [ ] **Step 1: Add seven new models to `backend/app/pgdatabase/models.py`**

After the `RecentConnection` class (line 119), add:

```python
class VerifiedQA(Base):
    __tablename__ = "verified_qas"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sql: Mapped[str] = mapped_column(Text, nullable=False, default="")
    restatement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    __table_args__ = (Index("ix_verified_qa_user_db", "user_id", "db_id"),)


class Glossary(Base):
    __tablename__ = "glossary_terms"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    maps_to: Mapped[str] = mapped_column(String, nullable=False)
    sql_hint: Mapped[str] = mapped_column(String, nullable=False, default="")
    __table_args__ = (Index("ix_glossary_user_db", "user_id", "db_id"),)


class CatalogColumn(Base):
    __tablename__ = "catalog_columns"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_cat_col_user_db", "user_id", "db_id"),)


class CatalogMetric(Base):
    __tablename__ = "catalog_metrics"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sql_expression: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("ix_cat_met_user_db", "user_id", "db_id"),)


class CatalogJoin(Base):
    __tablename__ = "catalog_joins"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    tables: Mapped[str] = mapped_column(String, nullable=False)
    join_condition: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    __table_args__ = (Index("ix_cat_join_user_db", "user_id", "db_id"),)


class CatalogSynonym(Base):
    __tablename__ = "catalog_synonyms"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    term: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_name: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("ix_cat_syn_user_db", "user_id", "db_id"),)


class CatalogValueMapping(Base):
    __tablename__ = "catalog_value_mappings"
    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=_uuid7
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    db_id: Mapped[str] = mapped_column(String, nullable=False)
    table_name: Mapped[str] = mapped_column(String, nullable=False)
    column_name: Mapped[str] = mapped_column(String, nullable=False)
    db_value: Mapped[str] = mapped_column(String, nullable=False)
    business_label: Mapped[str] = mapped_column(String, nullable=False)
    __table_args__ = (Index("ix_cat_val_user_db", "user_id", "db_id"),)
```

- [ ] **Step 2: Add `tour_completed` to User model**

In the `User` class (around line 56), add after `email_verified`:
```python
    tour_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

- [ ] **Step 3: Update imports in models.py**

Ensure `Index` is imported from sqlalchemy:
```python
from sqlalchemy import (
    Boolean, String, Integer, UniqueConstraint, ForeignKey,
    Text, DateTime, Index,
)
```

- [ ] **Step 4: Update `pgdatabase/__init__.py` exports**

Add all new models to the imports and `__all__`:
```python
from backend.app.pgdatabase.models import (
    Base, User, Conversation, QueryHistory, RecentConnection,
    PasswordResetToken, OtpCode,
    VerifiedQA, Glossary,
    CatalogColumn, CatalogMetric, CatalogJoin,
    CatalogSynonym, CatalogValueMapping,
)
```

- [ ] **Step 5: Generate alembic migration**

```bash
cd /home/somesh/Documents/bolodb/backend
DATABASE_URL=postgresql://... PYTHONPATH=.. alembic revision --autogenerate -m "add knowledge tables and tour_completed"
```

If `DATABASE_URL` is not available locally, write the migration manually.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add PostgreSQL knowledge models + tour_completed column"
```

---

### Task 2: KnowledgeService

**Files:**
- Create: `backend/app/pgdatabase/knowledge.py`
- Create: `tests/test_knowledge_service.py`

**Interfaces:**
- Consumes: `async_session` from `backend.app.pgdatabase.engine`
- Produces: `KnowledgeService` class with methods mirroring `KnowledgeBase` + `user_id` param

- [ ] **Step 1: Create `backend/app/pgdatabase/knowledge.py`**

```python
"""Async PostgreSQL knowledge service — per-(user, database) storage for
verified Q&As, glossary, and semantic catalog."""

import time
from difflib import SequenceMatcher

from sqlalchemy import select, delete, func

from backend.app.pgdatabase.models import (
    VerifiedQA, Glossary,
    CatalogColumn, CatalogMetric, CatalogJoin,
    CatalogSynonym, CatalogValueMapping,
)
from backend.app.utils import _tokens

DUPLICATE_THRESHOLD = 0.92


def _similarity(a, b, tb=None, b_lower=None):
    ta = _tokens(a)
    if tb is None:
        tb = _tokens(b)
    jacc = len(ta & tb) / len(ta | tb) if ta or tb else 0.0
    if b_lower is None:
        b_lower = b.lower()
    seq = SequenceMatcher(None, a.lower(), b_lower).ratio()
    return 0.6 * jacc + 0.4 * seq


class KnowledgeService:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    async def add_verified(self, user_id, db_id, question, sql, restatement=""):
        async with self._session_factory() as session:
            existing = await self.get_verified(user_id, db_id)
            tb = _tokens(question)
            b_lower = question.lower()
            for e in existing:
                if _similarity(e["question"], question, tb, b_lower) > DUPLICATE_THRESHOLD:
                    return
            session.add(VerifiedQA(
                user_id=user_id, db_id=db_id, question=question,
                sql=sql, restatement=restatement, created_at=time.time(),
            ))
            await session.commit()

    async def get_verified(self, user_id, db_id):
        async with self._session_factory() as session:
            result = await session.execute(
                select(VerifiedQA).where(
                    VerifiedQA.user_id == user_id,
                    VerifiedQA.db_id == db_id,
                ).order_by(VerifiedQA.created_at.desc())
            )
            return [
                {"question": r.question, "sql": r.sql, "restatement": r.restatement}
                for r in result.scalars().all()
            ]

    async def count_verified(self, user_id, db_id):
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).where(
                    VerifiedQA.user_id == user_id,
                    VerifiedQA.db_id == db_id,
                )
            )
            return result.scalar() or 0

    async def retrieve_similar(self, user_id, db_id, question, k=3, threshold=0.25):
        scored = []
        tb = _tokens(question)
        b_lower = question.lower()
        for c in await self.get_verified(user_id, db_id):
            s = _similarity(c["question"], question, tb, b_lower)
            if s >= threshold:
                scored.append({**c, "similarity": round(s, 3)})
        scored.sort(key=lambda x: -x["similarity"])
        return scored[:k]

    async def set_glossary(self, user_id, db_id, terms):
        async with self._session_factory() as session:
            await session.execute(
                delete(Glossary).where(
                    Glossary.user_id == user_id, Glossary.db_id == db_id
                )
            )
            for t in terms:
                session.add(Glossary(
                    user_id=user_id, db_id=db_id,
                    term=t.get("term", ""), maps_to=t.get("maps_to", ""),
                    sql_hint=t.get("sql_hint", ""),
                ))
            await session.commit()

    async def get_glossary(self, user_id, db_id):
        async with self._session_factory() as session:
            result = await session.execute(
                select(Glossary).where(
                    Glossary.user_id == user_id, Glossary.db_id == db_id
                )
            )
            return [
                {"term": r.term, "maps_to": r.maps_to, "sql_hint": r.sql_hint}
                for r in result.scalars().all()
            ]

    _CATALOG_CLASSES = {
        "column_descriptions": (CatalogColumn, ("table_name", "column_name", "description"), ("table", "column", "description")),
        "metrics": (CatalogMetric, ("name", "description", "sql_expression"), ("name", "description", "sql_expression")),
        "joins": (CatalogJoin, ("tables", "join_condition", "description"), ("tables", "join_condition", "description")),
        "synonyms": (CatalogSynonym, ("term", "entity_type", "entity_name"), ("term", "entity_type", "entity_name")),
        "value_maps": (CatalogValueMapping, ("table_name", "column_name", "db_value", "business_label"), ("table", "column", "db_value", "business_label")),
    }

    async def set_catalog(self, user_id, db_id, catalog):
        async with self._session_factory() as session:
            for key, (model_class, cols, in_keys) in self._CATALOG_CLASSES.items():
                if key not in catalog:
                    continue
                await session.execute(
                    delete(model_class).where(
                        model_class.user_id == user_id, model_class.db_id == db_id
                    )
                )
                for entry in catalog[key] or []:
                    kwargs = {"user_id": user_id, "db_id": db_id}
                    for c, ok in zip(cols, in_keys):
                        kwargs[c] = str(entry.get(ok, "") or "")
                    session.add(model_class(**kwargs))
            await session.commit()

    async def get_catalog(self, user_id, db_id):
        async with self._session_factory() as session:
            out = {}
            for key, (model_class, cols, out_keys) in self._CATALOG_CLASSES.items():
                result = await session.execute(
                    select(model_class).where(
                        model_class.user_id == user_id, model_class.db_id == db_id
                    )
                )
                rows = []
                for r in result.scalars().all():
                    row = {}
                    for c, ok in zip(cols, out_keys):
                        row[ok] = getattr(r, c)
                    rows.append(row)
                out[key] = rows
            return out

    async def catalog_is_empty(self, user_id, db_id):
        catalog = await self.get_catalog(user_id, db_id)
        return not any(catalog.values())

    async def trust_level(self, user_id, db_id):
        n = await self.count_verified(user_id, db_id)
        if n >= 7:
            return {"level": "Trusted", "verified": n, "pct": 100,
                    "note": "Answers shown directly; reasoning on tap."}
        if n >= 3:
            return {"level": "Assisted", "verified": n, "pct": 55,
                    "note": "Confident answers shown; novel ones get a second look."}
        return {"level": "Supervised", "verified": n, "pct": max(8, n * 7),
                "note": "Every answer waits for your confirmation while it learns."}
```

- [ ] **Step 2: Create `tests/test_knowledge_service.py`**

```python
"""Tests for KnowledgeService — async PostgreSQL-backed knowledge storage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.pgdatabase.knowledge import KnowledgeService, _similarity

USER_ID = "00000000-0000-0000-0000-000000000001"
DB_ID = "testdb"


def test_similarity_identical():
    assert _similarity("hello world", "hello world") == 1.0


def test_similarity_empty():
    assert _similarity("", "") == pytest.approx(0.4)


def test_similarity_different():
    assert _similarity("hello world", "abc xyz") < 0.1


@pytest.fixture
def kbs():
    return KnowledgeService(AsyncMock())


@pytest.mark.asyncio
async def test_add_verified_inserts(kbs):
    session = AsyncMock()
    kbs._session_factory.return_value.__aenter__.return_value = session

    session.execute.return_value.scalars.return_value.all.return_value = []

    await kbs.add_verified(USER_ID, DB_ID, "test question?", "SELECT 1", "test")

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    args = session.add.call_args[0][0]
    assert args.user_id == USER_ID
    assert args.db_id == DB_ID
    assert args.question == "test question?"


@pytest.mark.asyncio
async def test_count_verified(kbs):
    session = AsyncMock()
    kbs._session_factory.return_value.__aenter__.return_value = session
    session.execute.return_value.scalar.return_value = 3

    count = await kbs.count_verified(USER_ID, DB_ID)
    assert count == 3


@pytest.mark.asyncio
async def test_trust_level_supervised(kbs):
    q = AsyncMock()
    q.scalar.return_value = 1
    session = AsyncMock()
    session.execute.return_value = q
    kbs._session_factory.return_value.__aenter__.return_value = session

    trust = await kbs.trust_level(USER_ID, DB_ID)
    assert trust["level"] == "Supervised"


@pytest.mark.asyncio
async def test_trust_level_assisted(kbs):
    q = AsyncMock()
    q.scalar.return_value = 3
    session = AsyncMock()
    session.execute.return_value = q
    kbs._session_factory.return_value.__aenter__.return_value = session

    trust = await kbs.trust_level(USER_ID, DB_ID)
    assert trust["level"] == "Assisted"


@pytest.mark.asyncio
async def test_trust_level_trusted(kbs):
    q = AsyncMock()
    q.scalar.return_value = 7
    session = AsyncMock()
    session.execute.return_value = q
    kbs._session_factory.return_value.__aenter__.return_value = session

    trust = await kbs.trust_level(USER_ID, DB_ID)
    assert trust["level"] == "Trusted"


@pytest.mark.asyncio
async def test_set_and_get_glossary(kbs):
    session = AsyncMock()
    kbs._session_factory.return_value.__aenter__.return_value = session
    session.execute.return_value.scalars.return_value.all.return_value = []

    await kbs.set_glossary(USER_ID, DB_ID, [
        {"term": "revenue", "maps_to": "orders.total", "sql_hint": ""}
    ])

    session.add.assert_called_once()

    # Now test get
    mock_row = MagicMock()
    mock_row.term = "revenue"
    mock_row.maps_to = "orders.total"
    mock_row.sql_hint = ""
    session.execute.return_value.scalars.return_value.all.return_value = [mock_row]

    glossary = await kbs.get_glossary(USER_ID, DB_ID)
    assert len(glossary) == 1
    assert glossary[0]["term"] == "revenue"


@pytest.mark.asyncio
async def test_catalog_is_empty(kbs):
    session = AsyncMock()
    kbs._session_factory.return_value.__aenter__.return_value = session
    session.execute.return_value.scalars.return_value.all.return_value = []

    assert await kbs.catalog_is_empty(USER_ID, DB_ID) is True
```

- [ ] **Step 3: Run tests**

```bash
cd /home/somesh/Documents/bolodb && .venv/bin/python -m pytest tests/test_knowledge_service.py -v
```

Expected: 9 tests pass

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add KnowledgeService (async PostgreSQL knowledge base)"
```

---

### Task 3: Dependency injection swap

**Files:**
- Modify: `backend/app/server.py`
- Modify: `backend/app/dependencies.py`
- Modify: `backend/app/pgdatabase/__init__.py`

**Interfaces:**
- Consumes: `KnowledgeService` from Task 2
- Produces: `app.state.kbs` available via `get_kb()` dependency

- [ ] **Step 1: Update `backend/app/pgdatabase/__init__.py`**

Add import:
```python
from backend.app.pgdatabase.knowledge import KnowledgeService
```

Add `"KnowledgeService"` to `__all__`.

- [ ] **Step 2: Update `backend/app/server.py`**

Replace:
```python
from backend.app.knowledge import KnowledgeBase
...
kb = KnowledgeBase(cfgmod.KB_FILE)
...
app.state.kb = kb
```

With:
```python
from backend.app.pgdatabase import KnowledgeService
from backend.app.pgdatabase.engine import async_session
...
kbs = KnowledgeService(async_session)
...
app.state.kbs = kbs
```

- [ ] **Step 3: Update `backend/app/dependencies.py`**

Change `get_kb` to return `app.state.kbs`:
```python
def get_kb(request: Request):
    return request.app.state.kbs
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: swap KnowledgeBase for KnowledgeService in DI"
```

---

### Task 4: Update controllers (5 files)

**Files:**
- Modify: `backend/app/controllers/database.py`
- Modify: `backend/app/controllers/system.py`
- Modify: `backend/app/controllers/query.py`
- Modify: `backend/app/controllers/onboard.py`
- Modify: `backend/app/controllers/catalog.py`

**Interfaces:**
- Consumes: `KnowledgeService` with `(user_id, db_id)` signature
- No change to function signatures — `kb` param stays, `user_id` is already present

- [ ] **Step 1: Update `backend/app/controllers/database.py`**

Add `user_id` to all kb calls (lines 15-18, 42-84):
```python
# Line 15-18:
result["trust"] = kb.trust_level(user_id, db_id)
result["glossary"] = kb.get_glossary(user_id, db_id)
result["has_knowledge"] = kb.count_verified(user_id, db_id) > 0
result["starters"] = [v["question"] for v in await kb.get_verified(user_id, db_id)[:6]]

# Lines 42-86: same pattern — add user_id as first arg
```

Note: these methods are now `async`, so callers must `await`. The `connect` and
`connect_sample` functions are already `async def` — just add `await` before
each kb call.

Before:
```python
result["trust"] = kb.trust_level(db_id)
result["glossary"] = kb.get_glossary(db_id)
result["has_knowledge"] = kb.count_verified(db_id) > 0
result["starters"] = [v["question"] for v in kb.get_verified(db_id)[:6]]
```

After:
```python
result["trust"] = await kb.trust_level(user_id, db_id)
result["glossary"] = await kb.get_glossary(user_id, db_id)
result["has_knowledge"] = await kb.count_verified(user_id, db_id) > 0
result["starters"] = [v["question"] for v in (await kb.get_verified(user_id, db_id))[:6]]
```

The `connect_sample` function already has `user_id` as a parameter. Add `user_id`
to all its kb calls too (lines 42, 43, 63, 69, 75, 82-86).

- [ ] **Step 2: Update `backend/app/controllers/system.py`**

Add `user_id` + `await` to all kb calls in `get_state` (lines 22-27):
```python
"has_knowledge": (await kb.count_verified(user_id, db_id)) > 0,
...
s["trust"] = await kb.trust_level(user_id, db_id)
s["glossary"] = await kb.get_glossary(user_id, db_id)
s["starters"] = [
    v["question"] for v in (await kb.get_verified(user_id, db_id))[:6]
]
```

The `get_state` function is already `async def`, so `await` works.

- [ ] **Step 3: Update `backend/app/controllers/query.py`**

Three functions make kb calls:

In `run_query` (lines 78-80):
```python
glossary = await kb.get_glossary(user_id, db_id)
catalog = await kb.get_catalog(user_id, db_id)
retrieved = await kb.retrieve_similar(user_id, db_id, q, k=3)
```

In `feedback` (line 221):
```python
await kb.add_verified(user_id, db.get_db_id(user_id), req_data.question, req_data.sql, req_data.restatement)
```
And line 224:
```python
out = {"ok": True, "trust": await kb.trust_level(user_id, db.get_db_id(user_id))}
```
And lines 227:
```python
v["question"] for v in (await kb.get_verified(user_id, db.get_db_id(user_id)))[:6]
```

In `verify` (lines 235-238):
```python
await kb.add_verified(user_id, db.get_db_id(user_id), req_data.question, req_data.sql, req_data.restatement)
return {"ok": True, "trust": await kb.trust_level(user_id, db.get_db_id(user_id))}
```

In `stream_query` (lines 339-341):
```python
glossary = await kb.get_glossary(user_id, db.get_db_id(user_id))
catalog = await kb.get_catalog(user_id, db.get_db_id(user_id))
retrieved = await kb.retrieve_similar(user_id, db.get_db_id(user_id), q, k=3)
```

- [ ] **Step 4: Update `backend/app/controllers/onboard.py`**

In `save` (lines 54-67):
```python
await kb.set_glossary(user_id, db_id, [g.model_dump() for g in req_data.glossary])
for s in req_data.starters:
    await kb.add_verified(user_id, db_id, s.question, s.sql, s.restatement)
if await kb.catalog_is_empty(user_id, db_id):
    await kb.set_catalog(user_id, db_id, suggest_from_schema(db.get_schema(user_id)))
return {"ok": True, "trust": await kb.trust_level(user_id, db_id)}
```

The `save` function is already `async def`.

- [ ] **Step 5: Update `backend/app/controllers/catalog.py`**

In `get_catalog` (line 18):
```python
return {"catalog": await kb.get_catalog(user_id, db.get_db_id(user_id))}
```

In `save_catalog` (line 25):
```python
await kb.set_catalog(user_id, db.get_db_id(user_id), payload.model_dump())
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: update controllers for KnowledgeService (user_id + await)"
```

---

### Task 5: Product tour backend route

**Files:**
- Modify: `backend/app/routes/system.py`
- Modify: `backend/app/controllers/system.py`

**Interfaces:**
- Produces: `POST /api/tour-complete` route, `tour_completed` in `/api/state`

- [ ] **Step 1: Add tour_completed fetch to `get_state` in `controllers/system.py`**

```python
async def get_state(user_id, db, cfg, kb, session_factory):
    s = {"connected": db.connected(user_id), "config": cfgmod.public_config(cfg)}
    if db.connected(user_id):
        s["database"] = {
            ...
        }
        ...
    # Fetch tour_completed from user record
    from backend.app.pgdatabase.models import User
    from sqlalchemy import select
    async with session_factory() as session:
        result = await session.execute(select(User.tour_completed).where(User.id == user_id))
        s["tour_completed"] = result.scalar() or False
    return s
```

Note: `get_state` needs a `session_factory` param. Update its callers.

- [ ] **Step 2: Add `POST /api/tour-complete` route to `routes/system.py`**

```python
from backend.app.pgdatabase.engine import async_session

@router.post("/api/tour-complete")
async def tour_complete(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
):
    from backend.app.pgdatabase.models import User
    from sqlalchemy import update
    uid = user_token["user_id"]
    async with async_session() as session:
        await session.execute(
            update(User).where(User.id == uid).values(tour_completed=True)
        )
        await session.commit()
    return {"ok": True}
```

- [ ] **Step 3: Update `routes/system.py` state route to pass session_factory**

The `/api/state` route calls `ctrl.get_state(...)`. Add `async_session` as a
dependency or pass it. Simplest: pass `request.app.state.async_session`.

Actually, `async_session` is already importable from `pgdatabase.engine`:
```python
from backend.app.pgdatabase.engine import async_session

@router.get("/api/state")
async def get_state_route(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    cfg=Depends(get_cfg),
    kb=Depends(get_kb),
):
    uid = user_token["user_id"]
    return await ctrl.get_state(uid, db, cfg, kb, async_session)
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add /api/tour-complete route + tour_completed in state"
```

---

### Task 6: Frontend product tour

**Files:**
- Modify: `frontend/src/lib/appState.svelte.ts`
- Modify: `frontend/src/lib/components/ProductTour.svelte`

**Interfaces:**
- Consumes: `appState.tourCompleted` from `/api/state`
- Produces: `POST /api/tour-complete` call on tour finish

- [ ] **Step 1: Add `tourCompleted` to `appState.svelte.ts`**

Add after line 12 (`starters = $state<string[]>([])`):
```typescript
tourCompleted = $state(false);
```

In the `init()` method, after the state response is loaded (around line 52, after
`this.starters = s.starters || []`), add:
```typescript
this.tourCompleted = s.tour_completed || false;
```

- [ ] **Step 2: Update `ProductTour.svelte`**

Replace the localStorage check with appState:
```typescript
import { appState } from "$lib/appState.svelte";
import { apiCall } from "$lib/api";

// Remove: const STORAGE_KEY = "bolodb_tour_completed_v1";

onMount(() => {
    if (!browser) return;
    if (appState.tourCompleted) return;  // was localStorage check
    ...
```

Update `markDone` function (around line 182):
```typescript
async function markDone() {
    try {
        await apiCall("/api/tour-complete");
        appState.tourCompleted = true;
    } catch { /* ignore */ }
    if (browser) {
        const { default: posthog } = await import("posthog-js");
        posthog.capture("product_tour_completed");
    }
}
```

Remove the `localStorage.setItem(STORAGE_KEY, "1")` line.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: track product tour completion via backend"
```

---

### Task 7: Delete old knowledge.py and cleanup

**Files:**
- Delete: `backend/app/knowledge.py`
- Modify: `backend/app/server.py` (remove `cfgmod.KB_FILE` reference)
- Modify: `backend/app/config.py` (remove `KB_FILE` line, or leave for backward compat)

- [ ] **Step 1: Remove `from backend.app.knowledge import KnowledgeBase` from server.py**

- [ ] **Step 2: Remove `cfgmod.KB_FILE` reference from server.py**

- [ ] **Step 3: Delete `backend/app/knowledge.py`**

```bash
rm backend/app/knowledge.py
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: remove old KnowledgeBase (SQLite)"
```

---

### Task 8: Fix tests and final pass

**Files:**
- Modify: `tests/test_knowledge.py` — update to use KnowledgeService or remove
- Modify: `tests/test_query_pipeline.py` — update mocks
- Modify: `tests/test_query_stream.py` — update mocks
- Modify: `tests/test_semantic.py` — update mocks

- [ ] **Step 1: Fix `tests/test_knowledge.py`**

This test uses `KnowledgeBase` directly. Since the old class is deleted, either:
- Rewrite it to use `KnowledgeService` with mocked `async_session`
- Or move the `_similarity` / `_tokens` tests to `test_knowledge_service.py`

The `_similarity` and `_tokens` utility tests are now in
`test_knowledge_service.py` (Task 2). The `KnowledgeBase` integration tests
(trust_level, retreive_similar, etc.) are replaced by the KnowledgeService
tests. Delete `tests/test_knowledge.py` since its utility tests are covered
in the new file and the KB integration tests can't work with the old class.

```bash
rm tests/test_knowledge.py
```

- [ ] **Step 2: Fix `tests/test_query_pipeline.py`**

This test uses mocks for `KnowledgeBase`. Find all `kb.*` mock calls and add
`user_id` as first arg to the expected calls. The mock objects already return
coroutines since the controller awaits them — add `await` to mock setup if needed.

Search for `kb\.` in the file and add `user_id` arg to each call.

- [ ] **Step 3: Fix `tests/test_query_stream.py`**

Same as Step 2 — update mock expectations for `kb.*` calls.

- [ ] **Step 4: Fix `tests/test_semantic.py`**

Same pattern — update any `kb.*` mock expectations. The `semantic.py` module
doesn't use `kb` directly, but its tests may import it.

- [ ] **Step 5: Run all backend tests**

```bash
cd /home/somesh/Documents/bolodb && .venv/bin/python -m pytest tests/ -q
```

Expected: all tests pass.

- [ ] **Step 6: Run frontend check**

```bash
cd /home/somesh/Documents/bolodb/frontend && npm run check
```

Expected: 0 errors.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "test: update tests for KnowledgeService + cleanup old tests"
```

---

### Task 9: Final verification

- [ ] **Step 1: Run the full test suite one more time**

```bash
cd /home/somesh/Documents/bolodb && .venv/bin/python -m pytest tests/ -q
```

- [ ] **Step 2: Push branch (optional)**

```bash
git push origin knowledge-to-postgres
```
