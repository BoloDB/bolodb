"""All AI operations for BoloDB, powered by the Google Gemini API.

This module is the ONLY place in the backend that talks to an AI model.
Everything AI-related funnels through here:

- :func:`generate_sql`      — turn a plain-English question into one SELECT query
- :func:`explain_sql`       — turn a SQL query back into plain English (trust feature)
- :func:`generate_glossary` — suggest business-term meanings during onboarding
- :func:`generate_starters` — suggest example questions during onboarding

All four functions take a *provider* (today always :class:`GeminiProvider`) as
their first argument. The provider abstraction is deliberately kept thin so a
second AI vendor can be added later by writing one new class and registering it
in :func:`create_provider` — nothing else in the codebase would change.

Cost design (see docs/09-cost-optimisation.md):
- Prompts contain only the *linked* tables (see schema_link.py), rendered in a
  compact one-line-per-table format — not the whole database.
- Structured output (``responseSchema``) means the model can't ramble; we pay
  for exactly the JSON fields we asked for.
- Gemini "thinking" is disabled for cheap tasks (glossary, starters, explain)
  and left dynamic for SQL generation, where accuracy matters most.
- ``maxOutputTokens`` caps every call, and transient failures retry with
  exponential backoff instead of hammering the API.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod

import httpx

from backend.app.config import decrypt_api_key

log = logging.getLogger(__name__)

# The model used when the config doesn't name one. Flash is the sweet spot:
# near-Pro accuracy on text-to-SQL at a fraction of the cost, with a free tier.
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Transient HTTP statuses worth retrying (rate limit / server hiccups).
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3  # 1 try + 2 retries, backoff 1s then 2s


class LLMError(Exception):
    """Raised when the AI call fails in a way the caller should surface.

    ``user_message`` is safe to show to a non-technical user; ``detail`` keeps
    the raw technical cause for logs and debugging.
    """

    def __init__(self, user_message, detail=""):
        super().__init__(detail or user_message)
        self.user_message = user_message
        self.detail = detail or user_message


def parse_json(text):
    """Tolerantly extract a JSON object from model text (strips ``` fences)."""
    s = text.replace("```json", "").replace("```", "").strip()
    a, b = s.find("{"), s.rfind("}")
    if a != -1 and b != -1:
        s = s[a : b + 1]
    return json.loads(s)


# JSON schema for the SQL-generation response. Passed to the provider so the
# model is constrained to this exact shape, and used to document the contract.
SQL_SCHEMA = {
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
            "description": (
                "Any assumptions made while interpreting the question — e.g. how a "
                "vague term or date range was resolved. Empty list if none."
            ),
        },
    },
    "required": ["sql", "restatement", "assumptions"],
    "additionalProperties": False,
}

GLOSSARY_SCHEMA = {
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
            },
        }
    },
    "required": ["glossary"],
}

STARTERS_SCHEMA = {
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
            },
        }
    },
    "required": ["starters"],
}

EXPLAIN_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {
            "type": "string",
            "description": "2-4 plain sentences a non-technical person understands.",
        }
    },
    "required": ["explanation"],
}


def parse_sql_output(raw):
    """Normalize a model SQL response into ``{sql, restatement, assumptions}``.

    Accepts either a ``dict`` (already-parsed structured output) or raw text
    (parsed tolerantly via :func:`parse_json`). Missing or wrongly-typed fields
    get safe defaults — this never raises, so callers can treat an empty ``sql``
    as "generation failed".
    """
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


def to_gemini_schema(schema):
    """Convert a standard JSON schema into Gemini's ``responseSchema`` subset.

    Gemini's v1beta API accepts an OpenAPI-style schema that supports
    type/properties/required/items/description/enum but rejects keys like
    ``additionalProperties``. Strip anything it doesn't understand so the same
    schema constants can be shared with other providers later.
    """
    if isinstance(schema, dict):
        allowed = {
            "type",
            "format",
            "description",
            "enum",
            "items",
            "properties",
            "required",
            "nullable",
        }
        out = {}
        for k, v in schema.items():
            if k not in allowed:
                continue
            if k == "properties":
                # keys here are property NAMES, values are sub-schemas
                out[k] = {name: to_gemini_schema(sub) for name, sub in v.items()}
            elif k == "items":
                out[k] = to_gemini_schema(v)
            else:
                out[k] = v
        return out
    if isinstance(schema, list):
        return [to_gemini_schema(v) for v in schema]
    return schema


class LLMProvider(ABC):
    """Interface every AI vendor integration must implement.

    To add a new vendor later: subclass this, implement both methods, and add a
    branch to :func:`create_provider`. Nothing else needs to change.
    """

    @abstractmethod
    async def complete(self, system, user, json_mode=False, schema=None): ...

    @abstractmethod
    async def health_check(self): ...


class GeminiProvider(LLMProvider):
    """Google Gemini via the REST ``generateContent`` endpoint.

    Uses plain httpx (no SDK dependency). One call = one POST to
    ``{GEMINI_BASE_URL}/models/{model}:generateContent`` with the API key in the
    ``x-goog-api-key`` header.
    """

    def __init__(self, api_key, model=""):
        self.api_key = api_key
        self.model = model or DEFAULT_GEMINI_MODEL

    def _build_body(self, system, user, json_mode, schema, thinking_budget):
        generation_config = {
            # Low temperature: SQL generation should be deterministic, not creative.
            "temperature": 0.1,
            "maxOutputTokens": 4096,
        }
        if schema is not None:
            generation_config["responseMimeType"] = "application/json"
            generation_config["responseSchema"] = to_gemini_schema(schema)
        elif json_mode:
            generation_config["responseMimeType"] = "application/json"
        # thinkingConfig only exists on 2.5-series models; sending it to older
        # models is a hard 400, so gate on the model name.
        if thinking_budget is not None and "2.5" in self.model:
            generation_config["thinkingConfig"] = {"thinkingBudget": thinking_budget}
        return {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": generation_config,
        }

    async def complete(
        self, system, user, json_mode=False, schema=None, thinking_budget=None
    ):
        """Send one prompt, return the model's text. Retries transient failures.

        Raises :class:`LLMError` with a user-readable message on anything that
        can't be retried away (bad key, quota exhausted, blocked content...).
        """
        if not self.api_key:
            raise LLMError(
                "No Gemini API key is configured. Add one in Settings "
                "(get a free key at https://aistudio.google.com/app/api-keys).",
                detail="empty api_key",
            )
        body = self._build_body(system, user, json_mode, schema, thinking_budget)
        url = f"{GEMINI_BASE_URL}/models/{self.model}:generateContent"
        last_error = None
        for attempt in range(_MAX_ATTEMPTS):
            if attempt:
                await asyncio.sleep(2 ** (attempt - 1))  # 1s, 2s
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    r = await client.post(
                        url,
                        headers={
                            "x-goog-api-key": self.api_key,
                            "content-type": "application/json",
                        },
                        json=body,
                    )
            except httpx.HTTPError as e:
                last_error = LLMError(
                    "Could not reach the Gemini API — check your internet "
                    "connection and try again.",
                    detail=f"network error: {e}",
                )
                log.warning("Gemini network error (attempt %d): %s", attempt + 1, e)
                continue

            if r.status_code in _RETRYABLE_STATUS:
                last_error = LLMError(
                    "The AI service is busy right now — please try again in a moment.",
                    detail=f"HTTP {r.status_code}: {r.text[:300]}",
                )
                log.warning(
                    "Gemini transient HTTP %d (attempt %d)", r.status_code, attempt + 1
                )
                continue

            # Distinct messages per status. Note: Gemini returns 400 (not 401)
            # for "API key not valid", so 400 mentions the key too.
            if r.status_code == 400:
                raise LLMError(
                    "The Gemini API rejected the request as invalid — most "
                    "often the API key is malformed or not valid. Check the "
                    "key in Settings.",
                    detail=f"HTTP 400: {r.text[:300]}",
                )
            if r.status_code == 401:
                raise LLMError(
                    "The Gemini API key was not accepted — it may be invalid "
                    "or expired. Check it in Settings.",
                    detail=f"HTTP 401: {r.text[:300]}",
                )
            if r.status_code == 403:
                raise LLMError(
                    "The Gemini API denied access — the API key may lack "
                    "permission for this model, or the project/region may be "
                    "restricted. Check the key in Google AI Studio.",
                    detail=f"HTTP 403: {r.text[:300]}",
                )
            if r.status_code == 404:
                raise LLMError(
                    f"The model '{self.model}' was not found — it may have been "
                    "renamed or retired. Update the model in Settings.",
                    detail=f"HTTP 404: {r.text[:300]}",
                )
            if r.status_code >= 300:
                raise LLMError(
                    "The AI service returned an unexpected error.",
                    detail=f"HTTP {r.status_code}: {r.text[:300]}",
                )
            return self._extract_text(r.json())

        raise last_error or LLMError("The AI service could not be reached.")

    @staticmethod
    def _extract_text(data):
        """Pull the response text out of a generateContent payload."""
        feedback = data.get("promptFeedback") or {}
        if feedback.get("blockReason"):
            raise LLMError(
                "The AI declined to answer this question. Try rephrasing it.",
                detail=f"prompt blocked: {feedback.get('blockReason')}",
            )
        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMError(
                "The AI returned an empty answer — please try again.",
                detail=f"no candidates in response: {json.dumps(data)[:300]}",
            )
        parts = (candidates[0].get("content") or {}).get("parts") or []
        text = "".join(p.get("text", "") for p in parts)
        if not text.strip():
            raise LLMError(
                "The AI returned an empty answer — please try again.",
                detail=f"finishReason: {candidates[0].get('finishReason')}",
            )
        return text

    async def health_check(self):
        """Cheap liveness probe: list one model. Never raises."""
        if not self.api_key:
            return {"ok": False, "error": "No Gemini API key configured", "models": []}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    f"{GEMINI_BASE_URL}/models",
                    params={"pageSize": 1},
                    headers={"x-goog-api-key": self.api_key},
                )
                r.raise_for_status()
            return {"ok": True, "models": [self.model]}
        except Exception as e:
            return {"ok": False, "error": str(e), "models": []}


def create_provider(cfg):
    """Build the configured AI provider from a config dict.

    Gemini is currently the only supported provider. To add another vendor
    later: implement an :class:`LLMProvider` subclass above and add a branch
    here keyed on ``cfg["provider"]``.
    """
    p = cfg.get("provider", "gemini")
    if p == "gemini":
        # The config carries the key encrypted at rest; it is decrypted only
        # here, at the point of use.
        return GeminiProvider(
            api_key=decrypt_api_key(cfg.get("api_keys", {}).get("gemini", "")),
            model=cfg.get("model", ""),
        )
    raise ValueError(
        f"Unknown provider: {p!r}. BoloDB currently supports only 'gemini'."
    )


class ProviderManager:
    """Lazily builds and caches the provider; rebuilt when config changes."""

    def __init__(self, cfg):
        self.cfg = cfg
        self._p = None

    def get(self):
        if not self._p:
            self._p = create_provider(self.cfg)
        return self._p

    def reconfigure(self, cfg):
        self.cfg = cfg
        self._p = None


# --------------------------------------------------------------------------
# Prompt building. Each block is a small pure function so tests can check the
# exact text the model sees and docs can point at one place per concept.
# --------------------------------------------------------------------------

# Dialect-specific reminders that fix the most common cross-dialect mistakes.
_DIALECT_HINTS = {
    "sqlite": "Dates: use date()/strftime(); string concat is ||; no ILIKE (use LIKE, it is case-insensitive for ASCII).",
    "postgresql": "Dates: use date_trunc()/interval arithmetic; ILIKE is available; quote mixed-case identifiers.",
    "mysql": "Dates: use DATE_FORMAT()/DATE_SUB(); identifiers quote with backticks; LIMIT syntax applies.",
    "mssql": "Use TOP (N) instead of LIMIT; dates via DATEADD()/DATEDIFF(); string concat is +.",
    "duckdb": "PostgreSQL-like syntax; date_trunc()/interval work; ILIKE is available.",
}


def _context_block(context):
    """Render the last two conversation turns so follow-up questions
    ("now only 2023") can be resolved against the previous query."""
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
    """Render user-confirmed business-term meanings. These are ground truth —
    the user explicitly told us what these words mean in THEIR database."""
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


def _examples_block(retrieved, max_examples):
    """Render previously-verified Q→SQL pairs similar to this question.
    Few-shot examples of the user's own verified answers are the single
    strongest accuracy signal we have."""
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
    schema_text, dialect, glossary, retrieved, max_examples, context
):
    """Assemble the full system prompt for SQL generation."""
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
):
    """Question (+ optional repair feedback) → ``{sql, restatement, assumptions}``.

    ``feedback`` is filled by the repair loop (backend/app/repair.py) when a
    previous attempt failed validation or execution; it describes exactly what
    was wrong so the model can correct itself.
    """
    if context is None:
        context = []
    system = build_sql_system_prompt(
        schema_text, dialect, glossary, retrieved, max_examples, context
    )
    user = question if not feedback else f"{question}\n\n{feedback}"
    result = parse_sql_output(
        await provider.complete(system, user, json_mode=True, schema=SQL_SCHEMA)
    )
    if not result["sql"]:
        # Retry once if the model returned nothing usable.
        result = parse_sql_output(
            await provider.complete(
                system + "\nReturn ONLY valid JSON.",
                user,
                json_mode=True,
                schema=SQL_SCHEMA,
            )
        )
    return result


async def explain_sql(provider, sql, dialect):
    """SQL → plain English. The 'reverse text-to-SQL' trust feature: lets a
    non-technical user sanity-check a query without reading SQL."""
    system = (
        f"You explain {dialect} SQL to non-technical business users.\n"
        "Describe what the query returns in 2-4 short plain sentences: which "
        "data it looks at, how it filters/groups, and how results are ordered "
        "or limited. No SQL keywords, no jargon.\n"
        'Reply ONLY with JSON: {"explanation":"..."}'
    )
    raw = await provider.complete(
        system, sql, json_mode=True, schema=EXPLAIN_SCHEMA, thinking_budget=0
    )
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return {"explanation": str(obj.get("explanation", "")).strip()}


async def generate_glossary(provider, schema_text):
    """Suggest the 3 most important business terms for this database (onboarding)."""
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
        thinking_budget=0,
    )
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return obj.get("glossary", [])


async def generate_starters(provider, schema_text, dialect):
    """Suggest 3 example questions with SQL for the user to verify (onboarding)."""
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
        thinking_budget=0,
    )
    obj = raw if isinstance(raw, dict) else parse_json(raw)
    return obj.get("starters", [])
