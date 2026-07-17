# Post-Migration Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 15+ remaining issues from the OpenRouter migration: naming, error handling, config persistence, test coverage, frontend readiness, and documentation.

**Architecture:** Bite-sized independent fixes across the stack. Each task compiles/passes its own tests independently.

**Tech Stack:** Python (FastAPI, openai SDK), SvelteKit, pytest

## Global Constraints

- Model ID must use namespaced form `deepseek/deepseek-v4-flash`  (for API calls); display text can use `DeepSeek V4 Flash`
- API key is always read from `OPENROUTER_API_KEY` env var, never persisted to disk

---

### Task 1: Fix MODEL constant + _redact_error_text regex + add timeout to AsyncOpenAI

**Files:**
- Modify: `backend/app/llm.py:16,21,250,327`

**Interfaces:**
- Consumes: `MODEL` constant, `_redact_error_text`, `OpenRouterProvider.__init__`, `create_provider`
- Produces: Updated constant, regex, timeout, and error type

- [ ] **Step 1: Update MODEL to namespaced OpenRouter ID**

In `backend/app/llm.py:16`, change:
```python
MODEL = "deepseek-v4-flash"
```
to:
```python
MODEL = "deepseek/deepseek-v4-flash"
```

- [ ] **Step 2: Update _redact_error_text regex to match OpenRouter keys**

In `backend/app/llm.py:21`, change:
```python
s = re.sub(r"sk-[A-Za-z0-9]{10,}", "[REDACTED_KEY]", s)
```
to:
```python
s = re.sub(r"sk-or-v1-[A-Za-z0-9]+", "[REDACTED_KEY]", s)
s = re.sub(r"sk-[A-Za-z0-9]{10,}", "[REDACTED_KEY]", s)
```
This matches both `sk-or-v1-...` OpenRouter keys and legacy `sk-...` keys.

- [ ] **Step 3: Add timeout to AsyncOpenAI constructor**

In `backend/app/llm.py:249-253`, change:
```python
self._client = openai.AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
    max_retries=2,
)
```
to:
```python
self._client = openai.AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
    max_retries=2,
    timeout=30.0,
)
```

- [ ] **Step 4: Change ValueError to LLMError in create_provider**

In `backend/app/llm.py:324-331`, change:
```python
def create_provider(cfg, user_id=None):
    key = cfg.get("openrouter_key", "")
    if not key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set. "
            "Set it in the environment or config to use AI features."
        )
    return OpenRouterProvider(api_key=key)
```
to:
```python
def create_provider(cfg, user_id=None):
    key = cfg.get("openrouter_key", "")
    if not key:
        raise LLMError(
            "OpenRouter API key is not configured. "
            "Set OPENROUTER_API_KEY in the server environment.",
            detail="empty api_key in create_provider",
        )
    return OpenRouterProvider(api_key=key)
```

- [ ] **Step 5: Update test assertions for new MODEL name and LLMError**

In `tests/test_openrouter.py:48`, change:
```python
assert kwargs["model"] == "deepseek-v4-flash"
```
to:
```python
assert kwargs["model"] == "deepseek/deepseek-v4-flash"
```

In `tests/test_openrouter.py:146`, change:
```python
assert p.model == "deepseek-v4-flash"
```
to:
```python
assert p.model == "deepseek/deepseek-v4-flash"
```

In `tests/test_openrouter.py:149-152`, change:
```python
def test_create_provider_rejects_missing_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        create_provider({"openrouter_key": ""}, "user-1")
```
to:
```python
def test_create_provider_rejects_missing_key():
    with pytest.raises(LLMError, match="OpenRouter API key"):
        create_provider({"openrouter_key": ""}, "user-1")
```

- [ ] **Step 6: Add schema-body assertion in test_complete_passes_json_schema**

In `tests/test_openrouter.py:76-78`, after the existing assertions, add:
```python
    assert inner == SQL_SCHEMA["schema"]
```

- [ ] **Step 7: Run tests**

Run: `pytest tests/test_openrouter.py -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/llm.py tests/test_openrouter.py
git commit -m "fix: namespaced model ID, OpenRouter key redaction, timeout, and LLMError"
```

---

### Task 2: Fix {dialect} interpolation and add English instruction to all prompts

**Files:**
- Modify: `backend/app/llm.py:490,595,607,638,655`

**Interfaces:**
- Consumes: `build_sql_system_prompt`, `explain_sql`, `suggest_catalog`, `generate_glossary`, `generate_starters`
- Produces: Consistently English-instructed system prompts

