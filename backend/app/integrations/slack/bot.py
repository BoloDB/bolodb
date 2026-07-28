import asyncio
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

CONNECTION_PREFIX_RE = re.compile(r"^(\w[\w\s]*?):\s*(.*)", re.DOTALL)

SLACK_TIMEOUT = 10.0


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

    workspace_id = str(install.workspace_id)
    user_id = str(install.user_id)

    connections = await mdb.get_recent_connections(workspace_id)

    if conn_name:
        conn = _find_connection_by_alias(connections, conn_name)
        if not conn:
            available = (
                ", ".join(
                    c.get("alias_name") or c.get("db_id", "")[:8] for c in connections
                )
                or "None"
            )
            return {
                "response_type": "ephemeral",
                "text": f"I couldn't find a database connection named '{conn_name}'. Available connections: {available}",
            }

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

    workspace_id = str(install.workspace_id)
    user_id = str(install.user_id)

    connections = await mdb.get_recent_connections(workspace_id)
    conn_name = None
    for c in connections:
        if c.get("db_id") == db_id:
            conn_name = c.get("alias_name") or db_id[:8]
            break

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
        "text": f"🤔 Querying {conn_name or db_id[:8]}...",
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
    asyncio.ensure_future(
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

    try:
        await ensure_connection(db, workspace_id, db_id)

        req = QueryReq(question=question)
        out = await ctrl.run_query(
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

        blocks = result_blocks(out, question, conn_name)
        body = {
            "response_type": "ephemeral",
            "replace_original": True,
            "blocks": blocks,
        }
    except Exception as e:
        log.exception("Slack query [%s] failed: %s", question, e)
        body = {
            "response_type": "ephemeral",
            "replace_original": True,
            "blocks": error_blocks(str(e), question),
        }

    async with httpx.AsyncClient(timeout=SLACK_TIMEOUT) as client:
        await client.post(response_url, json=body)
