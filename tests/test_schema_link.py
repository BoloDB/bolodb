"""Tests for model budgeting, confidence scoring, and table linking."""

import pytest
from backend.app.schema_link import (
    expand_linked_tables,
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
            "columns": [{"name": "id"}, {"name": "workspace_id"}],
            "foreign_keys": [{"column": "workspace_id", "references": "users.id"}],
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
    result = link_relevant_tables(
        "test question", small_schema, [], [], max_tables=10, context_tables=set()
    )
    assert set(result) == {"users", "orders", "products"}


def test_link_prioritises_token_matched_tables(small_schema):
    result = link_relevant_tables(
        "show me all orders", small_schema, [], [], max_tables=1, context_tables=set()
    )
    assert "orders" in result


def test_link_includes_fk_referenced_tables(small_schema):
    # "orders" has a FK to "users"
    # even if max_tables=1 matches only "orders",
    # "users" should be pulled in as a FK dependency
    result = link_relevant_tables(
        "show me all orders", small_schema, [], [], max_tables=1, context_tables=set()
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
        "expensive items",
        small_schema,
        [],
        retrieved,
        max_tables=1,
        context_tables=set(),
    )
    assert "products" in result


@pytest.mark.parametrize(
    "model,expected_tier",
    [
        ("gemini-2.5-flash-lite", "flash"),
        ("gemini-2.5-flash", "flash"),
        ("gemini-2.5-pro", "flash"),
        ("gemma-4-26b-a4b-it", "flash"),
        ("", "flash"),
    ],
)
def test_model_budget_always_flash(model, expected_tier):
    budget = model_budget(model)
    assert budget["tier"] == expected_tier


def test_model_budget_is_constant():
    budget = model_budget()
    assert budget["tier"] == "flash"
    assert budget["max_tables"] == 20
    assert budget["max_examples"] == 5


def test_link_matches_singular_question_to_plural_table(small_schema):
    # "order" (singular) should still find the "orders" table
    result = link_relevant_tables(
        "average order value", small_schema, [], [], max_tables=1, context_tables=set()
    )
    assert "orders" in result


def test_link_glossary_only_expands_mentioned_terms(small_schema):
    glossary = [
        {"term": "revenue", "maps_to": "orders total", "sql_hint": ""},
        {"term": "catalog", "maps_to": "products price", "sql_hint": ""},
    ]
    # question mentions "revenue" but not "catalog" -> orders should win
    result = link_relevant_tables(
        "total revenue", small_schema, glossary, [], max_tables=1, context_tables=set()
    )
    assert result[0] == "orders"


def test_link_context_tables_beat_token_matches(small_schema):
    # follow-up question mentions products, but previous query used orders
    result = link_relevant_tables(
        "now show products too",
        small_schema,
        [],
        [],
        max_tables=1,
        context_tables={"orders"},
    )
    assert "orders" in result


def test_link_includes_junction_table_between_selected_tables():
    schema = {
        "orders": {
            "columns": [{"name": "id", "primary_key": True}],
            "foreign_keys": [],
            "row_count": 100,
            "distinct_values": {},
        },
        "products": {
            "columns": [{"name": "id", "primary_key": True}],
            "foreign_keys": [],
            "row_count": 50,
            "distinct_values": {},
        },
        "order_items": {
            "columns": [{"name": "order_id"}, {"name": "product_id"}],
            "foreign_keys": [
                {"column": "order_id", "references": "orders.id"},
                {"column": "product_id", "references": "products.id"},
            ],
            "row_count": 500,
            "distinct_values": {},
        },
        "reviews": {
            "columns": [{"name": "id"}],
            "foreign_keys": [],
            "row_count": 10,
            "distinct_values": {},
        },
    }
    # orders + products both match; order_items (the bridge) must come along
    result = link_relevant_tables(
        "products per order", schema, [], [], max_tables=2, context_tables=set()
    )
    assert "orders" in result and "products" in result
    assert "order_items" in result


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


def test_link_shortlist_boost_beats_no_match(small_schema):
    # nothing in the question matches; the LLM-shortlisted table must win
    result = link_relevant_tables(
        "hmm", small_schema, [], [], 1, set(), boost_tables={"products"}
    )
    assert result[0] == "products"


def test_expand_adds_referenced_real_table_and_its_fk_parents(small_schema):
    # model referenced `orders`, which we never sent; users is its FK parent
    added = expand_linked_tables(
        small_schema, ["products"], "SELECT * FROM orders", "sqlite"
    )
    assert added == ["orders", "users"]


def test_expand_ignores_hallucinated_and_already_linked_tables(small_schema):
    added = expand_linked_tables(
        small_schema, ["users"], "SELECT * FROM ghosts JOIN users", "sqlite"
    )
    assert added == []


def test_expand_is_case_insensitive(small_schema):
    added = expand_linked_tables(
        small_schema, ["users"], "SELECT * FROM ORDERS", "sqlite"
    )
    assert added == ["orders"]  # users (FK parent) already linked


def test_expand_handles_unparseable_sql(small_schema):
    assert expand_linked_tables(small_schema, ["users"], "not sql ((", "sqlite") == []


def test_confidence_uses_the_strongest_retrieved_match():
    confidence, reason, based = compute_confidence(
        retrieved=[{"similarity": 0.2}, {"similarity": 0.8}, {"similarity": 0.4}],
        exec_result={"rows": [{"n": 1}]},
    )
    assert confidence == "high"
    assert based is True


def test_expand_fk_parents_recursive():
    schema = {
        "permissions": {
            "columns": [{"name": "id"}, {"name": "role_id"}],
            "foreign_keys": [{"column": "role_id", "references": "roles.id"}],
            "row_count": 100,
            "distinct_values": {},
        },
        "roles": {
            "columns": [{"name": "id"}, {"name": "created_by"}],
            "foreign_keys": [{"column": "created_by", "references": "users.id"}],
            "row_count": 10,
            "distinct_values": {},
        },
        "users": {
            "columns": [{"name": "id"}, {"name": "name"}],
            "foreign_keys": [],
            "row_count": 50,
            "distinct_values": {},
        },
    }
    added = expand_linked_tables(schema, [], "SELECT * FROM permissions", "sqlite")
    assert set(added) == {"permissions", "roles", "users"}


def test_expand_fk_parents_with_cycle():
    schema = {
        "a": {
            "columns": [{"name": "id"}, {"name": "b_id"}],
            "foreign_keys": [{"column": "b_id", "references": "b.id"}],
            "row_count": 100,
            "distinct_values": {},
        },
        "b": {
            "columns": [{"name": "id"}, {"name": "a_id"}],
            "foreign_keys": [{"column": "a_id", "references": "a.id"}],
            "row_count": 100,
            "distinct_values": {},
        },
    }
    added = expand_linked_tables(schema, [], "SELECT * FROM a", "sqlite")
    assert set(added) == {"a", "b"}


def test_expand_fk_parents_self_reference():
    schema = {
        "employees": {
            "columns": [{"name": "id"}, {"name": "manager_id"}],
            "foreign_keys": [{"column": "manager_id", "references": "employees.id"}],
            "row_count": 100,
            "distinct_values": {},
        },
    }
    added = expand_linked_tables(schema, [], "SELECT * FROM employees", "sqlite")
    assert added == ["employees"]
