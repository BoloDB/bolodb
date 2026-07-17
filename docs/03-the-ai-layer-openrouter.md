# AI Layer — OpenRouter

BoloDB uses OpenRouter (`DeepSeek V4 Flash`) for all AI operations:
- SQL generation (question → SQL)
- SQL explanation (SQL → plain English)
- Glossary suggestion (onboarding)
- Starter question generation (onboarding)
- Semantic catalog suggestion
- Two-stage schema linking (table shortlisting)

## Configuration

Set `OPENROUTER_API_KEY` in the environment. The key is shared across all
users — there is no per-user API key storage.

## Architecture

All AI operations funnel through `backend/app/llm.py`:

- `OpenRouterProvider` — wraps the OpenAI SDK pointed at
  `https://openrouter.ai/api/v1`. Uses `deepseek/deepseek-v4-flash` with
  `max_retries=2` and `temperature=0.1`.
- `create_provider()` — factory function, called at startup.
- `ProviderManager` — caches a single shared provider instance.

## Structured Output

All AI responses use OpenAI's `response_format: { type: "json_schema" }`
with `strict: true`. Schemas are defined as module-level constants in
`llm.py` with the `"name"` wrapper required by the API.
