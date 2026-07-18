"""Async PostgreSQL knowledge service — per-(user, database) storage for
verified Q&As, glossary, and semantic catalog."""

import logging

from difflib import SequenceMatcher

from sqlalchemy import select, delete, func
from sqlalchemy.exc import IntegrityError

from backend.app.pgdatabase.models import (
    VerifiedQA,
    Glossary,
    CatalogColumn,
    CatalogMetric,
    CatalogJoin,
    CatalogSynonym,
    CatalogValueMapping,
)
from backend.app.utils import _tokens

DUPLICATE_THRESHOLD = 0.92

logger = logging.getLogger(__name__)


def _similarity(a, b, tb=None, b_lower=None):
    """
    Compute a similarity score between two strings using token overlap and sequence similarity.

    Parameters:
        a (str): The first string to compare.
        b (str): The second string to compare.
        tb (set, optional): Precomputed tokens for `b`.
        b_lower (str, optional): Lowercase version of `b`.

    Returns:
        float: A weighted similarity score from 0.0 to 1.0.
    """
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
        """Initialize the service with the factory used to create asynchronous database sessions.

        Parameters:
                session_factory: A callable that creates asynchronous database sessions.
        """
        self._session_factory = session_factory

    async def add_verified(self, user_id, db_id, question, sql, restatement=""):
        """
        Add a verified question-and-answer entry unless a sufficiently similar question already exists.

        Parameters:
                user_id: Identifier of the user who owns the entry.
                db_id: Identifier of the database associated with the entry.
                question: Natural-language question associated with the SQL query.
                sql: SQL query that answers the question.
                restatement: Optional restatement of the question.

        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(VerifiedQA).where(
                    VerifiedQA.user_id == user_id, VerifiedQA.db_id == db_id
                )
            )
            tb = _tokens(question)
            b_lower = question.lower()
            for r in result.scalars().all():
                if _similarity(r.question, question, tb, b_lower) > DUPLICATE_THRESHOLD:
                    return
            session.add(
                VerifiedQA(
                    user_id=user_id,
                    db_id=db_id,
                    question=question,
                    sql=sql,
                    restatement=restatement,
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                logger.warning(
                    "Duplicate verified QA skipped (user=%s db=%s question=%s)",
                    user_id,
                    db_id,
                    question,
                )

    async def get_verified(self, user_id, db_id):
        """
        Retrieve verified question-and-answer entries for a user and database, with newest entries first.

        Parameters:
                user_id: Identifier of the user.
                db_id: Identifier of the database.

        Returns:
                A list of dictionaries containing each question, SQL statement, and restatement.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(VerifiedQA)
                .where(VerifiedQA.user_id == user_id, VerifiedQA.db_id == db_id)
                .order_by(VerifiedQA.created_at.desc())
            )
            return [
                {"question": r.question, "sql": r.sql, "restatement": r.restatement}
                for r in result.scalars().all()
            ]

    async def count_verified(self, user_id, db_id):
        """
        Count verified Q&A entries for a user and database.

        Parameters:
                user_id: Identifier of the user.
                db_id: Identifier of the database.

        Returns:
                int: The number of verified Q&A entries.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(func.count()).where(
                    VerifiedQA.user_id == user_id, VerifiedQA.db_id == db_id
                )
            )
            return result.scalar() or 0

    async def retrieve_similar(self, user_id, db_id, question, k=3, threshold=0.25):
        """
        Finds verified questions that are similar to the provided question.

        Parameters:
                question (str): The question to compare against stored verified questions.
                k (int): The maximum number of results to return.
                threshold (float): The minimum similarity score required for a result.

        Returns:
                list: Up to `k` matching verified Q&As, ordered by descending similarity, with each similarity rounded to three decimal places.
        """
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
        """
        Replace the glossary entries for a user and database.

        Parameters:
            terms (iterable): Glossary entry dictionaries containing `term`, `maps_to`, and `sql_hint`.
        """
        async with self._session_factory() as session:
            await session.execute(
                delete(Glossary).where(
                    Glossary.user_id == user_id, Glossary.db_id == db_id
                )
            )
            for t in terms:
                session.add(
                    Glossary(
                        user_id=user_id,
                        db_id=db_id,
                        term=t.get("term", ""),
                        maps_to=t.get("maps_to", ""),
                        sql_hint=t.get("sql_hint", ""),
                    )
                )
            await session.commit()

    async def get_glossary(self, user_id, db_id):
        """Retrieve glossary entries for a user and database.

        Parameters:
                user_id: The user identifier.
                db_id: The database identifier.

        Returns:
                list: Glossary entries containing each term, its mapped value, and SQL hint.
        """
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
        "column_descriptions": (
            CatalogColumn,
            ("table_name", "column_name", "description"),
            ("table", "column", "description"),
        ),
        "metrics": (
            CatalogMetric,
            ("name", "description", "sql_expression"),
            ("name", "description", "sql_expression"),
        ),
        "joins": (
            CatalogJoin,
            ("tables", "join_condition", "description"),
            ("tables", "join_condition", "description"),
        ),
        "synonyms": (
            CatalogSynonym,
            ("term", "entity_type", "entity_name"),
            ("term", "entity_type", "entity_name"),
        ),
        "value_maps": (
            CatalogValueMapping,
            ("table_name", "column_name", "db_value", "business_label"),
            ("table", "column", "db_value", "business_label"),
        ),
    }

    async def set_catalog(self, user_id, db_id, catalog):
        """
        Replace the specified catalog sections for a user and database.

        Parameters:
            catalog (dict): Catalog sections and entries to store. Sections included in the mapping replace their existing entries; omitted sections remain unchanged.
        """
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
        """
        Retrieve the semantic catalog entries for a user and database.

        Parameters:
            user_id: Identifier of the user whose catalog entries are retrieved.
            db_id: Identifier of the database whose catalog entries are retrieved.

        Returns:
            A dictionary mapping each catalog section to a list of entry dictionaries.
        """
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
        """Determine whether a user's catalog contains any entries.

        Parameters:
                user_id: The user whose catalog is checked.
                db_id: The database whose catalog is checked.

        Returns:
                bool: `True` if all catalog sections are empty, `False` otherwise.
        """
        catalog = await self.get_catalog(user_id, db_id)
        return not any(catalog.values())

    async def seed_sample(self, user_id, db_id):
        """Seed sample knowledge for a new sample-database connection.

        All operations run in one transaction so partial failures roll back
        cleanly and the guard (count_verified == 0) remains accurate.
        """
        async with self._session_factory() as session:
            count = await session.execute(
                select(func.count()).where(
                    VerifiedQA.user_id == user_id, VerifiedQA.db_id == db_id
                )
            )
            if count.scalar():
                return
            await session.execute(
                delete(Glossary).where(
                    Glossary.user_id == user_id, Glossary.db_id == db_id
                )
            )
            for t in [
                {
                    "term": "Revenue",
                    "maps_to": "orders.total_amount",
                    "sql_hint": "Sum of total_amount on orders with status = completed",
                },
                {
                    "term": "Active customer",
                    "maps_to": "orders.created_at",
                    "sql_hint": "A customer with at least one order in the last 90 days",
                },
                {
                    "term": "Top product",
                    "maps_to": "order_items.quantity",
                    "sql_hint": "Product ranked by units sold (sum of quantity)",
                },
            ]:
                session.add(Glossary(user_id=user_id, db_id=db_id, **t))
            for q, s, r in [
                (
                    "How many orders were completed last month?",
                    "SELECT COUNT(*) AS completed_orders\nFROM orders\nWHERE status = 'completed'\n  AND created_at >= date('now','start of month','-1 month')\n  AND created_at <  date('now','start of month');",
                    "Count of orders with status 'completed' created in the previous calendar month",
                ),
                (
                    "Which product category brings in the most revenue?",
                    "SELECT p.category, ROUND(SUM(oi.quantity*oi.unit_price)) AS revenue\nFROM order_items oi\nJOIN products p ON p.id = oi.product_id\nJOIN orders   o ON o.id = oi.order_id\nWHERE o.status = 'completed'\nGROUP BY p.category\nORDER BY revenue DESC;",
                    "Total revenue per product category, highest first",
                ),
                (
                    "How many customers do we have in each segment?",
                    "SELECT segment, COUNT(*) AS customers\nFROM customers\nGROUP BY segment\nORDER BY customers DESC;",
                    "Count of customers grouped by segment",
                ),
            ]:
                session.add(
                    VerifiedQA(
                        user_id=user_id, db_id=db_id, question=q, sql=s, restatement=r
                    )
                )
            await session.commit()

    async def trust_level(self, user_id, db_id):
        """
        Summarize the trust level for a user's database from its verified answers.

        Parameters:
                user_id: Identifier of the user.
                db_id: Identifier of the database.

        Returns:
                A dictionary containing the trust `level`, verified-answer count, percentage, and explanatory note.
        """
        n = await self.count_verified(user_id, db_id)
        if n >= 7:
            return {
                "level": "Trusted",
                "verified": n,
                "pct": 100,
                "note": "Answers shown directly; reasoning on tap.",
            }
        if n >= 3:
            return {
                "level": "Assisted",
                "verified": n,
                "pct": 55,
                "note": "Confident answers shown; novel ones get a second look.",
            }
        return {
            "level": "Supervised",
            "verified": n,
            "pct": max(8, n * 7),
            "note": "Every answer waits for your confirmation while it learns.",
        }