- [ ] **Step 1: Fix {dialect} interpolation**

In `backend/app/llm.py:489-491`, change:
```python
    return (
        f"Answer in English\n"
        "You are an expert {dialect} analyst. Convert the user's question into "
```
to:
```python
    return (
        "Answer in English\n"
        f"You are an expert {dialect} analyst. Convert the user's question into "
```

- [ ] **Step 2: Add "Answer in English" to explain_sql prompt**

In `backend/app/llm.py:593-600`, change:
```python
    system = (
        f"You explain {dialect} SQL to non-technical business users.\n"
```
to:
```python
    system = (
        "Answer in English\n"
        f"You explain {dialect} SQL to non-technical business users.\n"
```

- [ ] **Step 3: Add "Answer in English" to suggest_catalog prompt**

In `backend/app/llm.py:607-621`, change:
```python
    system = (
        "You are a data analyst documenting a database for non-technical users.\n"
```
to:
```python
    system = (
        "Answer in English\n"
        "You are a data analyst documenting a database for non-technical users.\n"
```

- [ ] **Step 4: Add "Answer in English" to generate_glossary prompt**

In `backend/app/llm.py:638-643`, change:
```python
    system = (
        f"You are a database analyst.\n{schema_text}\n\n"
```
to:
```python
    system = (
        "Answer in English\n"
        f"You are a database analyst.\n{schema_text}\n\n"
```

- [ ] **Step 5: Add "Answer in English" to generate_starters prompt**

In `backend/app/llm.py:655-660`, change:
```python
    system = (
        f"You are a database analyst. {dialect} database.\n{schema_text}\n\n"
```
to:
```python
    system = (
        "Answer in English\n"
        f"You are a database analyst. {dialect} database.\n{schema_text}\n\n"
```

- [ ] **Step 6: Run tests**

Run: `pytest tests/test_openrouter.py -v`
Expected: All tests pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/llm.py
git commit -m "fix: interpolate dialect and add English instruction to all AI prompts"
```

---

### Task 3: Fix config migration to persist sanitized config + update_config handler

**Files:**
- Modify: `backend/app/config.py:55-63`, `backend/app/controllers/system.py:66-69`, `backend/app/models/api.py:4-5`
- Test: `tests/test_config.py:56-59`

**Interfaces:**
- Consumes: `load_config`, `save_config`, `update_config`, `ConfigUpdate`
- Produces: Sanitized config persisted to disk, last_db_url wired from request

- [ ] **Step 1: Persist sanitized config after legacy field cleanup**

In `backend/app/config.py:55-63`, change:
```python
    # Strip legacy fields that no longer apply
    d.pop("provider", None)
    d.pop("model", None)
    d.pop("api_keys", None)

    cfg = {**default_config(), **d}
    # API key is always read fresh from env, never from disk
    cfg["openrouter_key"] = os.environ.get("OPENROUTER_API_KEY", "")
    return cfg
```
to:
```python
    # Strip legacy fields that no longer apply
    changed = False
    for key in ("provider", "model", "api_keys"):
        if key in d:
            d.pop(key)
            changed = True

    cfg = {**default_config(), **d}
    # API key is always read fresh from env, never from disk
    cfg["openrouter_key"] = os.environ.get("OPENROUTER_API_KEY", "")

    # Persist sanitized config if legacy fields were removed
    if changed:
        save_config(cfg)

    return cfg
```

- [ ] **Step 2: Wire last_db_url from request data in update_config**

In `backend/app/controllers/system.py:66-69`, change:
```python
async def update_config(user_id, cfg, providers, req_data):
    """Update AI settings. The only settable field is last_db_url."""
    cfgmod.save_config(cfg)
    return {"config": cfgmod.public_config(cfg)}
```
to:
```python
async def update_config(user_id, cfg, providers, req_data):
    """Update AI settings. The only settable field is last_db_url."""
    if req_data.last_db_url is not None:
        cfg["last_db_url"] = req_data.last_db_url
    cfgmod.save_config(cfg)
    return {"config": cfgmod.public_config(cfg)}
```

- [ ] **Step 3: Add last_db_url to ConfigUpdate**

In `backend/app/models/api.py:4-5`, change:
```python
class ConfigUpdate(BaseModel):
    pass
```
to:
```python
class ConfigUpdate(BaseModel):
    last_db_url: str | None = None
