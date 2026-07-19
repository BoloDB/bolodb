"""Static validation of generated SQL against an introspected schema.

Runs *before* execution: parses the SQL with sqlglot and checks that every
referenced table and column actually exists in the schema. This catches
hallucinated identifiers early and returns model-readable error messages that a
repair loop can feed back to the LLM (see issue #88).

Design note: the validator is deliberately *conservative*. It only reports a
problem when it is confident one exists, because a false rejection of valid SQL
is worse than missing a subtle error — the downstream execution step is the
final backstop. In practice that means: unresolved column qualifiers, columns
that could originate from a CTE or subquery, and anything inside an opaque
source are left alone rather than flagged.
"""

import logging
from sqlglot import exp, parse_one

log = logging.getLogger(__name__)

# sqlalchemy dialect name -> sqlglot dialect name (only where they differ).
# Mirrors backend/app/database.py so validation parses with the same dialect
# the query will run against.
_GLOT_DIALECT = {"postgresql": "postgres", "mssql": "tsql"}

# Dialects that let a SELECT alias be referenced in a HAVING clause. Standard
# SQL (and Postgres / SQL Server) disallow it; MySQL and SQLite permit it.
# ORDER BY and GROUP BY accept aliases everywhere we support.
_HAVING_ALIAS_DIALECTS = {"mysql", "sqlite"}


def _normalize_schema(schema):
    """Return {table_lower: {col_lower: original_col_name}} from a get_schema() dict."""
    norm = {}
    for tbl, info in (schema or {}).items():
        cols = {}
        for c in (info or {}).get("columns", []):
            name = c.get("name")
            if name:
                cols[name.lower()] = name
        norm[tbl.lower()] = cols
    return norm


def _alias_clause(col):
    """Classify where ``col`` sits relative to its nearest enclosing SELECT.

    Returns ``(clause, select)`` where ``clause`` is ``"order"``, ``"group"``,
    ``"having"`` or ``None`` (anything else — WHERE, JOIN ON, the projection
    list, ...). ``select`` is the enclosing SELECT node whose projection aliases
    are visible from that clause, so alias resolution stays scoped to the SELECT
    that actually defines them (a nested SELECT's aliases don't leak outward).
    """
    clause = None
    node = col.parent
    while node is not None:
        if isinstance(node, exp.Select):
            return clause, node
        if clause is None:
            if isinstance(node, exp.Order):
                clause = "order"
            elif isinstance(node, exp.Group):
                clause = "group"
            elif isinstance(node, exp.Having):
                clause = "having"
        node = node.parent
    return clause, None


def _projection_aliases(select):
    """Return the lower-cased SELECT-list aliases defined by ``select``."""
    return {
        a.alias.lower()
        for a in select.expressions
        if isinstance(a, exp.Alias) and a.alias
    }


def validate_sql(sql, schema, dialect=""):
    """Validate ``sql`` against ``schema`` (the dict shape from ``DatabaseManager.get_schema``).

    Returns ``{"ok": bool, "errors": [str]}``. ``errors`` is empty when ``ok`` is
    True. Each error is a plain sentence suitable for feeding back into an LLM
    repair prompt.
    """
    sql = (sql or "").strip()
    if not sql:
        return {"ok": False, "errors": ["Empty SQL statement."]}

    glot_dialect = _GLOT_DIALECT.get(dialect, dialect) or None
    try:
        tree = parse_one(sql, dialect=glot_dialect)
    except Exception:  # sqlglot raises ParseError and friends
        log.warning("SQL parse failed during validation", exc_info=True)
        return {"ok": False, "errors": ["Could not parse SQL statement."]}
    if tree is None:
        return {"ok": False, "errors": ["Could not parse SQL: empty parse result."]}

    norm = _normalize_schema(schema)
    errors = []

    # Sources whose output columns are produced dynamically and therefore can't
    # be checked against the schema: CTEs and aliased subqueries.
    cte_names = {c.alias.lower() for c in tree.find_all(exp.CTE) if c.alias}
    opaque_sources = set(cte_names)
    for sub in tree.find_all(exp.Subquery):
        if sub.alias:
            opaque_sources.add(sub.alias.lower())

    # Cache of a SELECT node's projection aliases, keyed by object id, so the
    # per-clause alias check below stays scoped to the defining SELECT.
    alias_cache = {}

    # Map every alias / table name in use to its resolved base table (for real
    # schema tables only), and collect the set of real tables referenced.
    alias_to_table = {}
    real_tables_in_use = set()
    for t in tree.find_all(exp.Table):
        tname = (t.name or "").lower()
        if not tname:
            continue
        if tname in norm:
            real_tables_in_use.add(tname)
            alias_to_table[tname] = tname
            if t.alias:
                alias_to_table[t.alias.lower()] = tname
        elif tname in cte_names:
            # Referencing a CTE by name; track any alias as opaque too.
            if t.alias:
                opaque_sources.add(t.alias.lower())
        else:
            errors.append(f"Unknown table: '{t.name}' is not in the database schema.")

            # Unknown tables make unqualified column resolution ambiguous; treat them as opaque.
            opaque_sources.add(tname)
            if t.alias:
                opaque_sources.add(t.alias.lower())
    for col in tree.find_all(exp.Column):
        cname = (col.name or "").lower()
        if not cname:
            continue  # e.g. the Star in `t.*`
        qualifier = (col.table or "").lower()

        if qualifier:
            if qualifier in alias_to_table:
                tbl = alias_to_table[qualifier]
                if cname not in norm.get(tbl, {}):
                    errors.append(
                        f"Unknown column: '{col.name}' does not exist in table '{tbl}'."
                    )
            # Qualifier pointing at a CTE/subquery alias, or one we can't
            # resolve, is left unchecked to avoid false positives.
            continue

        # Unqualified column: accept if it exists in any real table in scope.
        if any(cname in norm[t] for t in real_tables_in_use):
            continue
        # Accept if it matches a SELECT alias, but only where SQL actually
        # allows referencing one: ORDER BY / GROUP BY (all dialects) and HAVING
        # (MySQL / SQLite only). Aliases in WHERE, JOIN ON, etc. are not valid
        # references, so an unknown column there is still flagged. The alias set
        # comes from the enclosing SELECT so nested-SELECT aliases don't leak.
        clause, select = _alias_clause(col)
        if clause == "order" or clause == "group" or (
            clause == "having" and dialect in _HAVING_ALIAS_DIALECTS
        ):
            if select is not None:
                aliases = alias_cache.get(id(select))
                if aliases is None:
                    aliases = _projection_aliases(select)
                    alias_cache[id(select)] = aliases
                if cname in aliases:
                    continue
        # If an opaque source is present, the column might come from it — don't
        # flag. Only report when every source is a known table and none has it.
        if opaque_sources or not real_tables_in_use:
            continue
        errors.append(
            f"Unknown column: '{col.name}' does not exist in any of the "
            f"referenced tables ({', '.join(sorted(real_tables_in_use))})."
        )

    # De-duplicate while preserving order.
    seen = set()
    deduped = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    return {"ok": not deduped, "errors": deduped}
