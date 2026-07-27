"""Per-dialect traits — the single source of truth for how each supported
database differs.

Everything the rest of the app needs to know about a dialect lives in ``TRAITS``
below: which sqlglot dialect parses it, how to limit rows, how to quote an
identifier, where approximate row counts come from, how to bound a runaway
statement, and what to tell the LLM about its SQL syntax.

Before this module those facts were spread across four ``if dialect == ...``
chains in ``database.py``, three copies of the sqlglot name map, and a hint dict
in ``llm.py``. Adding a database meant finding all of them. Now it means adding
one entry here.
"""

from dataclasses import dataclass

# Approximate row counts pulled from the server's own catalog/statistics tables.
# Far cheaper than COUNT(*) per table, and exact enough for the only thing we use
# it for: deciding which tables are big enough to deserve enrichment. Each query
# must return (table_name, row_count) rows. ``:owner`` is bound to the
# inspector's default schema where the query uses it.
_PG_ROW_COUNTS = "SELECT relname, reltuples FROM pg_class WHERE relkind IN ('r','p')"
_MYSQL_ROW_COUNTS = (
    "SELECT table_name, table_rows FROM information_schema.tables "
    "WHERE table_schema = DATABASE()"
)
_MSSQL_ROW_COUNTS = (
    "SELECT t.name, SUM(p.rows) FROM sys.tables t "
    "JOIN sys.partitions p ON t.object_id=p.object_id "
    "WHERE p.index_id IN (0,1) GROUP BY t.name"
)
_ORACLE_ROW_COUNTS = "SELECT table_name, num_rows FROM all_tables WHERE owner = :owner"


@dataclass(frozen=True)
class DialectTraits:
    """How one SQLAlchemy dialect differs from the others.

    ``sqlglot``
        Name sqlglot knows this dialect by, where it differs from SQLAlchemy's.
    ``row_limit``
        ``"limit"`` for trailing ``LIMIT n``; ``"fetch_first"`` for the SQL
        standard ``FETCH FIRST n ROWS ONLY`` (Oracle).
    ``quote``
        Identifier quote character.
    ``uppercase_identifiers``
        True when the server folds unquoted identifiers to upper case and
        SQLAlchemy's reflection hands them back lower-cased. Quoting such a name
        as-is produces a name that does not exist, so it must be upper-cased
        before quoting. Oracle only.
    ``row_count_sql``
        Bulk approximate row counts, or None to fall back to per-table COUNT(*).
    ``timeout_style``
        How to bound a single statement — see ``DatabaseManager._apply_statement_timeout``.
        None means the dialect offers no server-side mechanism we can use.
    ``prompt_hint``
        Syntax guidance handed to the LLM. Keep it about *dialect differences*,
        not general SQL advice.
    """

    sqlglot: str
    row_limit: str = "limit"
    quote: str = '"'
    uppercase_identifiers: bool = False
    row_count_sql: str | None = None
    timeout_style: str | None = None
    prompt_hint: str = ""


TRAITS: dict[str, DialectTraits] = {
    "sqlite": DialectTraits(
        sqlglot="sqlite",
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: use date()/strftime(); string concat is ||; "
            "no ILIKE (use LIKE, it is case-insensitive for ASCII)."
        ),
    ),
    "postgresql": DialectTraits(
        sqlglot="postgres",
        row_count_sql=_PG_ROW_COUNTS,
        timeout_style="statement_timeout",
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: use date_trunc()/interval arithmetic; ILIKE is available; "
            "quote mixed-case identifiers."
        ),
    ),
    # Bare "postgres" is accepted in connection URLs and normalises to the same
    # SQLAlchemy dialect, so it needs the same traits.
    "postgres": DialectTraits(
        sqlglot="postgres",
        row_count_sql=_PG_ROW_COUNTS,
        timeout_style="statement_timeout",
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: use date_trunc()/interval arithmetic; ILIKE is available; "
            "quote mixed-case identifiers."
        ),
    ),
    "mysql": DialectTraits(
        sqlglot="mysql",
        quote="`",
        row_count_sql=_MYSQL_ROW_COUNTS,
        timeout_style="max_execution_time",
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: use DATE_FORMAT()/DATE_SUB(); identifiers quote with backticks."
        ),
    ),
    "mssql": DialectTraits(
        sqlglot="tsql",
        row_count_sql=_MSSQL_ROW_COUNTS,
        prompt_hint=(
            "Row limiting: use TOP (n), never LIMIT. "
            "Dates via DATEADD()/DATEDIFF(); string concat is +."
        ),
    ),
    "oracle": DialectTraits(
        sqlglot="oracle",
        row_limit="fetch_first",
        uppercase_identifiers=True,
        row_count_sql=_ORACLE_ROW_COUNTS,
        timeout_style="call_timeout",
        prompt_hint=(
            "Row limiting: use FETCH FIRST n ROWS ONLY, never LIMIT. "
            "Dates: TRUNC(SYSDATE), ADD_MONTHS(), date arithmetic in days; "
            "format with TO_CHAR(). String concat is ||; NULLs via NVL(). "
            "There is no BOOLEAN column type — expect 0/1 or 'Y'/'N'. "
            "An empty string is NULL. SELECT aliases cannot be referenced in "
            "WHERE or HAVING."
        ),
    ),
}

