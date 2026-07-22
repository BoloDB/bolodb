# 9. Cost optimisation — good answers without burning tokens

Design goal, in order: **(1) the user's experience is never compromised,
(2) every avoidable token is avoided.** It turns out these rarely conflict —
most of what makes prompts cheaper (less irrelevant schema, structured
output, verified examples) also makes answers *better*.

## Where AI cost comes from

OpenRouter bills per token, input and output separately. For BoloDB, a
question's cost ≈

```text
(prompt: instructions + schema + glossary + examples + context)   ← input tokens
+ (the model's reply: SQL + restatement + assumptions)            ← output tokens
+ (invisible "thinking" tokens, if enabled)                       ← output tokens
× (number of attempts, if self-repair fires)
```

Every mechanism below trims one of those factors. Each row names the code
that implements it.

## The mechanisms

| # | Mechanism | Effect | Code |
|---|---|---|---|
| 1 | **Schema linking** — only relevant tables are sent, not the whole database | Biggest single saving on input tokens; also *improves* accuracy | `backend/app/schema_link.py` → `link_relevant_tables()` ([chapter 4](04-schema-linking.md)) |
| 2 | **Compact schema rendering** — one dense line per table instead of CREATE TABLE dumps | ~3–5× fewer tokens per table | `schema_link.py` → `compact_schema()` |
| 3 | **Structured output** — the model is constrained to a JSON schema; it cannot ramble, apologise, or wrap answers in prose | Output tokens = exactly the fields we parse | `backend/app/llm.py` → `responseSchema` in `OpenRouterProvider._build_body()` |
| 4 | **Thinking off for simple tasks** — glossary, starters and Explain don't need reasoning tokens | Removes the invisible thinking cost on 3 of 4 operations | `llm.py` → `thinking_budget=0` call sites |
| 5 | **Thinking left dynamic for SQL generation** — the model spends reasoning only when the question is hard | Pay for reasoning only where it buys accuracy (deliberate: experience > cost) | `llm.py` → `generate_sql()` (no `thinking_budget` override) |
| 6 | **Output caps** — `maxOutputTokens: 4096`, temperature 0.1 | Bounds worst-case output cost | `llm.py` → `_build_body()` |
| 7 | **Bounded self-repair** — at most 3 attempts, 60-second budget | A stubborn failure can't loop forever | `backend/app/controllers/query.py` → `_MAX_ATTEMPTS`, `_MAX_SECONDS` |
| 8 | **Retry with backoff, never blindly** — only transient statuses retry; a bad API key fails once, immediately | No token/HTTP waste on hopeless calls | `llm.py` → `_RETRYABLE_STATUS`, `complete()` |
| 9 | **Verified-answer reuse** — similar past answers are injected as examples, so the model converges on attempt 1 instead of needing repairs | Fewer repair rounds over time; the system gets *cheaper as it's used* | `backend/app/knowledge.py` → `retrieve_similar()` |
| 10 | **Per-model budgets** — cheaper models get smaller prompts (fewer tables/samples/examples) | Cost scales with the model tier you chose | `schema_link.py` → `model_budget()` |
| 11 | **Schema introspection cache** — your database is profiled once per connection, not per question | No repeated DB scans; instant prompts | `backend/app/database.py` → `get_schema()` cache |
| 12 | **Two-stage linking pays for itself** — the shortlist pre-pass (big schemas only, 30+ tables) is a names-only prompt with thinking off; picking the right tables up-front avoids repair rounds that cost far more | One tiny call replaces 1–2 full retries | `llm.py` → `shortlist_tables()`, threshold in `controllers/query.py` |
| 13 | **Enrichment cap** — sample rows / known values are collected for at most 40 tables (largest first); structure is still collected for all | Bounded introspection cost on huge databases | `database.py` → `ENRICH_MAX` in `get_schema()` |

## The one knob you control: the model

In Settings (persisted via `backend/app/config.py`):

| Model | Relative cost | Guidance |
|---|---|---|
| `deepseek-v4-flash` | lowest | Small schema, straightforward questions, high volume |
| `deepseek-v4-flash` (default) | low | The right answer for almost everyone |
| `deepseek-v4-flash` | highest | Big schemas, complex analytical questions |

OpenRouter's API also has a **free tier** — for evaluation and light usage the
cost is simply zero. Current pricing/quotas: https://ai.google.dev/pricing.

## What we deliberately do NOT do

- **We don't cut schema below what the question needs.** FK parents and
  junction tables are always included even past the table budget
  (`_FK_EXTRA_SLOTS`) — a cheap prompt that produces a broken JOIN costs
  more after one repair round than the tokens it saved.
- **We don't disable thinking for SQL generation.** Hard questions benefit;
  dynamic thinking means simple questions barely spend any.
- **We don't retry non-transient errors.** An invalid key or a blocked
  prompt fails fast with a clear message ([chapter 3](03-the-ai-layer-openrouter.md)).

## Ideas for later (not implemented)

- **Context caching** for the schema block — OpenRouter can cache repeated
  prompt prefixes at a discount; worth it once per-database question volume
  is high. Would slot into `OpenRouterProvider._build_body()`.
- **Semantic retrieval** (embeddings) instead of word-overlap for verified
  answers — better example reuse at the same token cost. Would replace
  `_similarity()` in `knowledge.py`.

A [Spider](https://github.com/taoyds/spider)-based benchmark for measuring
linking recall and execution accuracy before shipping prompt changes now
exists — see `benchmarks/README.md`.
