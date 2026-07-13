"""Semantic catalog helpers (issue #90).

The catalog (see :mod:`backend.app.knowledge`) maps business language to schema
entities, filters and joins. This module:

* turns an introspected schema into *suggested* catalog entries for the
  onboarding / curation flow — joins from foreign keys and value maps from the
  low-cardinality ``distinct_values`` already captured in
  ``backend/app/database.py`` — a reliable backbone the LLM then enriches; and
* filters a stored catalog down to the tables a query actually touches before
  it goes into the generation prompt, so wide schemas stay token-lean.
"""

import re
from backend.app.i18n.translator import _

_CATALOG_KEYS = (
    "column_descriptions",
    "metrics",
    "joins",
    "synonyms",
    "value_maps",
)


def empty_catalog():
    """An empty catalog dict with all five category lists present."""
    return {k: [] for k in _CATALOG_KEYS}


def _humanize(value):
    """`in_progress` / `IN-PROGRESS` -> `In progress` (a first-guess label)."""
    s = re.sub(r"[_\-]+", " ", str(value)).strip()
    return (s[:1].upper() + s[1:]) if s else str(value)


def _join_tables(join):
    """The set of lower-cased table names referenced by a join entry."""
    raw = join.get("tables", "") or ""
    return {t.strip().lower() for t in re.split(r"[,\s]+", raw) if t.strip()}


def suggest_from_schema(schema):
    """Deterministic catalog suggestions derived purely from the schema — no
    LLM needed. Foreign keys become join paths; the low-cardinality distinct
    values already captured become value-map scaffolding with a humanized
    first-guess label the user (or LLM enrichment) can refine."""
    out = empty_catalog()
    seen_joins = set()
    for tbl, info in schema.items():
        for fk in info.get("foreign_keys", []) or []:
            col = fk.get("column")
            ref = fk.get("references", "") or ""
            parent = ref.split(".")[0]
            if not col or not parent:
                continue
            key = (tbl, col, ref)
            if key in seen_joins:
                continue
            seen_joins.add(key)
            out["joins"].append(
                {
                    "tables": f"{tbl},{parent}",
                    "join_condition": f"{tbl}.{col} = {ref}",
                    "description": _("each {table} row links to one {parent}").format(
                        table=tbl, parent=parent
                    ),
                }
            )
        for col, values in (info.get("distinct_values", {}) or {}).items():
            for v in values:
                sval = str(v)
                out["value_maps"].append(
                    {
                        "table": tbl,
                        "column": col,
                        "db_value": sval,
                        "business_label": _humanize(sval),
                    }
                )
    return out


def merge_catalog_suggestions(schema_based, llm_based):
    """Combine the deterministic backbone with the LLM's enrichment.

    Joins and the set of value mappings come from the schema (reliable);
    column descriptions, metrics and synonyms come from the LLM; and the LLM's
    nicer business labels replace the humanized guesses on matching value maps.
    """
    llm_based = llm_based or {}
    out = empty_catalog()
    out["joins"] = list(schema_based.get("joins", []) or [])
    out["column_descriptions"] = list(llm_based.get("column_descriptions", []) or [])
    out["metrics"] = list(llm_based.get("metrics", []) or [])
    out["synonyms"] = list(llm_based.get("synonyms", []) or [])

    label_overrides = {}
    for v in llm_based.get("value_maps", []) or []:
        k = (
            (v.get("table", "") or "").lower(),
            (v.get("column", "") or "").lower(),
            str(v.get("db_value", "")),
        )
        label = (v.get("business_label", "") or "").strip()
        if label:
            label_overrides[k] = label

    value_maps = []
    for v in schema_based.get("value_maps", []) or []:
        k = (
            (v.get("table", "") or "").lower(),
            (v.get("column", "") or "").lower(),
            str(v.get("db_value", "")),
        )
        value_maps.append(
            {**v, "business_label": label_overrides.get(k, v["business_label"])}
        )
    out["value_maps"] = value_maps
    return out


def filter_catalog(catalog, tables):
    """Keep only the catalog entries relevant to ``tables``.

    Metrics and synonyms are global (few, high-signal) so they pass through;
    column notes, value maps and joins are scoped to the linked tables so wide
    schemas don't bloat the prompt."""
    if not catalog:
        return catalog
    tset = {t.lower() for t in tables}
    out = dict(catalog)
    out["column_descriptions"] = [
        c
        for c in catalog.get("column_descriptions", []) or []
        if (c.get("table", "") or "").lower() in tset
    ]
    out["value_maps"] = [
        v
        for v in catalog.get("value_maps", []) or []
        if (v.get("table", "") or "").lower() in tset
    ]
    # A join path only helps when both of its tables are in the prompt.
    out["joins"] = [
        j
        for j in catalog.get("joins", []) or []
        if _join_tables(j) and _join_tables(j) <= tset
    ]
    out["metrics"] = list(catalog.get("metrics", []) or [])
    out["synonyms"] = list(catalog.get("synonyms", []) or [])
    return out
