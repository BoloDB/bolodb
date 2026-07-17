# OpenRouter Migration Design

**Date:** 2026-07-17
**Status:** Approved
**Context:** Replace Google Gemini with OpenRouter (`deepseek-v4-flash` hardcoded), shared API key via env var, no per-user API key entry or model selection.

## Goals

- Remove all Gemini integration
- Add OpenRouter as the sole AI provider
- Hardcode model to `deepseek-v4-flash` via OpenRouter (users cannot select)
- Strip all per-user API key storage and encryption
- Strip model selector and API key UI from Settings

## Backend Changes

### `backend/app/llm.py`

- Replace `GeminiProvider` class with `OpenRouterProvider`
- Remove `GEMINI_BASE_URL`, `DEFAULT_GEMINI_MODEL`, `_RETRYABLE_STATUS`, `_MAX_ATTEMPTS`
- Remove `to_gemini_schema()` function
- `OpenRouterProvider` uses `openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=...)`
- `complete()` wraps `client.chat.completions.create()`
- JSON mode uses `response_format: { type: "json_schema", json_schema: { name, strict: true, schema } }`
- Update `create_provider()` — single branch returning `OpenRouterProvider`
- Update existing schemas (`SQL_SCHEMA`, `GLOSSARY_SCHEMA`, etc.) to add `"additionalProperties": false` and explicit `"type"` on all properties for OpenAI strict mode compliance
- Add `"name"` wrapper to each schema

### `backend/app/config.py`

- Remove `ALLOWED_MODELS`, `DEFAULT_MODEL`, `DEFAULTS["provider"]`
- Remove `get_api_key()`, `set_api_key()`, `clear_api_key()`, `has_api_key()`
- Remove `encrypt_api_key()` / `decrypt_api_key()` (keep `encrypt_db_url()` / `decrypt_db_url()` for connection strings)
- Remove Fernet-based API key encryption path
- Read `cfg["openrouter_key"] = os.getenv("OPENROUTER_API_KEY")` at startup
- Simplify `public_config()` — no per-user key status returned
- Remove provider migration/coercion logic

### `backend/app/schema_link.py`

- `model_budget()` — hardcode single budget tier (20 tables, 2 samples, 5 examples)
- Remove model-name-based budget branching

### `backend/app/controllers/system.py`

- `update_config()` — remove provider setting and model validation
- Remove `ALLOWED_MODELS` check

### `backend/app/models/api.py`

- `ConfigUpdate` — remove `provider`, `api_key`, `clear_api_key` fields

### `backend/app/routes/system.py`

- Config endpoint: no longer accepts provider/api_key/model from request body

### `backend/app/dependencies.py`

- Simplify `get_providers()` — no per-user provider creation, returns single shared provider

## Frontend Changes

### `frontend/src/lib/data.ts`

- Remove `providers` array
- Remove `GEMINI_KEY_URL` constant

### `frontend/src/lib/appState.svelte.ts`

- Remove `modelName` state

### `frontend/src/lib/components/Settings.svelte`

- Remove `MODELS` array and `<select>` dropdown
- Remove API key section (input field, save/change/remove buttons, configured badge)
- Add read-only "AI: OpenRouter (DeepSeek V4 Flash)" info line
- Keep: connection management, user profile, theme if any

### `frontend/src/lib/types.ts`

- Remove provider/model-related types

## Configuration & Deploy

- `.env.example`: `GEMINI_API_KEY=` → `OPENROUTER_API_KEY=`
- `docker-compose.yml`: update env var passthrough

## Documentation

- `docs/03-the-ai-layer-gemini.md` → rewrite as `docs/03-the-ai-layer-openrouter.md`

## Tests

- `tests/test_gemini.py` → `tests/test_openrouter.py`, rewritten for OpenRouter
- `tests/test_config.py` — updated for simplified config
- `tests/test_structured_output.py` — updated schemas

## Files Modified (complete list)

1. `backend/app/llm.py`
2. `backend/app/config.py`
3. `backend/app/schema_link.py`
4. `backend/app/controllers/system.py`
5. `backend/app/models/api.py`
6. `backend/app/routes/system.py`
7. `backend/app/dependencies.py`
8. `frontend/src/lib/data.ts`
9. `frontend/src/lib/appState.svelte.ts`
10. `frontend/src/lib/components/Settings.svelte`
11. `frontend/src/lib/types.ts`
12. `.env.example`
13. `docker-compose.yml`
14. `docs/03-the-ai-layer-gemini.md`
15. `tests/test_gemini.py`
16. `tests/test_config.py`
17. `tests/test_structured_output.py`

## Non-Goals

- Do NOT add any other AI provider (not even as a fallback)
- Do NOT keep per-user API key storage
- Do NOT add model selection or override for end users
- Do NOT add the `openai` package if avoidable via `httpx` raw calls (but per approved approach, we will use the OpenAI SDK)
