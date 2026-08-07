"""Slack integration routes — OAuth install flow + events endpoint.

A workspace owner/admin starts the install via ``GET /api/slack/install`` (returns
the Slack authorize URL carrying a signed ``state``); Slack redirects the browser
to ``GET /api/slack/oauth/callback``, which verifies the state, exchanges the code
for a bot token, and persists the installation against the workspace.

The callback is a top-level browser redirect from Slack, so it cannot receive the
``X-Workspace-Id`` header that ``get_current_workspace`` relies on — the workspace
and user identity ride through the signed ``state`` (a short-lived JWT), which also
provides CSRF protection.

Events (slash commands, interactive callbacks) arrive at ``POST /api/slack/events``,
verified via Slack's HMAC-SHA256 signing secret.
"""

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qs

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select

import backend.app.pgdatabase as mdb
from backend.app import tokens
from backend.app.crypto import encrypt_secret
from backend.app.dependencies import (
    get_cfg,
    get_db,
    get_kb,
    get_providers,
    get_session_log,
    require_permission,
    workspace_has_permission,
)
from backend.app.models.workspace import WorkspaceMember
from backend.app.pgdatabase.engine import async_session
from backend.app.pgdatabase.serialization import _to_uuid
from backend.app.pgdatabase.slack import SlackTeamConflictError
from backend.app.integrations.slack.auth import get_oauth_url, handle_oauth_callback
from backend.app.integrations.slack.bot import (
    handle_interactive_callback,
    handle_slash_command,
)
from backend.app.integrations.slack.models import SlackInstallationResponse
from backend.app.secrets import (
    get_frontend_url,
    get_jwt_secret,
    get_slack_signing_secret,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/slack", tags=["slack"])

STATE_TTL_SECONDS = 600


def _frontend_base() -> str:
    return (get_frontend_url() or "").rstrip("/")


@router.get("/install")
async def slack_install(workspace=Depends(require_permission("connections.manage"))):
    """Return the Slack OAuth authorize URL for the frontend to open."""
    # Typed like every other token: this one is handed to Slack in a URL, so it
    # is the most exposed thing we sign, and it carries a user_id. Untyped, it
    # was a working session cookie for anyone who saw the redirect.
    state = jwt.encode(
        {
            "workspace_id": workspace["workspace_id"],
            "user_id": workspace["user_id"],
            tokens.TYPE_CLAIM: tokens.SLACK_OAUTH_STATE,
            "exp": int(time.time()) + STATE_TTL_SECONDS,
        },
        get_jwt_secret(),
        algorithm="HS256",
    )
    return {"url": get_oauth_url(state)}


@router.get("/oauth/callback")
async def slack_callback(code: str = "", state: str = "", error: str = ""):
    """Handle Slack's OAuth redirect: verify state, exchange code, persist install."""
    fe = _frontend_base()
    if error or not code or not state:
        return RedirectResponse(f"{fe}/profile?slack=error")

    try:
        payload = jwt.decode(state, get_jwt_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        log.warning("Slack OAuth callback with invalid or expired state")
        return RedirectResponse(f"{fe}/profile?slack=error")
    if not tokens.is_kind(payload, tokens.SLACK_OAUTH_STATE):
        # Any other token of ours would satisfy the membership re-check below, so
        # without this an access token would serve as a state and defeat the CSRF
        # protection the state exists to provide.
        log.warning("Slack OAuth callback with a state that is not an install state")
        return RedirectResponse(f"{fe}/profile?slack=error")

    # Re-validate the user is still a member of the workspace with the
    # required permission. The state may be up to 10 minutes old, during
    # which the user could have been removed or their role changed.
    ws = {
        "workspace_id": payload["workspace_id"],
        "user_id": payload["user_id"],
        "role": "",
    }
    async with async_session() as session:
        result = await session.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == _to_uuid(ws["workspace_id"]),
                WorkspaceMember.user_id == _to_uuid(ws["user_id"]),
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return RedirectResponse(f"{fe}/profile?slack=error")
        ws["role"] = member.role
    if not await workspace_has_permission(ws, "connections.manage"):
        return RedirectResponse(f"{fe}/profile?slack=error")

    try:
        data = await handle_oauth_callback(code)
        await mdb.save_installation(
            team_id=data["team"]["id"],
            team_name=data["team"]["name"],
            bot_token=encrypt_secret(data["access_token"]),
            bot_user_id=data["bot_user_id"],
            user_id=payload["user_id"],
            workspace_id=payload["workspace_id"],
            scopes=data.get("scope", ""),
        )
    except SlackTeamConflictError:
        return RedirectResponse(f"{fe}/profile?slack=conflict")
    except RuntimeError:
        return RedirectResponse(f"{fe}/profile?slack=config")
    except Exception:
        log.exception("Slack OAuth token exchange or persistence failed")
        return RedirectResponse(f"{fe}/profile?slack=error")

    return RedirectResponse(f"{fe}/profile?slack=connected")


@router.get("/installations")
async def slack_installations(
    workspace=Depends(require_permission("connections.view")),
):
    """List Slack installations for the workspace (never exposes bot_token)."""
    installs = await mdb.get_installations_by_workspace(workspace["workspace_id"])
    return {
        "installations": [
            SlackInstallationResponse(
                id=str(i.id),
                team_id=i.team_id,
                team_name=i.team_name,
                bot_user_id=i.bot_user_id,
                scopes=i.scopes,
                created_at=i.created_at,
            )
            for i in installs
        ]
    }


@router.delete("/installations/{team_id}")
async def slack_uninstall(
    team_id: str, workspace=Depends(require_permission("connections.manage"))
):
    """Remove a Slack installation, scoped to the current workspace."""
    deleted = await mdb.delete_installation_for_workspace(
        team_id, workspace["workspace_id"]
    )
    return {"ok": deleted}


# ── Events (slash commands + interactive callbacks) ─────────────────────


def _verify_slack_request(body: bytes, timestamp: str, signature: str) -> bool:
    """HMAC-SHA256 verification of an incoming Slack request.

    Returns ``True`` if the signature is valid and the timestamp is within
    5 minutes of now (replay protection).
    """
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
    except ValueError:
        return False

    secret = get_slack_signing_secret()
    if not secret:
        return False

    # The basestring is bytes all the way down. Decoding the body to build it
    # would raise UnicodeDecodeError on a non-UTF-8 payload — surfacing as a
    # 500 from a request that should simply have been rejected, and handing an
    # unauthenticated caller a way to provoke tracebacks.
    sig_basestring = b"v0:" + timestamp.encode() + b":" + body
    my_signature = (
        "v0=" + hmac.new(secret.encode(), sig_basestring, hashlib.sha256).hexdigest()
    )
    return hmac.compare_digest(my_signature, signature)


@router.post("/events")
async def slack_events(
    request: Request,
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
):
    """Receive Slack events: slash commands and interactive callbacks.

    Verifies every request via Slack's signing secret before dispatching
    to the bot handler.  Also handles Slack's ``url_verification`` challenge
    used during app configuration.
    """
    body = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_request(body, timestamp, signature):
        raise HTTPException(401, "Invalid Slack request signature")

    # Slack re-delivers a request it considers failed or too slow, marking the
    # redelivery with X-Slack-Retry-Num. Every handler below starts an LLM call
    # and a database query, so running a retry would bill and execute the whole
    # pipeline a second time and post a second answer over the first. The
    # original attempt is still running and will deliver via response_url, so
    # acknowledge and do nothing.
    retry_num = request.headers.get("X-Slack-Retry-Num", "")
    is_retry = bool(retry_num)
    if is_retry:
        log.info(
            "Ignoring Slack retry #%s (%s)",
            retry_num,
            request.headers.get("X-Slack-Retry-Reason", "unknown"),
        )

    content_type = request.headers.get("content-type", "")

    if "application/x-www-form-urlencoded" in content_type:
        try:
            form = parse_qs(body.decode())
        except UnicodeDecodeError:
            raise HTTPException(400, "Request body is not valid UTF-8")

        if "payload" in form:
            try:
                payload = json.loads(form["payload"][0])
            except (json.JSONDecodeError, IndexError):
                raise HTTPException(400, "Invalid form payload")
            if is_retry:
                return {}
            return await handle_interactive_callback(
                payload, db, kb, cfg, providers, session_log
            )
        else:
            payload = {k: v[0] for k, v in form.items()}
            if is_retry:
                return {}
            return await handle_slash_command(
                payload, db, kb, cfg, providers, session_log
            )

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON in request body")
    # url_verification is exempt from the retry guard: answering the challenge
    # has no side effects, and refusing a retried one would leave the app's
    # event subscription unverifiable.
    if data.get("type") == "url_verification":
        challenge = data.get("challenge")
        if not challenge:
            raise HTTPException(400, "Missing challenge in url_verification")
        return {"challenge": challenge}

    return {"text": "Unsupported event type"}
