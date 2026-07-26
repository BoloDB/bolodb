"""Tests for the per-dialect traits table in app.dialects.

These are the facts every other module now depends on being right: get the
row-limiting syntax or the identifier casing wrong for a dialect and every
introspection query against it fails.
"""

import pytest
import sqlglot

from backend.app.dialects import (
    TRAITS,
    allowed_schemes,
    glot_dialect,
    limit_clause,
    prompt_hint,
    quote_ident,
    traits_for,
)


# --- row limiting -----------------------------------------------------------


def test_oracle_uses_fetch_first():
    """Oracle has no LIMIT; using it is a syntax error, not a slow query."""
    assert limit_clause("oracle", 3) == "FETCH FIRST 3 ROWS ONLY"


@pytest.mark.parametrize("dialect", ["postgresql", "mysql", "sqlite"])
def test_other_dialects_use_limit(dialect):
    assert limit_clause(dialect, 12) == "LIMIT 12"


def test_limit_clause_coerces_to_int():
    """The value is interpolated into SQL, so it must never carry a string through."""
    assert limit_clause("postgresql", "5") == "LIMIT 5"
    with pytest.raises(ValueError):
        limit_clause("postgresql", "1; DROP TABLE t")


def test_unknown_dialect_falls_back_to_limit():
    assert limit_clause("snowflake", 10) == "LIMIT 10"


# --- identifier quoting -----------------------------------------------------


def test_oracle_uppercases_reflected_identifiers():
    """SQLAlchemy hands back Oracle's upper-case names lower-cased. Quoting the
    reflected form verbatim would reference a table that does not exist."""
    assert quote_ident("oracle", "employees") == '"EMPLOYEES"'


def test_oracle_leaves_mixed_case_alone():
    """A name with any upper-case character was genuinely created quoted, so it
    is already in its true form — matching SQLAlchemy's denormalize_name rule."""
    assert quote_ident("oracle", "MixedCase") == '"MixedCase"'


def test_mysql_uses_backticks():
    assert quote_ident("mysql", "order") == "`order`"


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite", "mssql", "oracle"])
def test_non_mysql_dialects_use_double_quotes(dialect):
    assert quote_ident(dialect, "Table").startswith('"')


def test_embedded_quote_characters_are_escaped():
    assert quote_ident("mysql", "a`b") == "`a``b`"
    assert quote_ident("postgresql", 'a"b') == '"a""b"'
    # Upper-cased first (all-lower name), then the embedded quote doubled.
    assert quote_ident("oracle", 'we"ird') == '"WE""IRD"'


# --- sqlglot mapping --------------------------------------------------------


@pytest.mark.parametrize(
    "dialect,expected",
    [
        ("postgresql", "postgres"),
        ("postgres", "postgres"),
        ("mssql", "tsql"),
        ("oracle", "oracle"),
        ("mysql", "mysql"),
        ("sqlite", "sqlite"),
    ],
)
def test_glot_dialect_mapping(dialect, expected):
    assert glot_dialect(dialect) == expected


def test_unknown_dialect_parses_as_generic_sql():
    """None is sqlglot's own 'generic SQL' signal — better than handing it a
    dialect name it will reject outright."""
    assert glot_dialect("snowflake") is None
    assert glot_dialect("") is None


@pytest.mark.parametrize("dialect", sorted(TRAITS))
def test_every_traits_entry_names_a_real_sqlglot_dialect(dialect):
    """A typo here would silently disable AST-based read-only enforcement."""
    parsed = sqlglot.parse_one("SELECT 1", dialect=glot_dialect(dialect))
    assert parsed is not None


# --- table completeness -----------------------------------------------------


@pytest.mark.parametrize("dialect", sorted(TRAITS))
def test_every_dialect_has_a_prompt_hint(dialect):
    """An empty hint means the LLM gets an empty rule 7 and guesses the syntax."""
    assert prompt_hint(dialect).strip()


@pytest.mark.parametrize("dialect", sorted(TRAITS))
def test_every_prompt_hint_states_row_limiting_syntax(dialect):
    """Prompt rule 4 defers to the hint for row limiting, so it must be there."""
    assert "row limiting" in prompt_hint(dialect).lower()


def test_oracle_is_connectable():
    assert "oracle" in allowed_schemes()


def test_allowed_schemes_matches_the_traits_table():
    assert allowed_schemes() == set(TRAITS)


def test_unknown_dialect_gets_conservative_defaults():
    """No server features assumed, no hint invented."""
    t = traits_for("snowflake")
    assert t.row_count_sql is None
    assert t.timeout_style is None
    assert t.prompt_hint == ""


def test_oracle_bulk_row_counts_are_owner_scoped():
    """all_tables spans every schema on the instance; unscoped it would pull
    counts for tables the connection cannot even read."""
    sql = traits_for("oracle").row_count_sql
    assert ":owner" in sql
