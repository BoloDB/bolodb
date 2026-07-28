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

from dataclasses import dataclass, replace

# Approximate row counts pulled from the server's own catalog/statistics tables.
# Far cheaper than COUNT(*) per table, and exact enough for the only thing we use
# it for: deciding which tables are big enough to deserve enrichment. Each query
# must return (table_name, row_count) rows. ``:owner`` is bound to the
# inspector's default schema where the query uses it.
_PG_ROW_COUNTS = "SELECT relname, reltuples FROM pg_class WHERE relkind IN ('r','p') AND relnamespace = (SELECT oid FROM pg_namespace WHERE nspname = :owner)"
_MYSQL_ROW_COUNTS = (
    "SELECT table_name, table_rows FROM information_schema.tables "
    "WHERE table_schema = DATABASE()"
)
_MSSQL_ROW_COUNTS = (
    "SELECT t.name, SUM(p.rows) FROM sys.tables t "
    "JOIN sys.partitions p ON t.object_id=p.object_id "
    "WHERE p.index_id IN (0,1) AND t.schema_id = SCHEMA_ID(:owner) GROUP BY t.name"
)
_ORACLE_ROW_COUNTS = "SELECT table_name, num_rows FROM all_tables WHERE owner = :owner"
_SNOWFLAKE_ROW_COUNTS = (
    "SELECT table_name, row_count FROM information_schema.tables "
    "WHERE table_schema = :owner"
)

# Query parameters that must never reach a driver, whatever the dialect.
#
# Each one either points the driver at something other than the URL's own host,
# or makes it read a file off the server's disk — neither of which the SSRF
# guard in ``_validate_db_url`` can inspect, because the value is opaque to it.
# Global rather than per-dialect on purpose: a parameter that is dangerous on
# the database that defines it is not made safe by appearing on another.
FORBIDDEN_PARAMS: dict[str, str] = {
    # Oracle: a DSN or connect descriptor in place of the URL's host.
    "dsn": "connect with host, port and service_name instead",
    # BigQuery and Snowflake: read a key file from the server's filesystem.
    "credentials_path": "paste the service account key instead of a file path",
    "private_key_file": "paste the key instead of a file path",
    "private_key_path": "paste the key instead of a file path",
    "token_file_path": "paste the token instead of a file path",
}

# Query parameters whose *value* is a credential. Redacted wherever a URL is
# shown, stored for display, or hashed — see ``sanitize_url``. Global for the
# same reason as above: failing to redact is the expensive direction.
SECRET_PARAMS: frozenset[str] = frozenset(
    {
        # BigQuery: the whole service account key, base64-encoded.
        "credentials_base64",
        "credentials_info",
        # Databricks / Snowflake: token and key auth passed as parameters.
        "access_token",
        "token",
        "private_key",
        "password",
    }
)


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
    ``drivername``
        Scheme to rewrite this one to, when SQLAlchemy's default DBAPI for it
        is not the one we ship — see :func:`normalize_scheme`. Where the user
        named a driver, only the dialect in front of it is taken from here.
        None leaves the scheme alone.
    ``required_params``
        Query parameters without which the URL cannot identify its target at
        all, e.g. Databricks' ``http_path``. Missing ones are reported up front
        rather than as whatever the driver says when it fails to connect.
    ``target_params``
        Parameters that can name the target *instead of* the URL's path. At
        least one, or a path, must be present. Oracle's ``service_name`` is the
        case: with neither, SQLAlchemy stops building a host:port DSN and hands
        the host field to the driver as a connect string of its own.
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
    drivername: str | None = None
    required_params: frozenset[str] = frozenset()
    target_params: frozenset[str] = frozenset()
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
    "mysql": DialectTraits(
        sqlglot="mysql",
        quote="`",
        row_count_sql=_MYSQL_ROW_COUNTS,
        timeout_style="max_execution_time",
        # SQLAlchemy defaults bare "mysql" to MySQLdb, which we do not ship.
        drivername="mysql+pymysql",
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: use DATE_FORMAT()/DATE_SUB(); identifiers quote with backticks."
        ),
    ),
    "mssql": DialectTraits(
        sqlglot="tsql",
        row_limit="top",
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
        # Through SQLAlchemy 2.0 bare "oracle" still means cx_Oracle, which is
        # obsolete and not installed; python-oracledb is what we depend on.
        drivername="oracle+oracledb",
        target_params=frozenset({"service_name"}),
        prompt_hint=(
            "Row limiting: use FETCH FIRST n ROWS ONLY, never LIMIT. "
            "Dates: TRUNC(SYSDATE), ADD_MONTHS(), date arithmetic in days; "
            "format with TO_CHAR(). String concat is ||; NULLs via NVL(). "
            "There is no BOOLEAN column type — expect 0/1 or 'Y'/'N'. "
            "An empty string is NULL. SELECT aliases cannot be referenced in "
            "WHERE or HAVING."
        ),
    ),
    "snowflake": DialectTraits(
        sqlglot="snowflake",
        # snowflake-sqlalchemy's denormalize_name is the same rule as Oracle's:
        # the server stores unquoted names upper-cased and reflection hands
        # them back lower-cased, so a reflected name used verbatim resolves to
        # nothing. Verified against snowflake/sqlalchemy/name_utils.py.
        uppercase_identifiers=True,
        row_count_sql=_SNOWFLAKE_ROW_COUNTS,
        timeout_style="snowflake_session",
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: DATEADD()/DATEDIFF()/DATE_TRUNC(), CURRENT_DATE(); "
            "format with TO_CHAR(). String concat is ||; ILIKE is available. "
            "Unquoted identifiers fold to upper case. Semi-structured columns "
            "are VARIANT — reach into them with colon paths like col:field."
        ),
    ),
    "databricks": DialectTraits(
        sqlglot="databricks",
        quote="`",
        # No bulk source: Unity Catalog's information_schema.tables carries no
        # row count, so enrichment falls back to COUNT(*) per table.
        required_params=frozenset({"http_path"}),
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: date_add()/datediff()/date_trunc(), current_date(); "
            "format with date_format(). String concat is || or concat(). "
            "Identifiers quote with backticks. Tables are usually addressed "
            "three-part as catalog.schema.table."
        ),
    ),
    "bigquery": DialectTraits(
        sqlglot="bigquery",
        quote="`",
        # __TABLES__ carries row counts but has to be addressed per dataset,
        # which this table's single static statement cannot express. COUNT(*)
        # is metadata-only on BigQuery, so the fallback is cheap anyway.
        prompt_hint=(
            "Row limiting: use LIMIT n. "
            "Dates: DATE_ADD()/DATE_DIFF()/DATE_TRUNC() with named INTERVAL "
            "parts, CURRENT_DATE(); format with FORMAT_DATE(). String concat "
            "is CONCAT(). Identifiers quote with backticks and are addressed "
            "as `project.dataset.table`. Standard SQL only — no ILIKE."
        ),
    ),
}

