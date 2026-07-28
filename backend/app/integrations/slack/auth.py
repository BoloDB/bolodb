"""Slack OAuth v2 helpers.

Builds the authorize URL and exchanges the OAuth ``code`` for a bot token using
Slack's ``oauth.v2.access`` endpoint. Uses httpx (already a dependency, same
pattern as ``services/email.py``). ``oauth.v2.access`` expects a form-encoded
body, not JSON.
"""

from urllib.parse import urlencode

import httpx

from backend.app.secrets import (
    get_slack_client_id,
    get_slack_client_secret,
    get_slack_redirect_uri,
)

AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
TOKEN_URL = "https://slack.com/api/oauth.v2.access"
TIMEOUT_SECONDS = 10.0

# Forward-looking: consent for the bot capabilities is captured now so a later
# phase (slash commands / mentions) does not require re-installation.
DEFAULT_SCOPES = "commands,chat:write,app_mentions:read"


def get_oauth_url(state: str, scopes: str = DEFAULT_SCOPES) -> str:
    """Build the Slack OAuth authorize URL the user's browser should open."""
    client_id = get_slack_client_id()
    redirect_uri = get_slack_redirect_uri()
    if not client_id:
        raise RuntimeError("Slack client ID is not configured")
    if not redirect_uri:
        raise RuntimeError("Slack redirect URI is not configured")
    params = {
        "client_id": client_id,
        "scope": scopes,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


async def handle_oauth_callback(code: str) -> dict:
    """Exchange an OAuth ``code`` for a bot token.

    Returns the parsed ``oauth.v2.access`` response, which includes
    ``access_token`` (the ``xoxb-`` bot token), ``team`` (``id``/``name``),
    ``bot_user_id`` and ``scope``. Raises ``ValueError`` if Slack reports failure.
    """
    client_secret = get_slack_client_secret()
    if not client_secret:
        raise RuntimeError("Slack client secret is not configured")
    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        r = await client.post(
            TOKEN_URL,
            data={
                "client_id": get_slack_client_id(),
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": get_slack_redirect_uri(),
            },
        )
        r.raise_for_status()
        data = r.json()

    if not data.get("ok"):
        raise ValueError(f"Slack OAuth failed: {data.get('error')}")
    return data
