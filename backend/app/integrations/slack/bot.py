import asyncio
import contextlib
import json
import logging
import re

import httpx

import backend.app.pgdatabase as mdb
from backend.app.integrations.slack.blocks import (
    connection_picker_blocks,
    error_blocks,
    loading_blocks,
    result_blocks,
)

log = logging.getLogger(__name__)

_PENDING_TASKS: set[asyncio.Task] = set()

# A Slack query is one LLM round trip plus one database query, and nothing in
# the request path bounds how many can be in flight: /ask returns immediately
# and the work continues in the background, so a workspace typing faster than
# the queries finish would otherwise pile up unboundedly. Queries past the cap
# wait their turn rather than being dropped — the user has already been told
# "Querying …", and a slow answer beats a silent one.
MAX_CONCURRENT_QUERIES = 8
_QUERY_SLOTS: asyncio.Semaphore | None = None

CONNECTION_PREFIX_RE = re.compile(r"^(\w[\w\s]*?):\s*(.*)", re.DOTALL)

SLACK_TIMEOUT = 10.0

# Slack gives a response_url 30 minutes and 5 uses. Nothing here should be
# holding one open for anywhere near that, but a query that hangs would keep a
# semaphore slot forever, so bound the whole thing well inside the window.
QUERY_TIMEOUT = 300.0


def parse_slash_command(text: str) -> tuple[str | None, str]:
    m = CONNECTION_PREFIX_RE.match(text.strip())
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return None, text.strip()


async def handle_slash_command(
    payload: dict, db, kb, cfg, providers, session_log
) -> dict:
    text = payload.get("text", "")
    team_id = payload.get("team_id")
    response_url = payload.get("response_url")

    conn_name, question = parse_slash_command(text)

    if not question:
        return {
            "response_type": "ephemeral",
            "text": "Please ask a question. Usage: `/ask [connection:] your question`",
        }

    install = await mdb.get_installation_by_team(team_id)
    if not install:
        return {
            "response_type": "ephemeral",
            "text": "BoloDB isn't connected to this Slack workspace yet. Ask a workspace admin to install it.",
        }

    if not response_url:
        return {
            "response_type": "ephemeral",
            "text": "Slack sent no response_url, so there is nowhere to deliver the answer.",
        }

    workspace_id = str(install.workspace_id)
    user_id = str(install.user_id)

    connections = await mdb.get_recent_connections(workspace_id)

    conn = None
    if conn_name:
        conn = _find_connection_by_alias(connections, conn_name)
        if not conn:
            conn_name = None
            question = text.strip()

    if conn:
        _run_query_and_respond(
            question,
            workspace_id,
            conn["db_id"],
            user_id,
            response_url,
            db,
            kb,
            cfg,
            providers,
            session_log,
            conn_name,
        )

        return {
            "response_type": "ephemeral",
            "text": f"🤔 Querying {conn_name}...",
            "blocks": loading_blocks(conn_name, question),
        }

    if not connections:
        return {
            "response_type": "ephemeral",
            "text": "No database connections found in this workspace. Add one in the BoloDB web UI first.",
        }

    return {
        "response_type": "ephemeral",
        "blocks": connection_picker_blocks(connections, question),
    }


async def handle_interactive_callback(
    payload: dict, db, kb, cfg, providers, session_log
) -> dict:
    actions = payload.get("actions", [])
    if not actions:
        return {"text": "No action found.", "response_type": "ephemeral"}

    action = actions[0]
    if action.get("action_id") != "pick_connection":
        return {"text": "Unknown action.", "response_type": "ephemeral"}

    try:
        data = json.loads(action.get("value", "{}"))
        db_id = data.get("db_id")
        question = data.get("q", "")
    except (json.JSONDecodeError, TypeError):
        return {"text": "Invalid action data.", "response_type": "ephemeral"}

    if not db_id or not question:
        return {"text": "Missing data.", "response_type": "ephemeral"}

    team_id = payload.get("team", {}).get("id")
    response_url = payload.get("response_url")

    install = await mdb.get_installation_by_team(team_id)
    if not install:
        return {
            "response_type": "ephemeral",
            "text": "BoloDB isn't connected to this workspace.",
        }

    if not response_url:
        return {
            "response_type": "ephemeral",
            "text": "Slack sent no response_url, so there is nowhere to deliver the answer.",
        }

    workspace_id = str(install.workspace_id)
    user_id = str(install.user_id)

    # The db_id arrives in the button's value, which is round-tripped through
    # Slack rather than held server-side. The signing secret is what makes it
    # trustworthy, so this is not the security boundary — but a stale button
    # from a connection that has since been deleted, or one clicked after the
    # installation moved workspaces, would otherwise reach run_query and come
    # back as a bare "No database connected". Check it here and say so.
    connections = await mdb.get_recent_connections(workspace_id)
    conn = next((c for c in connections if c.get("db_id") == db_id), None)
    if conn is None:
        return {
            "response_type": "ephemeral",
            "text": "That database is no longer available in this workspace. Run `/ask` again to pick from the current list.",
        }
    conn_name = conn.get("alias_name") or db_id[:8]

    _run_query_and_respond(
        question,
        workspace_id,
        db_id,
        user_id,
        response_url,
        db,
        kb,
        cfg,
        providers,
        session_log,
        conn_name,
    )

    return {
        "response_type": "ephemeral",
        "text": f"🤔 Querying {conn_name}...",
    }


