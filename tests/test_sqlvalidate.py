"""Tests for the static SQL validator (issue #93)."""

from backend.app.sqlvalidate import validate_sql


def _col(name, pk=False):
    return {"name": name, "type": "TEXT", "primary_key": pk}


# Mirrors the shape returned by DatabaseManager.get_schema().
SCHEMA = {
    "customers": {
        "columns": [_col("id", pk=True), _col("name"), _col("email"), _col("segment")],
        "foreign_keys": [],
    },
    "orders": {
        "columns": [
            _col("id", pk=True),
            _col("customer_id"),
            _col("status"),
            _col("total_amount"),
            _col("created_at"),
        ],
        "foreign_keys": [{"column": "customer_id", "references": "customers.id"}],
    },
    "order_items": {
        "columns": [
            _col("id", pk=True),
            _col("order_id"),
            _col("product_id"),
            _col("quantity"),
            _col("unit_price"),
        ],
        "foreign_keys": [],
    },
}


def test_valid_simple_select():
    res = validate_sql("SELECT id, name FROM customers", SCHEMA)
    assert res["ok"] is True
    assert res["errors"] == []


def test_valid_join_with_aliases():
    sql = (
        "SELECT c.name, o.total_amount "
        "FROM orders o JOIN customers c ON c.id = o.customer_id "
        "WHERE o.status = 'completed'"
    )
    res = validate_sql(sql, SCHEMA)
    assert res["ok"] is True, res["errors"]


def test_unknown_table():
    res = validate_sql("SELECT * FROM invoices", SCHEMA)
    assert res["ok"] is False
    assert any("Unknown table" in e and "invoices" in e for e in res["errors"])


def test_unknown_unqualified_column():
    res = validate_sql("SELECT revenue FROM orders", SCHEMA)
    assert res["ok"] is False
    assert any("Unknown column" in e and "revenue" in e for e in res["errors"])


def test_unknown_qualified_column():
    res = validate_sql("SELECT o.nonexistent FROM orders o", SCHEMA)
    assert res["ok"] is False
    assert any(
        "Unknown column" in e and "nonexistent" in e and "orders" in e
        for e in res["errors"]
    )


def test_select_star_passes():
    res = validate_sql("SELECT * FROM customers", SCHEMA)
    assert res["ok"] is True


def test_count_star_passes():
    res = validate_sql("SELECT COUNT(*) FROM orders WHERE status = 'pending'", SCHEMA)
    assert res["ok"] is True, res["errors"]


def test_unqualified_column_resolves_across_joined_tables():
    # `quantity` only exists in order_items; `status` only in orders.
    sql = (
        "SELECT status, quantity FROM orders "
        "JOIN order_items ON order_items.order_id = orders.id"
    )
    res = validate_sql(sql, SCHEMA)
    assert res["ok"] is True, res["errors"]


def test_cte_columns_not_flagged():
    # `revenue` is produced by the CTE, not a base table — must not be flagged.
    sql = (
        "WITH totals AS (SELECT customer_id, SUM(total_amount) AS revenue FROM orders "
        "GROUP BY customer_id) SELECT customer_id, revenue FROM totals"
    )
    res = validate_sql(sql, SCHEMA)
    assert res["ok"] is True, res["errors"]


def test_subquery_alias_columns_not_flagged():
    sql = (
        "SELECT t.customer_id, t.revenue FROM "
        "(SELECT customer_id, SUM(total_amount) AS revenue FROM orders "
        "GROUP BY customer_id) t"
    )
    res = validate_sql(sql, SCHEMA)
    assert res["ok"] is True, res["errors"]


def test_group_by_and_order_by_columns_validated():
    res = validate_sql(
        "SELECT segment, COUNT(*) FROM customers GROUP BY segment ORDER BY segment",
        SCHEMA,
    )
    assert res["ok"] is True, res["errors"]

    bad = validate_sql("SELECT segment FROM customers GROUP BY bogus_col", SCHEMA)
    assert bad["ok"] is False
    assert any("bogus_col" in e for e in bad["errors"])


