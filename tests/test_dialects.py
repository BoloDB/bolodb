"""Tests for the per-dialect traits table in app.dialects.

These are the facts every other module now depends on being right: get the
row-limiting syntax or the identifier casing wrong for a dialect and every
introspection query against it fails.
"""

import pytest
import sqlglot
from sqlalchemy import create_engine
from sqlalchemy.exc import NoSuchModuleError

from backend.app.dialects import (
    TRAITS,
    allowed_schemes,
    denormalize_ident,
    glot_dialect,
    limit_clause,
    normalize_ident,
    normalize_scheme,
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


# --- scheme normalisation ---------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        ("POSTGRESQL://u:p@h:5432/db", "postgresql://u:p@h:5432/db"),
        ("POSTGRESQL+PSYCOPG2://u:p@h/db", "postgresql+psycopg2://u:p@h/db"),
        ("Oracle+OracleDB://u:p@h:1521/XE", "oracle+oracledb://u:p@h:1521/XE"),
        ("SQLite:///data/sample.db", "sqlite:///data/sample.db"),
    ],
)
def test_the_scheme_is_folded_to_lower_case(url, expected):
    """SQLAlchemy looks dialects up by exact name, and database.py reads the
    dialect off the front of the scheme — an upper-case one loads no plugin and
    misses the traits table, taking the default: no statement timeout, no bulk
    row counts, and generic SQL for the read-only guard's parser."""
    assert normalize_scheme(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://user:P%40ssWORD@Host.Example.COM:5432/MyDb",
        "oracle+oracledb://u:SeCrEt@h:1521/?service_name=ORCLPDB1",
    ],
)
def test_nothing_past_the_scheme_is_touched(url):
    """Passwords, hosts and service names are case-sensitive."""
    assert normalize_scheme(url) == url


# --- driver resolution ------------------------------------------------------


@pytest.mark.parametrize(
    "url,expected",
    [
        # SQLAlchemy dropped the "postgres" alias; it raises NoSuchModuleError.
        ("postgres://u:p@h:5432/db", "postgresql://u:p@h:5432/db"),
        # Bare mysql:// means MySQLdb, bare oracle:// means cx_Oracle. Neither
        # is a dependency, so both fail on import before connecting.
        ("mysql://u:p@h:3306/db", "mysql+pymysql://u:p@h:3306/db"),
        ("oracle://u:p@h:1521/XEPDB1", "oracle+oracledb://u:p@h:1521/XEPDB1"),
        # A driver spelled out against the dead alias still needs the rename.
        ("postgres+psycopg2://u:p@h/db", "postgresql+psycopg2://u:p@h/db"),
    ],
)
def test_unusable_schemes_are_pointed_at_the_driver_we_ship(url, expected):
    assert normalize_scheme(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        # Works as typed: psycopg2 is both the default and installed.
        "postgresql://u:p@h:5432/db",
        "sqlite:///data/sample.db",
        # An explicit driver is the user's choice to make.
        "mysql+mysqldb://u:p@h:3306/db",
        "oracle+cx_oracle://u:p@h:1521/XE",
        "postgresql+psycopg://u:p@h:5432/db",
    ],
)
def test_a_usable_or_explicit_scheme_is_left_exactly_as_typed(url):
    """db_id_for hashes the URL, so rewriting a working one would orphan that
    database's saved glossary and verified queries."""
    assert normalize_scheme(url) == url


def test_a_string_that_is_not_a_url_is_left_alone():
    """Validation rejects it; normalisation should not raise on the way there."""
    assert normalize_scheme("nonsense") == "nonsense"


@pytest.mark.parametrize("dialect", sorted(TRAITS))
def test_only_unusable_schemes_are_ever_rewritten(dialect):
    """The safety property behind normalize_scheme, pinned.

    Rewriting changes the URL, and db_id_for hashes the URL, so a database's
    persisted glossary, verified queries and catalog all hang off the result.
    That is only safe because none of the rewritten schemes can connect in the
    first place — they raise on import, so no connection was ever established
    under one, and no id exists to orphan. If a driver that makes one of them
    work ever lands in requirements.txt, this fails, and the entry has to go
    before the rewrite starts moving live databases' identities.
    """
    if TRAITS[dialect].drivername is None:
        return
    with pytest.raises(Exception) as excinfo:
        create_engine(f"{dialect}://user:pass@host/db").dialect
    assert isinstance(excinfo.value, (NoSuchModuleError, ImportError))


@pytest.mark.parametrize("dialect", sorted(TRAITS))
def test_every_substituted_drivername_keeps_its_dialect(dialect):
    """The scheme before the "+" is what database.py reads the dialect from, so
    a substitution that changed it would silently swap the traits too."""
    drivername = TRAITS[dialect].drivername
    if drivername is None:
        return
    assert drivername.split("+")[0] in TRAITS


# --- catalog identifier casing ----------------------------------------------


def test_oracle_owner_is_denormalised_before_the_catalog_sees_it():
    """ALL_TABLES.OWNER holds APPUSER, but reflection reports appuser. Bound
    unchanged, the owner filter matches nothing and every row count vanishes."""
    assert denormalize_ident("oracle", "appuser") == "APPUSER"


def test_oracle_catalog_names_are_normalised_on_the_way_back():
    """Row counts are keyed by the names get_table_names() returned, which are
    lower case — the upper-case catalog spelling would never match."""
    assert normalize_ident("oracle", "EMPLOYEES") == "employees"


def test_quoted_mixed_case_names_survive_both_directions():
    """A name with any upper-case character was created quoted, so it is
    already exact and must not be folded either way."""
    assert denormalize_ident("oracle", "MixedCase") == "MixedCase"
    assert normalize_ident("oracle", "MixedCase") == "MixedCase"


@pytest.mark.parametrize("dialect", ["postgresql", "mysql", "sqlite", "mssql"])
def test_identifier_casing_is_a_no_op_off_oracle(dialect):
    for name in ("employees", "EMPLOYEES", "MixedCase"):
        assert denormalize_ident(dialect, name) == name
        assert normalize_ident(dialect, name) == name


def test_a_missing_name_passes_through():
    """default_schema_name is None when reflection could not determine it."""
    assert denormalize_ident("oracle", None) is None
    assert normalize_ident("oracle", None) is None
