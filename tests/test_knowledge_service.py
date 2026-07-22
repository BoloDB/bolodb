"""Tests for KnowledgeService — async PostgreSQL-backed knowledge storage."""

import pytest
from unittest.mock import AsyncMock, MagicMock, Mock

from backend.app.pgdatabase.knowledge import KnowledgeService, _similarity

USER_ID = "00000000-0000-0000-0000-000000000001"
DB_ID = "testdb"


def test_similarity_identical():
    assert _similarity("hello world", "hello world") == 1.0


def test_similarity_empty():
    assert _similarity("", "") == pytest.approx(0.4)


def test_similarity_different():
    assert _similarity("hello world", "abc xyz") < 0.1


def test_similarity_partial():
    sim = _similarity("How many orders?", "How many customers?")
    assert 0.0 < sim < 1.0


@pytest.fixture
def kbs():
    sf = Mock()
    kbs = KnowledgeService(sf)
    return kbs, sf


def _session(sf):
    """
    Configure and return an asynchronous session mock for use with an async context manager.

    Parameters:
        sf: Session factory mock whose return value is configured to the session mock.

    Returns:
        The configured asynchronous session mock.
    """
    s = AsyncMock()
    sf.return_value = s
    s.__aenter__.return_value = s
    return s


def _result(value):
    """Create a mock result object whose scalar method returns the specified value.

    Parameters:
        value: The value returned by the mock result's scalar method.

    Returns:
        A mock result object configured to return value from scalar.
    """
    r = Mock()
    r.scalar.return_value = value
    return r


def _rows(rows):
    """Create an object that mimics a SQLAlchemy result with scalars().all()."""
    r = Mock()
    r.scalars.return_value.all.return_value = rows
    return r


@pytest.mark.asyncio
async def test_add_verified_inserts(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _rows([])

    await kbs.add_verified(USER_ID, DB_ID, "test question?", "SELECT 1", "test")

    session.add.assert_called_once()
    session.commit.assert_awaited_once()
    args = session.add.call_args[0][0]
    assert args.workspace_id == USER_ID
    assert args.db_id == DB_ID
    assert args.question == "test question?"


@pytest.mark.asyncio
async def test_count_verified(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _result(3)

    count = await kbs.count_verified(USER_ID, DB_ID)
    assert count == 3


@pytest.mark.asyncio
async def test_get_verified_returns_dicts(kbs):
    kbs, sf = kbs
    session = _session(sf)
    mock_row = MagicMock()
    mock_row.question = "test q"
    mock_row.sql = "SELECT 1"
    mock_row.restatement = "test"
    session.execute.return_value = _rows([mock_row])

    entries = await kbs.get_verified(USER_ID, DB_ID)
    assert len(entries) == 1
    assert entries[0]["question"] == "test q"


@pytest.mark.asyncio
async def test_trust_level_supervised(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _result(1)

    trust = await kbs.trust_level(USER_ID, DB_ID)
    assert trust["level"] == "Supervised"


@pytest.mark.asyncio
async def test_trust_level_assisted(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _result(3)

    trust = await kbs.trust_level(USER_ID, DB_ID)
    assert trust["level"] == "Assisted"


@pytest.mark.asyncio
async def test_trust_level_trusted(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _result(7)

    trust = await kbs.trust_level(USER_ID, DB_ID)
    assert trust["level"] == "Trusted"


@pytest.mark.asyncio
async def test_set_and_get_glossary(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _rows([])

    await kbs.set_glossary(
        USER_ID, DB_ID, [{"term": "revenue", "maps_to": "orders.total", "sql_hint": ""}]
    )

    session.add.assert_called_once()
    session.commit.assert_awaited_once()

    mock_row = MagicMock()
    mock_row.term = "revenue"
    mock_row.maps_to = "orders.total"
    mock_row.sql_hint = ""
    session.execute.return_value = _rows([mock_row])

    glossary = await kbs.get_glossary(USER_ID, DB_ID)
    assert len(glossary) == 1
    assert glossary[0]["term"] == "revenue"


@pytest.mark.asyncio
async def test_catalog_is_empty(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _rows([])

    assert await kbs.catalog_is_empty(USER_ID, DB_ID) is True


@pytest.mark.asyncio
async def test_retrieve_similar_empty(kbs):
    kbs, sf = kbs
    session = _session(sf)
    session.execute.return_value = _rows([])

    results = await kbs.retrieve_similar(USER_ID, DB_ID, "test", k=3, threshold=0.25)
    assert results == []
