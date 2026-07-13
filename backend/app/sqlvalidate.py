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

from sqlglot import exp, parse_one
from backend.app.i18n.translator import _

# sqlalchemy dialect name -> sqlglot dialect name (only where they differ).
# Mirrors backend/app/database.py so validation parses with the same dialect
# the query will run against.
_GLOT_DIALECT = {"postgresql": "postgres", "mssql": "tsql"}


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


def validate_sql(sql, schema, dialect=""):
    """Validate ``sql`` against ``schema`` (the dict shape from ``DatabaseManager.get_schema``).

    Returns ``{"ok": bool, "errors": [str]}``. ``errors`` is empty when ``ok`` is
    True. Each error is a plain sentence suitable for feeding back into an LLM
    repair prompt.
    """
    sql = (sql or "").strip()
    if not sql:
        return {"ok": False, "errors": [_("Empty SQL statement.")]}

    glot_dialect = _GLOT_DIALECT.get(dialect, dialect) or None
    try:
        tree = parse_one(sql, dialect=glot_dialect)
    except Exception as e:  # sqlglot raises ParseError and friends
        return {
            "ok": False,
            "errors": [_("Could not parse SQL: {error}").format(error=e)],
        }
    if tree is None:
        return {"ok": False, "errors": [_("Could not parse SQL: empty parse result.")]}

    norm = _normalize_schema(schema)
    errors = []

    # Sources whose output columns are produced dynamically and therefore can't
    # be checked against the schema: CTEs and aliased subqueries.
    cte_names = {c.alias.lower() for c in tree.find_all(exp.CTE) if c.alias}
    opaque_sources = set(cte_names)
    for sub in tree.find_all(exp.Subquery):
        if sub.alias:
            opaque_sources.add(sub.alias.lower())

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
            errors.append(
                _("Unknown table: '{table}' is not in the database schema.").format(
                    table=t.name
                )
            )

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
                        _(
                            "Unknown column: '{column}' does not exist in table '{table}'."
                        ).format(column=col.name, table=tbl)
                    )
            # Qualifier pointing at a CTE/subquery alias, or one we can't
            # resolve, is left unchecked to avoid false positives.
            continue

        # Unqualified column: accept if it exists in any real table in scope.
        if any(cname in norm[t] for t in real_tables_in_use):
            continue
        # If an opaque source is present, the column might come from it — don't
        # flag. Only report when every source is a known table and none has it.
        if opaque_sources or not real_tables_in_use:
            continue
        errors.append(
            _(
                "Unknown column: '{column}' does not exist in any of the referenced tables ({tables})."
            ).format(column=col.name, tables=", ".join(sorted(real_tables_in_use)))
        )

    # De-duplicate while preserving order.
    seen = set()
    deduped = []
    for e in errors:
        if e not in seen:
            seen.add(e)
            deduped.append(e)
    return {"ok": not deduped, "errors": deduped}
