# 8. Troubleshooting — when something goes wrong

This chapter is organised by **symptom**. For each: what it probably means,
where to look in the code, and how to fix it. The first section needs no
technical knowledge; the second is for whoever maintains the deployment.

---

## Part A — For users

### "No Gemini API key is configured…"

The AI has no key to work with.
**Fix:** open **Settings** (gear icon in the sidebar) → paste a key →
Save. Get a free key at https://aistudio.google.com/app/api-keys.

### "…the API key is malformed or not valid" / "…invalid or expired" / "…may lack permission"

The key exists but Google refused it. The message tells you which flavour:

- **"rejected the request as invalid"** (HTTP 400) — usually a typo or a
  truncated key. Re-copy it carefully.
- **"was not accepted — invalid or expired"** (HTTP 401) — the key was
  revoked or expired. Generate a fresh one.
- **"denied access — may lack permission"** (HTTP 403) — the key is real but
  restricted: the Generative Language API isn't enabled for its project, the
  key has API restrictions, or your region/Workspace blocks access. Check the
  key's settings in Google AI Studio.

**Fix:** generate a fresh key in Google AI Studio and re-enter it in
Settings. The moment a valid key is saved, everything works — no restart
needed (saving triggers `providers.reconfigure()` in
`backend/app/controllers/system.py`).

### "The AI service is busy right now — please try again in a moment."

Google's API returned a rate-limit or temporary server error, and BoloDB's
automatic retries (3 attempts with backoff) didn't get through.
**Fix:** wait a minute and re-ask. If it persists for hours, check Google's
status page or your quota in AI Studio (free-tier quotas are per-day).

### "Could not form a query - try rephrasing" / an answer with Low confidence and an error

The AI tried up to 3 times (including automatic self-repair) and still
couldn't produce SQL your database accepts.
**Fix:** rephrase with more specifics — name the thing you want counted or
summed the way it's called in your business. If a term keeps failing, add it
to the glossary during onboarding or verify a correct answer once — both
directly teach the system (see [chapter 6](06-learning-trust-and-confidence.md)).

### "no matching rows - the question may not match your data"

The query ran fine but found nothing. Often the filter is subtly off — e.g.
a date range with no data, or a category spelled differently in your data.
**Fix:** open the SQL toggle or hit Explain and check the filter values; ask
again naming an exact value you know exists.

### The answer is wrong, but confidently so

No validator can catch "runs fine, answers the wrong question". Your tools:
read the **restatement** and **assumptions**, hit **Explain**, and click
**"Something's wrong"** — that feedback is logged and keeps the wrong answer
out of the knowledge base.

### "Only read-only SELECT queries are allowed"

You (or the AI) tried something that would modify data. That's the safety
guard working as intended — BoloDB never writes to your database. Code:
`backend/app/database.py` → `_readonly_violation()`.

### Can't connect to the database

The connect screen translates the raw error into a friendly sentence
(`frontend/src/lib/data.ts` → `humanError()`): wrong password, unreachable
host, missing file, etc. If running in Docker and connecting to a database on
your own machine, note that `localhost` is automatically rewritten to reach
the host (`backend/app/database.py` → `connect()`).

---

## Part B — For developers / maintainers

### Golden rule: check the logs first

- Every LLM failure logs a `WARNING` with the technical detail (the
  user-facing message is intentionally vaguer). Search the backend log for
  `LLM error during run_query` (from `controllers/query.py`) — the `detail`
  field of the `LLMError` carries the HTTP status + response snippet from
  Google (`backend/app/llm.py` → `complete()`).
- Every question and its outcome is appended to
  `~/.bolodb/sessions/session-<timestamp>.jsonl` — question, SQL,
  confidence, error, feedback verdicts. This is your replay log.

### Diagnosing a bad answer, step by step

1. **Which tables did the AI see?** The `/api/query` response includes
   `tables_used`. If the right table isn't there, the problem is schema
   linking — see `link_relevant_tables()` scoring in
   `backend/app/schema_link.py`, and enable DEBUG logging to see per-table
   scores. Common cause: table/column names that share no words with how
   users talk → fix by adding glossary terms.
2. **What was the AI actually told?** The full prompt is assembled in
   `build_sql_system_prompt()` (`backend/app/llm.py`). Log or breakpoint
   there to inspect it.
3. **Did self-repair fire?** Check `attempts` and `repaired` in the
   response. `attempts: 3` + an `execution_error` means the model never
   converged — usually a schema-linking miss (step 1) or a dialect quirk
   (see `_DIALECT_HINTS` in `llm.py`).
4. **Was the SQL rejected before execution?** Validation errors ("Unknown
   column …") come from `backend/app/sqlvalidate.py`; read the conservative
   design note at the top of that file before "fixing" it.

### The schema looks stale (renamed/added columns not showing)

Schema introspection is cached per connection
(`backend/app/database.py` → `get_schema()`, `_schema_cache`).
Reconnecting the database refreshes it (or call `get_schema(user_id,
refresh=True)` where appropriate).

### Everything AI-related fails instantly with no network calls

`GeminiProvider.complete()` fails fast when `api_key` is empty — before any
HTTP. Check `GET /api/health`: it reports
`{"provider": {"name": "gemini", "ok": false, "error": "No Gemini API key configured"}}`
in that state. Key resolution order: value saved in Settings beats the
`GEMINI_API_KEY` env var (`backend/app/config.py` → `load_config()`).

### Google returned 404 for the model

Model names get retired. The allowed list lives in one place —
`ALLOWED_MODELS` in `backend/app/config.py` — and the Settings dropdown in
`frontend/src/lib/components/Settings.svelte` mirrors it. Update both when
Google renames models.

### The saved API key stopped working after files were moved/restored

The key in `config.json` is encrypted with the per-install secret in
`~/.bolodb/.secret` (`backend/app/config.py` → `_fernet()`). If `.secret` is
deleted or the config is copied to another machine without it, the stored key
can no longer be decrypted — Gemini will reject it as invalid.
**Fix:** re-enter the key in Settings (it gets re-encrypted with the current
secret). When backing up `~/.bolodb`, keep `config.json` and `.secret`
together.

### Old config from the multi-provider era

Config files written before the Gemini-only switch (provider `ollama` /
`claude` / `openai` / `groq`) are migrated silently on load —
`load_config()` coerces provider+model and drops old vendor keys. Covered by
`tests/test_config.py::test_load_config_migrates_old_provider_config`.

### Running the test suite

```bash
pip install -r backend/requirements.txt
pytest tests -q
```

All AI tests use a fake HTTP client (`tests/test_gemini.py`) — the suite
needs **no network and no API key**. If you touched the pipeline, the most
valuable file to keep green is `tests/test_query_pipeline.py`.

### Quick health checklist

| Check | Expect |
|---|---|
| `GET /api/health` | `provider.name == "gemini"`, `ok: true` when a valid key is set |
| `GET /api/state` | `config.api_keys_set.gemini == "set"`, connection info |
| `~/.bolodb/config.json` | `{"provider": "gemini", "model": "gemini-2.5-…", "api_keys": {"gemini": "…"}}` |
| Backend log | no repeated `Gemini transient HTTP …` warnings (would mean quota pressure) |