# Bare "postgres" is accepted in connection URLs and normalises to the same
# SQLAlchemy dialect, so it needs the same traits. The entry stays even
# though normalize_scheme rewrites the scheme before anything derives a
# dialect from it: allowed_schemes() reads this table to decide what a user
# may type, and normalize_scheme itself looks the rewrite up here.
TRAITS["postgres"] = replace(
    TRAITS["postgresql"],
    drivername="postgresql",
)

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


def select_prefix(dialect, n) -> str:
    """Prefix to inject between SELECT and its column list, e.g. ``TOP (12)``.

    Only used for the introspection queries we build ourselves.
    """
    if traits_for(dialect).row_limit == "top":
        return f"TOP ({int(n)})"
    return ""


def limit_clause(dialect, n) -> str:
    """Row-limiting clause to append to a SELECT, e.g. ``LIMIT 12``.

    Only used for the introspection queries we build ourselves; the LLM is told
    the right syntax via ``prompt_hint``.
    """
    style = traits_for(dialect).row_limit
    if style == "fetch_first":
        return f"FETCH FIRST {int(n)} ROWS ONLY"
    if style == "top":
        return ""
    return f"LIMIT {int(n)}"


def normalize_scheme(url: str) -> str:
    """Put a URL's scheme in the form the rest of the app expects to read.

    Two things are corrected, and nothing beyond the scheme is touched — the
    rest of the URL, passwords and service names included, is case-sensitive.

    **Case.** SQLAlchemy looks its dialects up by exact name, so ``POSTGRESQL://``
    loads nothing, and ``database.py`` reads the dialect off the front of the
    scheme — an upper-case one misses the traits table entirely and silently
    takes the default: no statement timeout, no bulk row counts, and generic
    SQL for the read-only guard's parser.

    **Dead and unshipped drivers.** ``postgres://`` is not a dialect SQLAlchemy
    still answers to, and bare ``mysql://`` and ``oracle://`` resolve to
    MySQLdb and cx_Oracle, drivers this app does not depend on. All three raise
    on import, so a user who types one gets a plugin error rather than an
    answer. Where the user named a driver explicitly that choice is kept: only
    the dead dialect name in front of it is replaced.

    A scheme that already works is left byte-for-byte as typed — a driver the
    user named, or one SQLAlchemy picks that we actually ship, is not ours to
    second-guess.

    The result is only ever handed to ``create_engine``. A database's identity
    stays tied to the URL as it was given, so nothing here can move a live
    database's ``db_id`` away from its own saved data.
    """
    scheme, sep, rest = url.partition("://")
    if not sep:
        return url
    base, plus, driver = scheme.lower().partition("+")
    substitute = traits_for(base).drivername
    if substitute:
        if plus:
            base = substitute.split("+")[0]
        else:
            base, plus, driver = substitute.partition("+")
    return f"{base}{plus}{driver}://{rest}"


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
