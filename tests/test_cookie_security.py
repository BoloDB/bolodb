"""Session cookies must default to HTTPS-only.

COOKIE_SECURE defaulted to false, so an operator who never set it shipped
session cookies in clear over HTTP — and never setting it is the common case,
because nothing about the app misbehaves when it is wrong.
"""

import pytest

from backend.app.secrets import get_cookie_secure


def test_unset_defaults_to_secure(monkeypatch):
    """The whole point: forgetting must not mean cookies on the wire in clear."""
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    assert get_cookie_secure() is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE"])
def test_plain_http_deployments_can_still_opt_out(monkeypatch, value):
    monkeypatch.setenv("COOKIE_SECURE", value)
    assert get_cookie_secure() is False


@pytest.mark.parametrize("value", ["true", "True", "1", "yes", "", "typo"])
def test_anything_that_is_not_false_stays_secure(monkeypatch, value):
    """Fails towards the safe side.

    A misspelled value should not quietly downgrade the cookie — the reader has
    to spell the insecure option correctly to get it.
    """
    monkeypatch.setenv("COOKIE_SECURE", value)
    assert get_cookie_secure() is True
