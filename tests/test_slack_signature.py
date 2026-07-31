"""Tests for the Slack request signature check.

This is the only thing standing between the public internet and a handler that
runs an LLM call and a SQL query against a customer's database, so it gets
tested as the security boundary it is rather than as a helper.
"""

import hashlib
import hmac
import time

import pytest

from backend.app.routes.slack import _verify_slack_request

# Deliberately not a realistic-looking secret: a high-entropy hex string
# here trips the repo's gitleaks hook on every commit, and a fake
# credential that has to be allowlisted is worse than one that reads as
# fake. HMAC does not care what the key looks like.
SECRET = "test-slack-signing-secret"


def sign(body: bytes, timestamp: str, secret: str = SECRET) -> str:
    basestring = b"v0:" + timestamp.encode() + b":" + body
    return "v0=" + hmac.new(secret.encode(), basestring, hashlib.sha256).hexdigest()


@pytest.fixture(autouse=True)
def signing_secret(monkeypatch):
    monkeypatch.setenv("SLACK_SIGNING_SECRET", SECRET)


def test_a_correctly_signed_request_is_accepted():
    body = b"token=x&team_id=T1&text=how+many+orders"
    ts = str(int(time.time()))
    assert _verify_slack_request(body, ts, sign(body, ts)) is True


def test_a_tampered_body_is_rejected():
    """The signature covers the body, so editing it after signing must fail."""
    ts = str(int(time.time()))
    signature = sign(b"text=harmless", ts)
    assert _verify_slack_request(b"text=DROP+TABLE", ts, signature) is False


def test_a_signature_from_a_different_secret_is_rejected():
    body = b"text=x"
    ts = str(int(time.time()))
    assert _verify_slack_request(body, ts, sign(body, ts, "not-the-secret")) is False


@pytest.mark.parametrize("age", [301, 3600, 86400])
def test_a_replayed_request_is_rejected_once_outside_the_window(age):
    """A captured request stays perfectly signed forever; the timestamp is the
    only thing that stops it being replayed."""
    body = b"text=x"
    ts = str(int(time.time()) - age)
    assert _verify_slack_request(body, ts, sign(body, ts)) is False


def test_a_request_from_the_future_is_rejected():
    """The window is absolute, not one-sided — a clock-skewed forgery does not
    get to buy itself extra validity."""
    body = b"text=x"
    ts = str(int(time.time()) + 400)
    assert _verify_slack_request(body, ts, sign(body, ts)) is False


def test_a_request_just_inside_the_window_is_accepted():
    body = b"text=x"
    ts = str(int(time.time()) - 290)
    assert _verify_slack_request(body, ts, sign(body, ts)) is True


@pytest.mark.parametrize(
    "timestamp,signature",
    [
        ("", "v0=abc"),
        ("1700000000", ""),
        ("", ""),
    ],
)
def test_missing_headers_are_rejected(timestamp, signature):
    assert _verify_slack_request(b"text=x", timestamp, signature) is False


def test_a_non_numeric_timestamp_is_rejected_rather_than_raising():
    """int() on a header an attacker controls; the ValueError has to be caught
    or an unauthenticated caller gets a 500 for free."""
    assert _verify_slack_request(b"text=x", "not-a-number", "v0=abc") is False


def test_verification_fails_closed_when_no_secret_is_configured(monkeypatch):
    """A deployment that never set SLACK_SIGNING_SECRET must reject everything,
    not accept everything."""
    monkeypatch.delenv("SLACK_SIGNING_SECRET", raising=False)
    body = b"text=x"
    ts = str(int(time.time()))
    assert _verify_slack_request(body, ts, sign(body, ts)) is False


def test_a_non_utf8_body_is_rejected_rather_than_raising():
    """The basestring is built from bytes. Decoding the body to build it turned
    a malformed payload into an UnicodeDecodeError escaping as a 500 — a
    traceback generator anyone could reach without a valid signature."""
    body = b"text=\xff\xfe\x00binary"
    ts = str(int(time.time()))
    assert _verify_slack_request(body, ts, sign(body, ts)) is True
    assert _verify_slack_request(body, ts, "v0=" + "0" * 64) is False


def test_signature_comparison_does_not_short_circuit_on_length():
    """compare_digest handles unequal lengths without raising."""
    ts = str(int(time.time()))
    assert _verify_slack_request(b"text=x", ts, "v0=short") is False