def test_order_by_select_alias_not_flagged():
    # `revenue` is a SELECT alias, not a real column — must not be flagged.
    res = validate_sql(
        "SELECT total_amount AS revenue FROM orders ORDER BY revenue DESC",
        SCHEMA,
    )
    assert res["ok"] is True, res["errors"]

    # `customers` is a SELECT alias for COUNT(*).
    res = validate_sql(
        "SELECT segment, COUNT(*) AS customers FROM customers "
        "GROUP BY segment ORDER BY customers DESC",
        SCHEMA,
    )
    assert res["ok"] is True, res["errors"]

    # Real column should still be accepted.
    res = validate_sql(
        "SELECT total_amount AS revenue FROM orders ORDER BY total_amount",
        SCHEMA,
    )
    assert res["ok"] is True, res["errors"]

    # Bona-fide unknown column with no matching alias should still be flagged.
    bad = validate_sql("SELECT id, name FROM customers ORDER BY bogus_col", SCHEMA)
    assert bad["ok"] is False
    assert any("bogus_col" in e for e in bad["errors"])


def test_alias_in_where_is_flagged():
    # `revenue` is a SELECT alias; SQL does not allow referencing it in WHERE,
    # so this must be flagged rather than slipping through to execution.
    res = validate_sql(
        "SELECT total_amount AS revenue FROM orders WHERE revenue > 0", SCHEMA
    )
    assert res["ok"] is False
    assert any("Unknown column" in e and "revenue" in e for e in res["errors"])


def test_group_by_alias_accepted_per_dialect():
    # GROUP BY may reference a SELECT alias across the dialects we support.
    for dialect in ("postgresql", "mysql", "sqlite", "mssql", ""):
        res = validate_sql(
            "SELECT total_amount AS revenue FROM orders GROUP BY revenue",
            SCHEMA,
            dialect=dialect,
        )
        assert res["ok"] is True, (dialect, res["errors"])


def test_having_alias_dialect_dependent():
    sql = (
        "SELECT segment, COUNT(*) AS c FROM customers "
        "GROUP BY segment HAVING c > 1"
    )
    # MySQL and SQLite allow referencing a SELECT alias in HAVING.
    for dialect in ("mysql", "sqlite"):
        res = validate_sql(sql, SCHEMA, dialect=dialect)
        assert res["ok"] is True, (dialect, res["errors"])

    # Postgres / SQL Server (and standard SQL) do not — the alias must be
    # flagged so the repair loop rewrites it as the underlying aggregate.
    for dialect in ("postgresql", "mssql"):
        res = validate_sql(sql, SCHEMA, dialect=dialect)
        assert res["ok"] is False, dialect
        assert any("Unknown column" in e and "'c'" in e for e in res["errors"])


def test_nested_subquery_alias_does_not_leak_to_outer_scope():
    # `revenue` is an alias in the OUTER select; it is not visible inside the
    # subquery's WHERE, so referencing it there must be flagged.
    sql = (
        "SELECT total_amount AS revenue FROM orders "
        "WHERE customer_id IN (SELECT id FROM customers WHERE revenue > 0)"
    )
    res = validate_sql(sql, SCHEMA)
    assert res["ok"] is False
    assert any("Unknown column" in e and "revenue" in e for e in res["errors"])


def test_outer_alias_not_visible_in_sibling_subquery_select_list():
    # A GROUP BY inside the subquery must resolve aliases against the subquery's
    # own projection list, not the outer SELECT's aliases.
    sql = (
        "SELECT customer_id AS revenue FROM orders "
        "WHERE customer_id IN (SELECT customer_id FROM orders GROUP BY revenue)"
    )
    res = validate_sql(sql, SCHEMA)
    assert res["ok"] is False
    assert any("Unknown column" in e and "revenue" in e for e in res["errors"])


def test_unparseable_sql():
    res = validate_sql("SELECT FROM WHERE haha", SCHEMA)
    assert res["ok"] is False
    assert any("Could not parse SQL" in e for e in res["errors"])


def test_empty_sql():
    res = validate_sql("   ", SCHEMA)
    assert res["ok"] is False
    assert res["errors"] == ["Empty SQL statement."]


def test_case_insensitive_identifiers():
    res = validate_sql("SELECT ID, Name FROM Customers", SCHEMA)
    assert res["ok"] is True, res["errors"]


def test_multiple_errors_collected_and_deduped():
    res = validate_sql("SELECT bogus FROM customers, customers", SCHEMA)
    assert res["ok"] is False
    # the duplicated table reference must not produce duplicate column errors
    assert len(res["errors"]) == len(set(res["errors"]))


def test_dialect_is_respected():
    # Postgres-style cast should parse cleanly under the postgresql dialect.
    res = validate_sql(
        "SELECT created_at::date FROM orders", SCHEMA, dialect="postgresql"
    )
    assert res["ok"] is True, res["errors"]
