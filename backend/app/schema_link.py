"""Schema linking: pick which tables the AI gets to see for a question.

Sending the whole database schema to the model on every question is expensive
(more tokens = more cost) and *hurts* accuracy (irrelevant tables distract the
model — the key finding behind the Spider benchmark's schema-linking work).
This module scores every table against the question and keeps only the most
relevant ones, then expands the selection along foreign keys so the chosen
tables can actually be JOINed together.

Public functions, in pipeline order (see docs/04-schema-linking.md):

- :func:`model_budget`         — how many tables/samples/examples the prompt may use
- :func:`link_relevant_tables` — score + select the tables for a question
- :func:`compact_schema`       — render the selected tables in a token-lean format
- :func:`compute_confidence`   — turn retrieval + execution signals into High/Medium/Low
"""

import logging
import re

import sqlglot
from sqlglot import exp

from backend.app.utils import _tokens

log = logging.getLogger(__name__)

# --- scoring weights --------------------------------------------------------
# A question token matching the TABLE NAME is the strongest signal; matching a
# key (PK/FK) column matters more than an ordinary column because keys carry
# the relational structure (Spider's schema-linking insight).
_W_TABLE_NAME = 3.0
_W_KEY_COLUMN = 1.5
_W_COLUMN = 1.0
_W_VALUE = 2.0  # question token matches a known cell value, e.g. "completed"
_W_VERIFIED = 5.0  # table appears in a previously verified similar answer
_W_CONTEXT = 8.0  # table was used by the previous query in this conversation
_MAX_COLUMN_POINTS = 4.0  # cap so very wide tables can't win on width alone
_MAX_VALUE_POINTS = 4.0
_FK_EXTRA_SLOTS = 4  # how many tables FK expansion may add beyond max_tables


def model_budget(provider, model):
    """Prompt budget for the configured Gemini model.

    All Gemini models have huge context windows, so the limit here is not what
    *fits* but what keeps cost low and accuracy high — more schema than needed
    measurably degrades text-to-SQL quality. Bigger models get a bigger budget
    because they are better at ignoring irrelevant tables.
    """
    m = (model or "").lower()
    if "lite" in m:
        return {"tier": "lite", "max_tables": 12, "samples": 1, "max_examples": 3}
    if "pro" in m:
        return {"tier": "pro", "max_tables": 25, "samples": 2, "max_examples": 5}
    return {"tier": "flash", "max_tables": 20, "samples": 2, "max_examples": 5}


def extract_table_names_from_prev_query(sql: str, dialect):
    """Table names used by the previous answer's SQL (for follow-up questions)."""
    if not sql:
        return set()
    _GLOT_DIALECT = {"postgresql": "postgres", "mssql": "tsql"}
    glot_dialect = _GLOT_DIALECT.get(dialect, dialect)
    try:
        stmts = sqlglot.parse_one(sql, read=glot_dialect)
        return {table.name for table in stmts.find_all(exp.Table)}
    except Exception:
        return set()


def _stem(tok):
    """Cheap singular/plural normalizer so 'order' matches table 'orders'
    and 'categories' matches 'category'. Not linguistics — just the two
    English plural forms that dominate table naming."""
    if len(tok) > 3 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _stems(text):
    return {_stem(t) for t in _tokens(text)}


def _question_stems(question, glossary):
    """Stems from the question, expanded with glossary meanings — but only for
    glossary terms the question actually mentions, so unrelated business terms
    don't drag in unrelated tables."""
    q = _stems(question)
    for g in glossary or []:
        term_stems = _stems(g.get("term", ""))
        if term_stems & q:
            q |= _stems(g.get("maps_to", "")) | _stems(g.get("sql_hint", ""))
    return q


def _score_table(name, info, q_stems):
    """Relevance of one table to the question (name, columns, known values)."""
    score = 0.0
    score += _W_TABLE_NAME * len(q_stems & _stems(name))

    fk_columns = {
        fk["column"] for fk in info.get("foreign_keys", []) if fk.get("column")
    }
    column_points = 0.0
    for col in info.get("columns", []):
        overlap = len(q_stems & _stems(col["name"]))
        if not overlap:
            continue
        weight = (
            _W_KEY_COLUMN
            if (col.get("primary_key") or col["name"] in fk_columns)
            else _W_COLUMN
        )
        column_points += weight * overlap
    score += min(column_points, _MAX_COLUMN_POINTS)

    value_points = 0.0
    for values in info.get("distinct_values", {}).values():
        for v in values:
            if q_stems & _stems(str(v)):
                value_points += _W_VALUE
    score += min(value_points, _MAX_VALUE_POINTS)
    return score


