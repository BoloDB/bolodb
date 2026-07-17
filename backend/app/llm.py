"""All AI operations for BoloDB, powered by OpenRouter (deepseek-v4-flash).

This module is the ONLY place in the backend that talks to an AI model.
"""

import json
import logging
import os
import re
import time
from abc import ABC, abstractmethod

import openai

log = logging.getLogger(__name__)

MODEL = "deepseek-v4-flash"


def _redact_error_text(text, max_len=200):
    s = text[:max_len]
    s = re.sub(r"sk-[A-Za-z0-9]{10,}", "[REDACTED_KEY]", s)
    s = re.sub(r"Bearer\s+[A-Za-z0-9._-]{20,}", "Bearer [REDACTED]", s)
    return s


class LLMError(Exception):
    def __init__(self, user_message, detail=""):
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail or user_message


def parse_json(text):
    s = text.replace("```json", "").replace("```", "").strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a : b + 1]
    return json.loads(s)


SQL_SCHEMA = {
    "name": "sql_result",
    "schema": {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "One read-only SELECT query answering the question.",
            },
            "restatement": {
                "type": "string",
                "description": "One plain sentence describing what the query returns, no jargon.",
            },
            "assumptions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Any assumptions made while interpreting the question.",
            },
        },
        "required": ["sql", "restatement", "assumptions"],
        "additionalProperties": False,
    },
}

GLOSSARY_SCHEMA = {
    "name": "glossary",
    "schema": {
        "type": "object",
        "properties": {
            "glossary": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "maps_to": {"type": "string"},
                        "sql_hint": {"type": "string"},
                    },
                    "required": ["term", "maps_to", "sql_hint"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["glossary"],
        "additionalProperties": False,
    },
}

STARTERS_SCHEMA = {
    "name": "starters",
    "schema": {
        "type": "object",
        "properties": {
            "starters": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "sql": {"type": "string"},
                        "restatement": {"type": "string"},
                    },
                    "required": ["question", "sql", "restatement"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["starters"],
        "additionalProperties": False,
    },
}

EXPLAIN_SCHEMA = {
    "name": "explanation",
    "schema": {
        "type": "object",
        "properties": {
            "explanation": {
                "type": "string",
                "description": "2-4 plain sentences a non-technical person understands.",
            }
        },
        "required": ["explanation"],
        "additionalProperties": False,
    },
}

CATALOG_SCHEMA = {
    "name": "catalog",
    "schema": {
        "type": "object",
        "properties": {
            "column_descriptions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "column": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["table", "column", "description"],
                    "additionalProperties": False,
                },
            },
            "metrics": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "sql_expression": {"type": "string"},
                    },
                    "required": ["name", "sql_expression"],
                    "additionalProperties": False,
                },
            },
            "synonyms": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "term": {"type": "string"},
                        "entity_type": {"type": "string"},
                        "entity_name": {"type": "string"},
                    },
                    "required": ["term", "entity_type", "entity_name"],
                    "additionalProperties": False,
                },
            },
            "value_maps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "column": {"type": "string"},
                        "db_value": {"type": "string"},
                        "business_label": {"type": "string"},
                    },
                    "required": ["table", "column", "db_value", "business_label"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["column_descriptions", "metrics", "synonyms", "value_maps"],
        "additionalProperties": False,
    },
}

SHORTLIST_SCHEMA = {
    "name": "shortlist",
    "schema": {
        "type": "object",
        "properties": {
            "tables": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Names of tables from the catalog that may be needed.",
            }
        },
        "required": ["tables"],
        "additionalProperties": False,
    },
}


def parse_sql_output(raw):
    if isinstance(raw, dict):
        obj = raw
    else:
        try:
            obj = parse_json(raw)
        except Exception:
            obj = {}
    if not isinstance(obj, dict):
        obj = {}
    sql = obj.get("sql")
    restatement = obj.get("restatement")
    assumptions = obj.get("assumptions")
    if isinstance(assumptions, str):
        assumptions = [assumptions] if assumptions.strip() else []
    elif isinstance(assumptions, list):
        assumptions = [str(a) for a in assumptions if str(a).strip()]
    else:
        assumptions = []
    sql = (sql if isinstance(sql, str) else ("" if sql is None else str(sql))).strip()
    restatement = (
        restatement
        if isinstance(restatement, str)
        else ("" if restatement is None else str(restatement))
    ).strip()
    return {"sql": sql, "restatement": restatement, "assumptions": assumptions}