```

- [ ] **Step 4: Update test_save_config_writes_plain_dict to verify key exclusion**

In `tests/test_config.py:56-59`, change:
```python
def test_save_config_writes_plain_dict(tmp_path):
    with _paths(tmp_path) as config_dir:
        save_config({"test": "data"})
        assert json.loads((config_dir / "config.json").read_text()) == {"test": "data"}
```
to:
```python
def test_save_config_writes_plain_dict(tmp_path):
    with _paths(tmp_path) as config_dir:
        save_config({"openrouter_key": "sk-or-v1-secret", "last_db_url": "sqlite:///test.db"})
        saved = json.loads((config_dir / "config.json").read_text())
        assert "openrouter_key" not in saved
        assert saved["last_db_url"] == "sqlite:///test.db"
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_config.py tests/test_openrouter.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/config.py backend/app/controllers/system.py backend/app/models/api.py tests/test_config.py
git commit -m "fix: persist sanitized config, wire last_db_url, tighten ConfigUpdate"
```

---

### Task 4: Update requirements.txt + docker-compose.yml

**Files:**
- Modify: `backend/requirements.txt:20`, `docker-compose.yml:25`

- [ ] **Step 1: Bump openai minimum version**

In `backend/requirements.txt:20`, change:
```
openai>=1.0.0
```
to:
```
openai>=1.40.0
```

- [ ] **Step 2: Make OpenRouter key required in docker-compose**

In `docker-compose.yml:25`, change:
```yaml
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
```
to:
```yaml
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY:?OPENROUTER_API_KEY must be set}
```

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt docker-compose.yml
git commit -m "fix: bump openai to >=1.40.0, require OPENROUTER_API_KEY in compose"
```

---

### Task 5: Un-track generated .svelte-kit-root-owned files + fix .gitignore

**Files:**
- Modify: `frontend/.gitignore:24`
- Git: Remove tracked generated files from index

- [ ] **Step 1: Fix gitignore pattern**

In `frontend/.gitignore:24`, change:
```
frontend/.svelte-kit-root-owned/
```
to:
```
/.svelte-kit-root-owned/
```

- [ ] **Step 2: Remove tracked generated files from index**

Run:

- [ ] **Step 3: Commit**

```bash
git add frontend/.gitignore
git commit -m "fix: correct .gitignore pattern, un-track generated .svelte-kit-root-owned files"
```

---

### Task 6: Fix doc references (docs + plans)

**Files:**
- Modify: `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md` (lines 211, 568, 979-981, 1013-1015, 1591-1639, 1660-1668, 1714-1717)
- Modify: `docs/superpowers/specs/2026-07-17-openrouter-migration-design.md` (line 76)
- Modify: `.env.example` (line 13)
- Modify: `docs/03-the-ai-layer-openrouter.md` (lines 3, 21)

- [ ] **Step 1: Fix model references in docs to use namespaced ID**

In `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:211`, change `MODEL = "deepseek-v4-flash"` to `MODEL = "deepseek/deepseek-v4-flash"`.

In `docs/superpowers/specs/2026-07-17-openrouter-migration-design.md:76`, change `"AI: OpenRouter (openai/gpt-4o)"` to `"AI: OpenRouter (DeepSeek V4 Flash)"`.

In `.env.example:13`, change `deepseek-v4-flash` to `DeepSeek V4 Flash` (display label only).

In `docs/03-the-ai-layer-openrouter.md:3`, change `BoloDB uses OpenRouter (\`deepseek-v4-flash\`)` to `BoloDB uses OpenRouter (\`DeepSeek V4 Flash\`)` (display label).

In `docs/03-the-ai-layer-openrouter.md:21`, change `Uses \`deepseek-v4-flash\` with` to `Uses \`deepseek/deepseek-v4-flash\` with` (API-facing reference).

In `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:568`, change `OpenRouter/gpt-4o doesn't support` to `OpenRouter/DeepSeek V4 Flash doesn't support`.

In `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:1014`, change `OpenRouter/gpt-4o` to `OpenRouter/DeepSeek V4 Flash`.

Update sidebar/dashboard plan references at `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:1591-1639` - the actual code was already fixed (no model labels), so just update the doc text to remove the gpt-4o references. Replace gpt-4o with DeepSeek V4 Flash in the plan steps.

In `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:1714-1717`, update to reflect that `OPENROUTER_MODEL` is not implemented.

- [ ] **Step 2: Add dotenv language identifier to fenced code blocks**

