"""Tests for verified-answer storage, similarity retrieval, and trust levels."""
import pytest
from app.knowledge import KnowledgeBase, _tokens, _similarity

DB_ID = "testdb"


def test_tokens():
    assert _tokens(None) == set()
    assert _tokens("") == set()
    assert _tokens("a b c d") == set()  # words length <= 1 are ignored
    assert _tokens("Hello World!") == {"hello", "world"}
    assert _tokens("It's a test, 123!") == {"it", "test", "123"}
    assert _tokens("Mixed_Case-And.Punctuation!") == {"mixed", "case", "and", "punctuation"}


def test_similarity():
    # Identical strings
    assert _similarity("Hello World", "Hello World") == 1.0
    assert _similarity("Hello World", "hello world") == 1.0  # Case insensitivity

    # Completely different (Jaccard will be 0.0, but SequenceMatcher ratio might be > 0.0)
    # "hello world" and "apples oranges" both have "es" / "le" / " l" / " o" etc.
    # So sequence ratio might be e.g., 0.32, thus sim > 0
    sim_diff = _similarity("xyz", "abc")
    assert sim_diff == 0.0

    # Partial overlap
    sim = _similarity("How many orders?", "How many customers?")
    assert 0.0 < sim < 1.0

    # Robustness against empty string
    # jaccard is 0.0 (since no tokens)
    # SequenceMatcher ratio is 1.0 for two empty strings
    # final score = 0.6 * 0.0 + 0.4 * 1.0 = 0.4
    assert _similarity("", "") == 0.4


@pytest.fixture
def kb(tmp_path):
    return KnowledgeBase(tmp_path / "kb.sqlite")


def test_add_and_retrieve_verified(kb):
    kb.add_verified(DB_ID, "How many orders were placed last month?",
                    "SELECT COUNT(*) FROM orders", "Counted recent orders")
    entries = kb.get_verified(DB_ID)
    assert len(entries) == 1
    assert entries[0]["question"] == "How many orders were placed last month?"


def test_near_duplicate_questions_are_not_stored_twice(kb):
    kb.add_verified(DB_ID, "How many orders were placed last month?", "SELECT COUNT(*) FROM orders")
    kb.add_verified(DB_ID, "How many orders were placed last month", "SELECT COUNT(*) FROM orders")
    assert kb.count_verified(DB_ID) == 1


def test_distinct_questions_are_both_stored(kb):
    kb.add_verified(DB_ID, "How many orders were placed last month?", "SELECT COUNT(*) FROM orders")
    kb.add_verified(DB_ID, "What is our total revenue this year?", "SELECT SUM(total) FROM orders")
    assert kb.count_verified(DB_ID) == 2


def test_retrieve_similar_ranks_closest_first(kb):
    kb.add_verified(DB_ID, "How many customers signed up this month?", "SELECT COUNT(*) FROM customers")
    kb.add_verified(DB_ID, "What is our total revenue?", "SELECT SUM(total) FROM orders")
    results = kb.retrieve_similar(DB_ID, "How many customers joined this month?", k=3)
    assert results
    assert results[0]["question"] == "How many customers signed up this month?"
    assert results[0]["similarity"] >= results[-1]["similarity"]


def test_retrieve_similar_respects_threshold_and_k(kb):
    kb.add_verified(DB_ID, "Top selling products by revenue", "SELECT * FROM products")
    kb.add_verified(DB_ID, "List all employees in HR", "SELECT * FROM employees")
    results = kb.retrieve_similar(DB_ID, "Completely unrelated gibberish xyzzy", k=3, threshold=0.25)
    assert results == []


def test_retrieve_similar_is_scoped_to_db_id(kb):
    kb.add_verified("db_a", "How many orders this month?", "SELECT COUNT(*) FROM orders")
    assert kb.retrieve_similar("db_b", "How many orders this month?") == []
    assert kb.count_verified("db_b") == 0


def test_glossary_round_trip_replaces_existing(kb):
    kb.set_glossary(DB_ID, [{"term": "active", "maps_to": "status = 'active'", "sql_hint": ""}])
    kb.set_glossary(DB_ID, [{"term": "churned", "maps_to": "status = 'cancelled'", "sql_hint": ""}])
    glossary = kb.get_glossary(DB_ID)
    assert len(glossary) == 1
    assert glossary[0]["term"] == "churned"


@pytest.mark.parametrize("verified,expected_level", [
    (0, "Supervised"),
    (2, "Supervised"),
    (3, "Assisted"),
    (6, "Assisted"),
    (7, "Trusted"),
    (20, "Trusted"),
])
def test_trust_level_thresholds(kb, monkeypatch, verified, expected_level):
    monkeypatch.setattr(kb, "count_verified", lambda db_id: verified)
    trust = kb.trust_level(DB_ID)
    assert trust["level"] == expected_level
    assert trust["verified"] == verified