def _find_connection_by_alias(connections: list[dict], alias: str) -> dict | None:
    alias_lower = alias.lower()
    for c in connections:
        ca = c.get("alias_name")
        if ca and ca.lower() == alias_lower:
            return c
    return None


def _run_query_and_respond(
    question: str,
    workspace_id: str,
    db_id: str,
    user_id: str,
    response_url: str,
    db,
    kb,
    cfg,
    providers,
    session_log,
    conn_name: str | None = None,
):
    task = asyncio.ensure_future(
        _execute_query(
            question,
            workspace_id,
            db_id,
            user_id,
            response_url,
            db,
            kb,
            cfg,
            providers,
            session_log,
            conn_name,
        )
    )
    # A strong reference until it finishes: the event loop only holds a weak
    # one, so a task nothing keeps can be garbage-collected mid-flight.
    _PENDING_TASKS.add(task)
    task.add_done_callback(_PENDING_TASKS.discard)


async def drain_pending_queries(timeout: float = 30.0) -> int:
    """Let in-flight Slack queries finish, or tell their users they will not.

    Called from the app's lifespan shutdown. Without it a redeploy drops every
    running query on the floor: the loop closes, the response_url is never
    posted to, and the user is left looking at "🤔 Querying …" forever with no
    indication anything went wrong.

    Returns the number of tasks that were still pending when called.
    """
    pending = list(_PENDING_TASKS)
    if not pending:
        return 0
    log.info("Waiting for %d in-flight Slack quer(ies) to finish", len(pending))
    _finished, still_running = await asyncio.wait(pending, timeout=timeout)
    for task in still_running:
        task.cancel()
    if still_running:
        # Wait again, briefly: each cancelled task catches the CancelledError
        # long enough to tell its user the query was abandoned, and that post
        # has to go out before the loop closes.
        await asyncio.wait(still_running, timeout=SLACK_TIMEOUT)
        log.warning(
            "Cancelled %d Slack quer(ies) still running at shutdown",
            len(still_running),
        )
    return len(pending)


def _query_slots() -> asyncio.Semaphore:
    """The concurrency limiter, bound to whichever loop is running.

    Created lazily rather than at import: a Semaphore latches onto the first
    loop that awaits it and refuses every other one, which under pytest — a
    fresh loop per test — turns into "bound to a different event loop".
    """
    global _QUERY_SLOTS
    loop = asyncio.get_running_loop()
    if _QUERY_SLOTS is None or getattr(_QUERY_SLOTS, "_bolodb_loop", None) is not loop:
        _QUERY_SLOTS = asyncio.Semaphore(MAX_CONCURRENT_QUERIES)
        _QUERY_SLOTS._bolodb_loop = loop
    return _QUERY_SLOTS


async def _execute_query(
    question: str,
    workspace_id: str,
    db_id: str,
    user_id: str,
    response_url: str,
    db,
    kb,
    cfg,
    providers,
    session_log,
    conn_name: str | None = None,
):
    from backend.app.controllers.database import ensure_connection
    import backend.app.controllers.query as ctrl
    from backend.app.models.api import QueryReq

    async def run():
        await ensure_connection(db, workspace_id, db_id)
        req = QueryReq(question=question)
        return await ctrl.run_query(
            workspace_id,
            db,
            kb,
            cfg,
            providers,
            session_log,
            req,
            db_id=db_id,
            user_id=user_id,
        )

    try:
        try:
            async with _query_slots():
                out = await asyncio.wait_for(run(), timeout=QUERY_TIMEOUT)
            body = {
                "response_type": "ephemeral",
                "replace_original": True,
                "blocks": result_blocks(out, question, conn_name),
            }
        except asyncio.TimeoutError:
            log.warning("Slack query [%s] exceeded %ss", question, QUERY_TIMEOUT)
            body = {
                "response_type": "ephemeral",
                "replace_original": True,
                "blocks": error_blocks(
                    "The query took too long and was stopped. Try narrowing the question.",
                    question,
                ),
            }
        except Exception as e:
            log.exception("Slack query [%s] failed: %s", question, e)
            body = {
                "response_type": "ephemeral",
                "replace_original": True,
                "blocks": error_blocks(
                    "An unexpected error occurred while running your query.", question
                ),
            }
    except asyncio.CancelledError:
        # Shutdown. Say so rather than leaving the user on "🤔 Querying …"
        # forever, then let the cancellation continue on its way.
        with contextlib.suppress(Exception):
            await _post_response(
                response_url,
                {
                    "response_type": "ephemeral",
                    "replace_original": True,
                    "blocks": error_blocks(
                        "BoloDB restarted before this query finished. Please ask again.",
                        question,
                    ),
                },
            )
        raise

    try:
        await _post_response(response_url, body)
    except Exception:
        log.exception("Failed to send Slack callback response for query [%s]", question)


async def _post_response(response_url: str, body: dict) -> None:
    async with httpx.AsyncClient(timeout=SLACK_TIMEOUT) as client:
        await client.post(response_url, json=body)
