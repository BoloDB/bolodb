# 3. The AI layer — Google Gemini

Every AI operation in BoloDB goes through **one file**:
`backend/app/llm.py`. If you want to know anything about what the AI is asked,
told, or paid for — that file is the single source of truth. Nothing else in
the backend talks to an AI service.

## The four AI operations

| Operation | Function in `llm.py` | When it runs | Thinking* |
|---|---|---|---|
| Question → SQL | `generate_sql()` | Every question you ask | dynamic (model decides) |
| SQL → plain English | `explain_sql()` | When you ask for an explanation (`POST /api/explain`) | off |
| Suggest business terms | `generate_glossary()` | Once, during onboarding | off |
| Suggest starter questions | `generate_starters()` | Once, during onboarding | off |

\* "Thinking" is Gemini's internal reasoning mode. It improves hard SQL
generation but costs extra output tokens, so BoloDB leaves it on (dynamic)
only for SQL generation and switches it off (`thinking_budget=0`) for the
three simpler tasks. See `GeminiProvider._build_body()`.

## Which model is used?

Configured in Settings, stored in `~/.bolodb/config.json`, defaults defined in
`backend/app/config.py`:

| Model | When to pick it |
|---|---|
| `gemini-2.5-flash-lite` | Cheapest and fastest. Fine for small, simple databases. |
| `gemini-2.5-flash` | **Default.** Best cost/accuracy balance for most databases. |
| `gemini-2.5-pro` | Most accurate. For large schemas and gnarly questions. |

The allowed list is `ALLOWED_MODELS` in `backend/app/config.py`; the Settings
screen (`frontend/src/lib/components/Settings.svelte`) mirrors it. The model
choice also changes how much schema the prompt may contain — see
`model_budget()` in `backend/app/schema_link.py`.

## The API key

- Get a free key at https://aistudio.google.com/apikey.
- Enter it during onboarding (`ConnectScreen.svelte`, step 1) or later in
  Settings. It is saved **locally only**, in `~/.bolodb/config.json`, and
  **encrypted at rest**: a per-install secret (`~/.bolodb/.secret`, generated
  once, owner-only file permissions) encrypts the key before it is written and
  decrypts it on load (`backend/app/config.py` → `save_config()` /
  `load_config()`). The frontend is never shown the key itself, only whether
  one is set (`public_config()`).
- Deployments can instead set the `GEMINI_API_KEY` environment variable —
  picked up in `load_config()`. A key saved in Settings wins over the
  environment variable.

## What exactly is sent to Google?

For SQL generation (the most frequent call), the prompt contains — assembled
in `build_sql_system_prompt()` in `llm.py`, in this order:

1. **Instructions** — write one read-only SELECT in the right dialect, use
   only the listed tables/columns, join via the shown foreign keys, etc.
2. **The trimmed schema** — only the tables schema linking selected
   (chapter 4): table names, column names, primary/foreign keys, up to a few
   *sample values* for short text columns (e.g. `status[completed,pending]`)
   and optionally one sample row per table.
3. **Your confirmed glossary terms** (`_glossary_block()`).
4. **Up to 5 previously verified Q→SQL examples** (`_examples_block()`).
5. **The last 2 conversation turns**, for follow-up questions
   (`_context_block()`).
6. **Your question** (plus, on repair attempts, the error to fix).

**Never sent:** the rows inside your tables (beyond the small sample values
above), credentials, or query results.

## How the call works (and fails) — `GeminiProvider`

`GeminiProvider.complete()` in `llm.py` does one POST to Google's
`generateContent` REST endpoint using plain `httpx` (no SDK dependency).
Details that matter:

- **Structured output.** We pass a JSON schema (`responseSchema`) so the
  model is *constrained* to reply in the exact shape we parse — no rambling,
  no markdown fences, fewer wasted tokens. The schemas are the constants
  `SQL_SCHEMA`, `GLOSSARY_SCHEMA`, `STARTERS_SCHEMA`, `EXPLAIN_SCHEMA` at the
  top of `llm.py`. Gemini's schema dialect is slightly different from
  standard JSON Schema, so `to_gemini_schema()` converts.
- **Low temperature (0.1).** SQL generation should be deterministic, not
  creative.
- **Retries.** Rate limits (HTTP 429), server errors (5xx) and network
  failures are retried up to 2 more times with 1s/2s backoff. Constants:
  `_RETRYABLE_STATUS`, `_MAX_ATTEMPTS`.
- **Errors carry two messages.** Anything unrecoverable raises `LLMError`,
  which has a `user_message` (safe to show in the UI, e.g. *"the API key may
  be invalid — check it in Settings"*) and a `detail` (the raw technical
  cause, written to the server log). The mapping from HTTP status → message
  is right there in `complete()`:

| What happened | HTTP | What the user sees |
|---|---|---|
| No key configured | — | "No Gemini API key is configured. Add one in Settings…" |
| Bad/expired key | 400/401/403 | "…the API key may be invalid or expired." |
| Model renamed/retired | 404 | "The model '…' was not found — update the model in Settings." |
| Rate limit / outage (after retries) | 429/5xx | "The AI service is busy right now — try again in a moment." |
| Safety block | 200 + blockReason | "The AI declined to answer this question. Try rephrasing it." |

- **Health check.** `GeminiProvider.health_check()` (used by `/api/health`)
  does a cheap models-list GET and never raises — so a status page can always
  render.

## Where the provider is created

- `create_provider(cfg)` in `llm.py` builds the provider from config.
- `ProviderManager` caches it and rebuilds it when Settings change
  (`reconfigure()` is called from `backend/app/controllers/system.py` →
  `update_config()`).

## Adding a second AI vendor later (the flexibility we kept)

The product decision today is: **users don't choose the AI — it's Gemini.**
But the code keeps the door open. To add another vendor later:

1. Write a class in `llm.py` implementing the two-method `LLMProvider`
   interface: `complete(system, user, json_mode, schema)` and
   `health_check()`.
2. Add a branch for it in `create_provider()`.
3. Add its name to the config/Settings surface
   (`backend/app/config.py`, `backend/app/controllers/system.py`,
   `frontend/src/lib/components/Settings.svelte`).

Nothing else changes — `generate_sql`, schema linking, repair, confidence are
all provider-agnostic.

## Tests to look at

- `tests/test_gemini.py` — request shape, structured output, retries, error
  taxonomy, health check (all with a fake HTTP client; no network).
- `tests/test_structured_output.py` — the JSON contract and tolerant parsing.
- `tests/test_llm.py` — the `parse_json` fence-stripping helper.