# Fallback for a dialect we have no entry for. Standard-ish SQL, no server
# features assumed, no hint — the prompt simply omits the dialect rule.
_DEFAULT = DialectTraits(sqlglot="")


def traits_for(dialect) -> DialectTraits:
    """Traits for ``dialect``, or a conservative default if it is unknown."""
    return TRAITS.get(dialect or "", _DEFAULT)


def allowed_schemes() -> set[str]:
    """URL schemes ``_validate_db_url`` will accept."""
    return set(TRAITS)


def glot_dialect(dialect):
    """sqlglot's name for ``dialect``, or None when we have nothing to offer.

    None is what sqlglot itself takes to mean "parse as generic SQL", which is
    the right behaviour for a dialect we don't know.
    """
    return traits_for(dialect).sqlglot or None


def limit_clause(dialect, n) -> str:
    """Row-limiting clause to append to a SELECT, e.g. ``LIMIT 12``.

    Only used for the introspection queries we build ourselves; the LLM is told
    the right syntax via ``prompt_hint``.
    """
    if traits_for(dialect).row_limit == "fetch_first":
        return f"FETCH FIRST {int(n)} ROWS ONLY"
    return f"LIMIT {int(n)}"


def denormalize_ident(dialect, name):
    """Reflected identifier -> the spelling the server's own catalog stores.

    On Oracle, SQLAlchemy reflection lower-cases identifiers the server stores in
    upper case, so using the reflected name verbatim — quoting it, or comparing
    it against ``ALL_TABLES.OWNER`` — references something that does not exist.
    Upper-case it first, but only when it is entirely lower-case, which is
    exactly SQLAlchemy's own ``denormalize_name`` rule: a name with any
    upper-case character was genuinely created quoted and mixed-case.

    A no-op for every other dialect, and for a missing name.
    """
    if name is None:
        return name
    traits = traits_for(dialect)
    name = str(name)
    if traits.uppercase_identifiers and name.islower():
        return name.upper()
    return name


def normalize_ident(dialect, name):
    """Catalog identifier -> the spelling SQLAlchemy reflection hands back.

    The inverse of :func:`denormalize_ident`, and SQLAlchemy's own
    ``normalize_name``: rows read straight out of a catalog table come back in
    Oracle's stored upper case, and have to be folded back to lower case before
    they will match anything ``get_table_names()`` returned.
    """
    if name is None:
        return name
    traits = traits_for(dialect)
    name = str(name)
    if traits.uppercase_identifiers and name.isupper():
        return name.lower()
    return name


def quote_ident(dialect, name) -> str:
    """Quote ``name`` for ``dialect``, escaping any embedded quote character.

    The name is denormalised first — see :func:`denormalize_ident` for why a
    reflected Oracle name cannot be quoted verbatim.
    """
    traits = traits_for(dialect)
    name = denormalize_ident(dialect, str(name))
    q = traits.quote
    return f"{q}{name.replace(q, q * 2)}{q}"


def prompt_hint(dialect) -> str:
    """Dialect syntax guidance for the SQL-generation prompt."""
    return traits_for(dialect).prompt_hint
