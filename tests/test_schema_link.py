"""Tests for model budgeting, confidence scoring, and table linking."""

import pytest
from backend.app.schema_link import (
    model_budget,
    compute_confidence,
    link_relevant_tables,
)


@pytest.fixture
def small_schema():
    return {
        "users": {
            "columns": [{"name": "id"}, {"name": "name"}],
            "row_count": 100,
            "foreign_keys": [],
            "distinct_values": {},
        },
        "orders": {
            "columns": [{"name": "id"}, {"name": "user_id"}],
            "foreign_keys": [{"column": "user_id", "references": "users.id"}],
            "row_count": 50,
            "distinct_values": {},
        },
        "products": {
            "columns": [{"name": "id"}, {"name": "title"}, {"name": "price"}],
            "row_count": 200,
            "foreign_keys": [],
            "distinct_values": {},
        },
    }


def test_link_returns_all_tables_when_under_max(small_schema):
    result = link_relevant_tables("test question", small_schema, [], [], max_tables=10)
    assert set(result) == {"users", "orders", "products"}


def test_link_prioritises_token_matched_tables(small_schema):
    result = link_relevant_tables(
        "show me all orders", small_schema, [], [], max_tables=1
    )
    assert "orders" in result


def test_link_includes_fk_referenced_tables(small_schema):
    # "orders" has a FK to "users"
    # even if max_tables=1 matches only "orders",
    # "users" should be pulled in as a FK dependency
    result = link_relevant_tables(
        "show me all orders", small_schema, [], [], max_tables=1
    )
    assert "users" in result


def test_link_uses_verified_sql_as_boost(small_schema):
    retrieved = [
        {
            "sql": "SELECT * FROM products WHERE price > 100",
            "question": "",
            "restatement": "",
        }
    ]
    result = link_relevant_tables(
        "expensive items", small_schema, [], retrieved, max_tables=1
    )
    assert "products" in result


@pytest.mark.parametrize(
    "provider,model,expected_tier",
    [
        ("claude", "claude-sonnet", "large"),
        ("openai", "gpt-4o", "large"),
        ("groq", "llama-3.3-70b-versatile", "large"),
        ("ollama", "qwen2.5:0.5b", "tiny"),
        ("ollama", "llama3.2:1b", "tiny"),
        ("ollama", "phi3-mini", "tiny"),
        ("ollama", "llama3.2", "small"),
        ("ollama", "mistral", "small"),
        ("ollama", "", "small"),
    ],
)
def test_model_budget_tiering(provider, model, expected_tier):
    budget = model_budget(provider, model)
    assert budget["tier"] == expected_tier


def test_api_providers_get_a_larger_budget_than_small_local_models():
    api_budget = model_budget("claude", "claude-sonnet")
    local_budget = model_budget("ollama", "llama3.2")
    assert api_budget["max_tables"] > local_budget["max_tables"]
    assert api_budget["max_examples"] > local_budget["max_examples"]


def test_confidence_low_when_query_failed():
    confidence, reason, based = compute_confidence(
        retrieved=[{"similarity": 0.95}], exec_result={"error": "no such table: ghosts"}
    )
    assert confidence == "low"
    assert based is False


def test_confidence_high_when_closely_matches_verified_answer():
    confidence, reason, based = compute_confidence(
        retrieved=[{"similarity": 0.9}], exec_result={"rows": [{"n": 1}]}
    )
    assert confidence == "high"
    assert based is True


def test_confidence_medium_when_loosely_matches_verified_answer():
    confidence, reason, based = compute_confidence(
        retrieved=[{"similarity": 0.6}], exec_result={"rows": [{"n": 1}]}
    )
    assert confidence == "medium"
    assert based is True


def test_confidence_low_when_novel_question_returns_no_rows():
    confidence, reason, based = compute_confidence(
        retrieved=[], exec_result={"rows": []}
    )
    assert confidence == "low"
    assert based is False


def test_confidence_medium_when_novel_question_returns_rows():
    confidence, reason, based = compute_confidence(
        retrieved=[], exec_result={"rows": [{"n": 1}]}
    )
    assert confidence == "medium"
    assert based is False


def test_confidence_uses_the_strongest_retrieved_match():
    confidence, reason, based = compute_confidence(
        retrieved=[{"similarity": 0.2}, {"similarity": 0.8}, {"similarity": 0.4}],
        exec_result={"rows": [{"n": 1}]},
    )
    assert confidence == "high"
    assert based is True