In `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:1660`, change:
````
```
# ── AI ──
...
```
````
to:
````
```dotenv
# ── AI ──
...
```
````

Do the same for the replacement block at line 1668.

- [ ] **Step 3: Fix httpx.AsyncClient context manager**

In `docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md:979-981`, change:
```python
            import httpx
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            resp = await httpx.AsyncClient(timeout=5).get(jwks_url)
```
to:
```python
            import httpx
            jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(jwks_url)
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-07-17-openrouter-migration-plan.md docs/superpowers/specs/2026-07-17-openrouter-migration-design.md .env.example docs/03-the-ai-layer-openrouter.md
git commit -m "docs: fix model references, add dotenv identifiers, fix httpx lifecycle"
```

---

### Task 7: Add openrouter_ready to backend state and frontend

**Files:**
- Modify: `backend/app/controllers/system.py:14-29`
- Modify: `frontend/src/lib/appState.svelte.ts:39-59`
- Modify: `frontend/src/lib/components/ConnectScreen.svelte:322-348`
- Modify: `frontend/src/lib/components/AskScreen.svelte:658-662`

- [ ] **Step 1: Add openrouter_ready to state response**

In `backend/app/controllers/system.py:15`, after `s = {"connected": db.connected(user_id), "config": cfgmod.public_config(cfg)}`, add:
```python
    s["openrouter_ready"] = bool(os.environ.get("OPENROUTER_API_KEY"))
```

And add `import os` at the top if not already present (it is at line 1).

- [ ] **Step 2: Consume openrouter_ready in appState**

In `frontend/src/lib/appState.svelte.ts`, add after the existing state fields (around line 15):
```typescript
  openrouterReady = $state(false);
```

In the `init` method, after `const s = await apiCall("/api/state");` (around line 41), add:
```typescript
        this.openrouterReady = s.openrouter_ready ?? false;
```

- [ ] **Step 3: Conditionally show AI readiness in ConnectScreen**

In `frontend/src/lib/components/ConnectScreen.svelte:322-348`, the current "AI ready" block:
```html
    <!-- AI info -->
    <div ...>
      ...
      AI ready. Only your
      <b>database structure and your question</b> are sent — never your actual data.
    </div>
```
Change to conditionally show AI readiness based on openrouter_ready:
```html
    <!-- AI info -->
    <div ...>
      ...
      {#if appState.openrouterReady}
        AI ready. Only your
        <b>database structure and your question</b> are sent — never your actual data.
      {:else}
        AI not yet ready — set <b>OPENROUTER_API_KEY</b> in the server environment.
      {/if}
    </div>
```

Add the import at the top of ConnectScreen.svelte:
```typescript
  import { appState } from '$lib/appState.svelte';
```

- [ ] **Step 4: Update AskScreen to use openrouter_ready**

In `frontend/src/lib/components/AskScreen.svelte`, look for any Settings import and replace the stale key recovery path with OpenRouter readiness handling.

Check around line 658-662 - the Settings panel is conditionally rendered when `settingsOpen` is true. If there's any Gemini-specific error handling, update it to use the shared OpenRouter readiness state.

- [ ] **Step 5: Commit**

```bash
git add backend/app/controllers/system.py frontend/src/lib/appState.svelte.ts frontend/src/lib/components/ConnectScreen.svelte frontend/src/lib/components/AskScreen.svelte
git commit -m "feat: add openrouter_ready state propagation to frontend"
```

---

### Task 8: Update AnswerCard model label

**Files:**
- Modify: `frontend/src/lib/components/AnswerCard.svelte` (around line 188)

Note: After verification, no model label exists in AnswerCard. If the user wants a model label added, add it to the confidence badge area.

- [ ] **Step 1: Check if model label is desired**

The finding noted the absence of any model label. If a display label is wanted, add it near the ConfidenceBadge at line 187-192:
```html
        <div style="flex-shrink:0;display:flex;align-items:center;gap:8px">
          <div style="font-size:11px;font-weight:600;color:var(--faint);padding:3px 9px;border-radius:99px;background:var(--surface-2);border:1px solid var(--border)">DeepSeek V4 Flash</div>
          <div data-tour="confidence">
            <ConfidenceBadge level={turn.confidence} reason={turn.reason} />
          </div>
        </div>
```

- [ ] **Step 2: Commit if changed**

```bash
git add frontend/src/lib/components/AnswerCard.svelte
git commit -m "fix: add model label to AnswerCard"
```
