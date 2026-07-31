"""Tests for the Slack events endpoint.

Covers the request-level behaviour that sits in front of the handlers:
signature enforcement, Slack's own retry semantics, and payload dispatch.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.dependencies import (
    get_cfg,
    get_db,
    get_kb,
    get_providers,
    get_session_log,
)
from backend.app.routes import slack as slack_routes

# Deliberately not a realistic-looking secret: a high-entropy hex string
# here trips the repo's gitleaks hook on every commit, and a fake
# credential that has to be allowlisted is worse than one that reads as
# fake. HMAC does not care what the key looks like.
SECRET = "test-slack-signing-secret"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SECRET)
    application = FastAPI()
    application.include_router(slack_routes.router)
    for dep in (get_db, get_kb, get_cfg, get_providers, get_session_log):
        application.dependency_overrides[dep] = lambda: None
    return application


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def dispatched(monkeypatch):
    """Record every handler invocation so a test can assert none happened."""
    calls = []

    async def slash(payload, *a):
        calls.append(("slash", payload))
        return {"text": "ok"}

    async def interactive(payload, *a):
        calls.append(("interactive", payload))
        return {"text": "ok"}

    monkeypatch.setattr(slack_routes, "handle_slash_command", slash)
    monkeypatch.setattr(slack_routes, "handle_interactive_callback", interactive)
    return calls


def post(client, body: bytes, content_type: str, headers=None, sign=True):
    ts = str(int(time.time()))
    hdrs = {"content-type": content_type, "X-Slack-Request-Timestamp": ts}
    if sign:
        basestring = b"v0:" + ts.encode() + b":" + body
        hdrs["X-Slack-Signature"] = (
            "v0=" + hmac.new(SECRET.encode(), basestring, hashlib.sha256).hexdigest()
        )
    hdrs.update(headers or {})
    return client.post("/api/slack/events", content=body, headers=hdrs)


FORM = "application/x-www-form-urlencoded"
JSON = "application/json"


def slash_body(text="how many orders"):
    return urlencode(
        {"team_id": "T1", "text": text, "response_url": "https://x"}
    ).encode()


def action_body():
    payload = {"team": {"id": "T1"}, "actions": [{"action_id": "pick_connection"}]}
    return urlencode({"payload": json.dumps(payload)}).encode()


# --- authentication ---------------------------------------------------------


def test_an_unsigned_request_is_rejected(client, dispatched):
    res = post(client, slash_body(), FORM, sign=False)
    assert res.status_code == 401
    assert dispatched == []


def test_a_forged_signature_is_rejected(client, dispatched):
    res = post(
        client, slash_body(), FORM, headers={"X-Slack-Signature": "v0=" + "0" * 64}
    )
    assert res.status_code == 401
    assert dispatched == []


def test_a_signed_slash_command_reaches_the_handler(client, dispatched):
    res = post(client, slash_body(), FORM)
    assert res.status_code == 200
    assert [kind for kind, _ in dispatched] == ["slash"]
    assert dispatched[0][1]["text"] == "how many orders"


def test_a_signed_interactive_payload_reaches_the_handler(client, dispatched):
    res = post(client, action_body(), FORM)
    assert res.status_code == 200
    assert [kind for kind, _ in dispatched] == ["interactive"]


# --- retries ----------------------------------------------------------------


@pytest.mark.parametrize("body", [slash_body(), action_body()])
def test_a_retry_is_acknowledged_without_running_the_query_again(
    client, dispatched, body
):
    """Slack re-delivers anything it considers failed or too slow. Every handler
    here starts an LLM call and a database query, so running a retry would bill
    and execute the whole pipeline twice and post a second answer over the
    first. The original attempt is still running and answers via response_url."""
    res = post(client, body, FORM, headers={"X-Slack-Retry-Num": "1"})
    assert res.status_code == 200
    assert dispatched == []


def test_a_first_delivery_is_not_mistaken_for_a_retry(client, dispatched):
    res = post(client, slash_body(), FORM, headers={"X-Slack-Retry-Num": ""})
    assert res.status_code == 200
    assert [kind for kind, _ in dispatched] == ["slash"]


def test_a_retried_url_verification_still_answers_the_challenge(client):
    """Exempt from the retry guard: answering has no side effects, and refusing
    would leave the app's event subscription unverifiable."""
    body = json.dumps({"type": "url_verification", "challenge": "c123"}).encode()
    res = post(client, body, JSON, headers={"X-Slack-Retry-Num": "2"})
    assert res.status_code == 200
    assert res.json() == {"challenge": "c123"}


# --- payload handling -------------------------------------------------------


def test_the_url_verification_challenge_is_echoed(client):
    body = json.dumps({"type": "url_verification", "challenge": "abc"}).encode()
    res = post(client, body, JSON)
    assert res.json() == {"challenge": "abc"}


def test_a_url_verification_without_a_challenge_is_a_400(client):
    body = json.dumps({"type": "url_verification"}).encode()
    assert post(client, body, JSON).status_code == 400


def test_an_unknown_event_type_is_acknowledged(client):
    body = json.dumps({"type": "event_callback"}).encode()
    res = post(client, body, JSON)
    assert res.status_code == 200


def test_a_malformed_interactive_payload_is_a_400(client, dispatched):
    body = urlencode({"payload": "{not json"}).encode()
    assert post(client, body, FORM).status_code == 400
    assert dispatched == []


def test_a_body_that_is_not_json_is_a_400(client):
    assert post(client, b"<xml/>", JSON).status_code == 400


def test_a_non_utf8_body_is_a_400_not_a_500(client, dispatched):
    """A signed but malformed body used to reach body.decode() and escape as an
    unhandled UnicodeDecodeError."""
    for content_type in (FORM, JSON):
        res = post(client, b"\xff\xfe\x00\x01", content_type)
        assert res.status_code == 400, content_type
    assert dispatched == []