class LLMProvider(ABC):
    @abstractmethod
    async def complete(self, system, user, json_mode=False, schema=None): ...

    @abstractmethod
    async def health_check(self): ...


class OpenRouterProvider(LLMProvider):
    def __init__(self, api_key, model=None):
        self.api_key = api_key
        self.model = model or MODEL
        self._client = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            max_retries=2,
        )

    async def complete(self, system, user, json_mode=False, schema=None, **kwargs):
        if not self.api_key:
            raise LLMError(
                "OpenRouter API key is not configured. "
                "Set OPENROUTER_API_KEY in the server environment.",
                detail="empty api_key",
            )
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})

        completion_kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4096,
        }
        if json_mode and schema:
            schema_copy = dict(schema)
            name = schema_copy.pop("name", "response")
            completion_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": name,
                    "strict": True,
                    "schema": schema_copy,
                },
            }
        elif json_mode:
            completion_kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = await self._client.chat.completions.create(**completion_kwargs)
        except openai.APIError as e:
            raise LLMError(
                "The AI service returned an error. Please try again.",
                detail=f"OpenRouter API error: {_redact_error_text(str(e))}",
            )
        except Exception as e:
            raise LLMError(
                "Could not reach the AI service — check your internet connection.",
                detail=f"OpenRouter error: {_redact_error_text(str(e))}",
            )

        choices = resp.choices if hasattr(resp, "choices") else []
        if not choices:
            raise LLMError(
                "The AI returned an empty answer — please try again.",
                detail="no choices in response",
            )
        text = (choices[0].message.content or "").strip()
        if not text:
            raise LLMError(
                "The AI returned an empty answer — please try again.",
                detail="empty content",
            )
        return text

    async def health_check(self):
        if not self.api_key:
            return {"ok": False, "error": "No OpenRouter API key configured"}
        try:
            await self.complete("Respond with OK", "OK", json_mode=False)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}


def create_provider(cfg, user_id=None):
    key = cfg.get("openrouter_key", "") or os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Set it in the environment or config to use AI features."
        )
    return OpenRouterProvider(api_key=key)


class ProviderManager:
    def __init__(self, cfg):
        self.cfg = cfg
        self._provider = None

    def get(self, user_id=None):
        if self._provider is None:
            self._provider = create_provider(self.cfg)
        return self._provider

    def invalidate(self, user_id=None):
        self._provider = None

    def reconfigure(self, cfg):
        self.cfg = cfg
        self._provider = None


_DIALECT_HINTS = {
    "sqlite": "Dates: use date()/strftime(); string concat is ||; no ILIKE (use LIKE, it is case-insensitive for ASCII).",
    "postgresql": "Dates: use date_trunc()/interval arithmetic; ILIKE is available; quote mixed-case identifiers.",
    "mysql": "Dates: use DATE_FORMAT()/DATE_SUB(); identifiers quote with backticks; LIMIT syntax applies.",
    "mssql": "Use TOP (N) instead of LIMIT; dates via DATEADD()/DATEDIFF(); string concat is +.",
    "duckdb": "PostgreSQL-like syntax; date_trunc()/interval work; ILIKE is available.",
}


def _context_block(context):
    if not context:
        return ""
    items = ""
    for prev in context[-2:]:
        items += (
            "BEGIN_CONTEXT_ITEM\n"
            + json.dumps(
                {
                    "question": prev.question,
                    "sql": prev.sql,
                    "restatement": prev.restatement,
                },
                ensure_ascii=False,
            )
            + "\nEND_CONTEXT_ITEM\n"
        )
    return (
        "Recent conversation (use it to resolve follow-ups and references like "
        '"those", "that year", "filter this"). If the question modifies the '
        "previous one, adapt the previous SQL instead of starting over:\n"
        f"{items}\n"
    )


def _glossary_block(glossary):
    if not glossary:
        return ""
    lines = []
    for g in glossary:
        line = f"- {g.get('term', '')} = {g.get('maps_to', '')}"
        if g.get("sql_hint"):
            line += f" (SQL hint: {g['sql_hint']})"
        lines.append(line)
    return (
        "Term meanings the user has confirmed (treat as ground truth):\n"
        + "\n".join(lines)
        + "\n\n"
    )


