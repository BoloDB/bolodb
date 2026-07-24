# 8. Troubleshooting — when something goes wrong

This chapter is organized by **symptom**. For each issue, it covers the root cause, where to check in the codebase, and how to resolve it.

---

## Part A — For Users

### "No OpenRouter API Key configured"
- **Cause**: The server is missing the `OPENROUTER_API_KEY` environment variable.
- **Fix**: Set `OPENROUTER_API_KEY` in your `.env` file or environment and restart the backend server.

### "Authentication Required / 401 Unauthorized"
- **Cause**: Your session JWT cookie has expired or is invalid.
- **Fix**: Log out and log back in at `/login`.

### "Workspace Access Denied / 403 Forbidden"
- **Cause**: You are attempting to perform an action (e.g., connect database, edit catalog) without the required role permission in the active workspace.
- **Fix**: Contact your workspace Owner or Admin to adjust your role in Workspace Settings (`/workspaces/[id]/settings`).

### "Connection Refused / Database Unreachable"
- **Cause**: Network connection to the target database failed, or SSRF protection blocked the host (`backend/app/database.py`).
- **Fix**: Ensure the database host is not loopback (`localhost`, `127.0.0.1`) when running inside Docker, and verify firewall rules allow traffic.

### "Could not form a query — try rephrasing"
- **Cause**: The AI attempted up to 3 repair loops but could not generate valid SQL for your schema.
- **Fix**: Rephrase the question using exact column or table names, or add missing business definitions to the Data Catalog (`/api/catalog`).

---

## Part B — For Developers and Maintainers

### 1. Database Connection Encryption Errors
- **Symptom**: `Fernet InvalidToken` or failure decrypting stored connection credentials.
- **Root Cause**: `RECENT_CONNECTIONS_KEY` env variable changed or is not set properly across deployments.
- **Fix**: Ensure `RECENT_CONNECTIONS_KEY` remains static in your production `.env` file (`backend/app/pgdatabase/connections.py`).

### 2. Rate Limiting Limits Triggered (`slowapi`)
- **Symptom**: HTTP 429 Too Many Requests response.
- **Root Cause**: Client exceeded endpoint rate limits.
- **Fix**: Inspect `backend/app/ratelimit.py`. Ensure proxy headers (`X-Forwarded-For`) are forwarded correctly by Nginx/Traefik so all users don't share a single IP limit.

### 3. OpenRouter API Errors & Taxonomy
- **Symptom**: `LLMError` in backend logs.
- **Code Reference**: `backend/app/llm.py` → `OpenRouterProvider`.
- **Fix**:
  - For `LLMError` (authentication issue): Verify `OPENROUTER_API_KEY` validity at https://openrouter.ai/keys.
  - For `LLMError` (context window / budget issue): Check `schema_link.py` budgets — table count budget may need adjustment.

### 4. Stale-Chunk Streaming Interruptions
- **Symptom**: Chat interface hangs or streaming stops abruptly during query generation.
- **Code Reference**: `frontend/src/lib/api.ts` → `streamApiCall()`.
- **Fix**: Verify Nginx reverse proxy buffer settings (`proxy_buffering off;`) to allow SSE chunks to pass through immediately without buffering.

### 5. Running the Backend Test Suite

```bash
pip install -r backend/requirements.txt
pytest tests -v
```

All unit tests use mock/fake OpenRouter providers and isolated database fixtures (`tests/test_openrouter.py`, `tests/test_query_pipeline.py`).