def _tables_in_verified_sql(all_tables, retrieved):
    """Tables mentioned by previously verified similar answers."""
    patterns = {t: re.compile(r"\b" + re.escape(t.lower()) + r"\b") for t in all_tables}
    used = set()
    for ex in retrieved or []:
        sql_low = (ex.get("sql", "") or "").lower()
        for t in all_tables:
            if patterns[t].search(sql_low):
                used.add(t)
    return used


def _fk_parents(schema, table):
    """Tables that `table` points at via its foreign keys."""
    parents = set()
    for fk in schema.get(table, {}).get("foreign_keys", []):
        ref = fk.get("references", "").split(".")[0]
        if ref and ref in schema:
            parents.add(ref)
    return parents


def link_relevant_tables(
    question, schema, glossary, retrieved, max_tables, context_tables
):
    """Pick the tables the model should see for this question.

    Returns an ordered list (most relevant first) of at most
    ``max_tables + 4`` table names. Selection happens in three steps:

    1. SCORE every table: question-token matches against the table name
       (weight 3), key columns (1.5), other columns (1), known cell values (2);
       plus +5 if a verified similar answer used the table and +8 if the
       previous query in this conversation did.
    2. SEED: take the ``max_tables`` best scorers (falling back to the largest
       tables when nothing matches at all).
    3. CONNECT: add FK parents of every seed (a fact table is useless without
       the dimension it references) and junction tables that link two seeds
       (e.g. order_items connecting orders and products) — so the model can
       always build the JOINs it needs.
    """
    all_tables = list(schema.keys())
    if len(all_tables) <= max_tables:
        return all_tables

    q_stems = _question_stems(question, glossary)
    verified = _tables_in_verified_sql(all_tables, retrieved)
    context_lookup = {t.lower() for t in context_tables}

    scores = {}
    for t, info in schema.items():
        s = _score_table(t, info, q_stems)
        if t in verified:
            s += _W_VERIFIED
        if t.lower() in context_lookup:
            s += _W_CONTEXT
        scores[t] = s

    ranked = sorted(all_tables, key=lambda t: (-scores[t], t))
    if all(scores[t] == 0 for t in all_tables):
        # Nothing matched — most likely a vague question. Prefer big tables:
        # they're usually the fact tables questions end up needing.
        ranked = sorted(all_tables, key=lambda t: -(schema[t].get("row_count") or 0))

    selected = set(ranked[:max_tables])

    # FK parents: every seed must be joinable to what it references.
    for t in list(selected):
        selected |= _fk_parents(schema, t)

    # Junction tables: a non-selected table whose FKs hit >= 2 selected tables
    # is almost certainly the bridge needed to join them (many-to-many).
    for t in all_tables:
        if t in selected:
            continue
        if len(_fk_parents(schema, t) & selected) >= 2:
            selected.add(t)

    # `ranked` contains every table, so filtering it both orders and covers
    # the whole selection.
    ordered = [t for t in ranked if t in selected]
    result = ordered[: max_tables + _FK_EXTRA_SLOTS]
    log.debug(
        "schema link: question=%r selected=%s scores=%s",
        question,
        result,
        {t: scores[t] for t in result},
    )
    return result


def compact_schema(schema, tables, samples):
    """Render selected tables in a token-lean one-line-per-table format.

    Example output line:
        orders(id PK, customer_id->customers.id, status[completed,pending], total) ~38104 rows
    """
    lines = []
    for t in tables:
        info = schema.get(t)
        if not info:
            continue
        fk_map = {
            fk["column"]: fk["references"]
            for fk in info.get("foreign_keys", [])
            if fk.get("column")
        }
        parts = []
        for c in info.get("columns", []):
            seg = c["name"]
            if c.get("primary_key"):
                seg += " PK"
            if c["name"] in fk_map:
                seg += f"->{fk_map[c['name']]}"
            dv = info.get("distinct_values", {}).get(c["name"])
            if dv:
                seg += "[" + ",".join(str(v) for v in dv[:6]) + "]"
            parts.append(seg)
        row_count = info.get("row_count")
        suffix = f" ~{row_count} rows" if row_count is not None else ""
        lines.append(f"{t}({', '.join(parts)}){suffix}")
        if samples and info.get("sample_rows"):
            lines.append(f"  e.g. {info['sample_rows'][0]}")
    return "\n".join(lines)


def compute_confidence(retrieved, exec_result):
    """Signal-based confidence: (level, plain-English reason, based_on_verified)."""
    if exec_result.get("error"):
        return "low", "the generated query did not run - please rephrase", False
    top_sim = max((e.get("similarity", 0) for e in retrieved), default=0)
    rows = exec_result.get("rows", []) or []
    if top_sim >= 0.78:
        return "high", "closely matches an answer you verified before", True
    if top_sim >= 0.50:
        return "medium", "similar to an answer you verified before", True
    if len(rows) == 0:
        return "low", "no matching rows - the question may not match your data", False
    return "medium", "new question - please confirm it is right", False