def _semantic_block(catalog):
    if not catalog:
        return ""
    sections = []

    metrics = catalog.get("metrics") or []
    if metrics:
        lines = []
        for m in metrics:
            line = f"- {m.get('name', '')} = {m.get('sql_expression', '')}"
            if m.get("description"):
                line += f"  ({m['description']})"
            lines.append(line)
        sections.append(
            "Metric definitions (use these exact expressions):\n" + "\n".join(lines)
        )

    value_maps = catalog.get("value_maps") or []
    if value_maps:
        grouped = {}
        for v in value_maps:
            key = f"{v.get('table', '')}.{v.get('column', '')}"
            grouped.setdefault(key, []).append(
                f'"{v.get("business_label", "")}" = {v.get("db_value", "")!r}'
            )
        lines = [f"- {k}: " + ", ".join(vs) for k, vs in grouped.items()]
        sections.append(
            "Value meanings (the business label on the left maps to the stored "
            "value on the right — filter on the stored value):\n" + "\n".join(lines)
        )

    synonyms = catalog.get("synonyms") or []
    if synonyms:
        lines = [
            f'- "{s.get("term", "")}" -> {s.get("entity_name", "")} '
            f"({s.get('entity_type', '')})"
            for s in synonyms
        ]
        sections.append(
            "Synonyms (business word -> schema entity):\n" + "\n".join(lines)
        )

    joins = catalog.get("joins") or []
    if joins:
        lines = []
        for j in joins:
            line = f"- {j.get('join_condition', '')}"
            if j.get("description"):
                line += f"  ({j['description']})"
            lines.append(line)
        sections.append("Preferred join paths:\n" + "\n".join(lines))

    cols = catalog.get("column_descriptions") or []
    if cols:
        lines = [
            f"- {c.get('table', '')}.{c.get('column', '')}: {c.get('description', '')}"
            for c in cols
        ]
        sections.append("Column notes:\n" + "\n".join(lines))

    if not sections:
        return ""
    return (
        "Business catalog for this database (curated by the user — treat as "
        "ground truth):\n" + "\n\n".join(sections) + "\n\n"
    )


def _examples_block(retrieved, max_examples):
    if not retrieved:
        return ""
    ex_lines = [
        f"Q: {e['question']}\nSQL: {e['sql']}" for e in retrieved[:max_examples]
    ]
    return (
        "Previously verified correct examples for this database (reuse their "
        "patterns, joins and filters where applicable):\n"
        + "\n".join(ex_lines)
        + "\n\n"
    )


def build_sql_system_prompt(
    schema_text, dialect, glossary, retrieved, max_examples, context, catalog=None
):
    hint = _DIALECT_HINTS.get(dialect, "")
    return (
        f"You are an expert {dialect} analyst. Convert the user's question into "
        "exactly one read-only SELECT query.\n\n"
        "Rules:\n"
        "1. SELECT (or WITH ... SELECT) only — never modify data.\n"
        "2. Use ONLY the tables and columns listed in the schema below. Never "
        "invent names.\n"
        "3. Join tables via the foreign keys shown as col->table.column.\n"
        "4. Add LIMIT 100 unless the question asks for a single total/count "
        "or the dialect uses TOP.\n"
        "5. When filtering on a column whose example values are shown in "
        "[brackets], match those values exactly.\n"
        "6. Qualify column names with table aliases whenever more than one "
        "table is involved.\n"
        f"7. {hint}\n\n"
        f"Schema (col PK = primary key, col->t.c = foreign key, [v1,v2] = "
        f"example values):\n{schema_text}\n\n"
        f"{_glossary_block(glossary)}"
        f"{_semantic_block(catalog)}"
        f"{_examples_block(retrieved, max_examples)}"
        f"{_context_block(context)}"
        "Reply ONLY with this JSON, nothing else:\n"
        '{"sql":"<one SELECT query>",'
        '"restatement":"<one plain sentence of what the query returns, no jargon>",'
        '"assumptions":["<any assumption you made, e.g. how you read a vague term '
        'or date range; empty list if none>"]}'
    )


async def generate_sql(
    provider,
    question,
    schema_text,
    dialect,
    glossary,
    retrieved,
    max_examples=3,
    context=None,
    feedback="",
    catalog=None,
):
    if context is None:
        context = []
    system = build_sql_system_prompt(
        schema_text, dialect, glossary, retrieved, max_examples, context, catalog
    )
    user = question if not feedback else f"{question}\n\n{feedback}"
    result = parse_sql_output(
        await provider.complete(system, user, json_mode=True, schema=SQL_SCHEMA)
    )
    if not result["sql"]:
        result = parse_sql_output(
            await provider.complete(
                system + "\nReturn ONLY valid JSON.",
                user,
                json_mode=True,
                schema=SQL_SCHEMA,
            )
        )
    return result


async def shortlist_tables(provider, question, schema, max_columns=4):
    start = time.monotonic()
    lines = []
    for t, info in schema.items():
        cols = [c["name"] for c in info.get("columns", [])]
        head = ", ".join(cols[:max_columns])
        more = ", …" if len(cols) > max_columns else ""
        lines.append(f"{t}({head}{more})")
    catalog = "\n".join(lines)
    system = (
        "You map questions to database tables. Below is the complete catalog "
        "of tables (name and columns only).\n"
        "Return every table that might be needed to answer the user's "
        "question — including the join/bridge tables that connect them. "
        "Prefer including a borderline table over dropping it. Use ONLY names "
        "from the catalog.\n\n"
        f"Catalog:\n{catalog}\n\n"
        'Reply ONLY with JSON: {"tables":["name1","name2",...]}'
    )
    raw = await provider.complete(
        system, question, json_mode=True, schema=SHORTLIST_SCHEMA
    )
    elapsed = time.monotonic() - start
    catalog_tokens = len(catalog) // 4
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    names = obj.get("tables", [])
    if not isinstance(names, list):
        names = []
    by_lower = {t.lower(): t for t in schema}
    validated = {by_lower[str(n).lower()] for n in names if str(n).lower() in by_lower}
    log.info(
        "shortlist: %d tables in catalog (~%d tokens), "
        "LLM took %.1fs, returned %d / %d validated",
        len(schema),
        catalog_tokens,
        elapsed,
        len(validated),
        len(names),
    )
    return validated


async def explain_sql(provider, sql, dialect):
    system = (
        f"You explain {dialect} SQL to non-technical business users.\n"
        "Describe what the query returns in 2-4 short plain sentences: which "
        "data it looks at, how it filters/groups, and how results are ordered "
        "or limited. No SQL keywords, no jargon.\n"
        'Reply ONLY with JSON: {"explanation":"..."}'
    )
    raw = await provider.complete(system, sql, json_mode=True, schema=EXPLAIN_SCHEMA)
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return {"explanation": str(obj.get("explanation", "")).strip()}


async def suggest_catalog(provider, schema_text):
    system = (
        "You are a data analyst documenting a database for non-technical users.\n"
        f"{schema_text}\n\n"
        "Produce a concise semantic catalog:\n"
        "- column_descriptions: a short plain-English meaning for columns whose "
        "purpose is not obvious from the name (skip the obvious ones).\n"
        "- metrics: the business metrics people ask for (e.g. revenue) as a "
        "name, a one-line description, and a SQL expression built from the real "
        "table/column names in the schema.\n"
        "- synonyms: business words a user might say, each mapped to the "
        "matching table or column (entity_type is 'table' or 'column').\n"
        "- value_maps: for columns whose example values appear in [brackets], "
        "give each stored value a friendly business_label.\n"
        "Use ONLY tables and columns that appear in the schema. Keep it tight."
    )
    raw = await provider.complete(
        system,
        "Produce the catalog.",
        json_mode=True,
        schema=CATALOG_SCHEMA,
    )
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return {
        "column_descriptions": obj.get("column_descriptions", []) or [],
        "metrics": obj.get("metrics", []) or [],
        "synonyms": obj.get("synonyms", []) or [],
        "value_maps": obj.get("value_maps", []) or [],
    }


async def generate_glossary(provider, schema_text):
    system = (
        f"You are a database analyst.\n{schema_text}\n\n"
        "Identify the 3 most important BUSINESS TERMS a non-technical user of this database would say "
        "(e.g. revenue, active customer, best seller) and map each to plain language + a short SQL hint.\n"
        'Return ONLY JSON: {"glossary":[{"term":"...","maps_to":"<plain>","sql_hint":"<sql>"}]}'
    )
    raw = await provider.complete(
        system,
        "Produce the glossary.",
        json_mode=True,
        schema=GLOSSARY_SCHEMA,
    )
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return obj.get("glossary", [])


async def generate_starters(provider, schema_text, dialect):
    system = (
        f"You are a database analyst. {dialect} database.\n{schema_text}\n\n"
        "Generate 3 common useful questions a non-technical user would ask, each with the SQL and "
        "a one-sentence plain-English description.\n"
        'Return ONLY JSON: {"starters":[{"question":"...","sql":"...","restatement":"..."}]}'
    )
    raw = await provider.complete(
        system,
        "Produce starter questions.",
        json_mode=True,
        schema=STARTERS_SCHEMA,
    )
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return obj.get("starters", [])
