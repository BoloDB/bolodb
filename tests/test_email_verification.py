"""Tests for the MyEmailVerifier signup gate (backend/app/services/email_verification.py).

Covers the allow/deny decision for each verification status, the fail-open
behaviour when the service is unconfigured or unreachable, and the catch-all
status labelling (regression guard for operator-precedence in the allow branch).
"""

import pytest

import backend.app.services.email_verification as ev


class _FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self._data


class _FakeClient:
    def __init__(self, data):
        self._data = data

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url):
        return _FakeResp(self._data)


def _patch_service(monkeypatch, data):
    """Configure an API key and stub the HTTP client to return `data`."""
    monkeypatch.setenv("MYEMAILVERIFIER_API_KEY", "test-key")
    monkeypatch.setattr(ev.httpx, "AsyncClient", lambda *a, **k: _FakeClient(data))


@pytest.mark.asyncio
async def test_skipped_when_unconfigured(monkeypatch):
    monkeypatch.delenv("MYEMAILVERIFIER_API_KEY", raising=False)
    outcome = await ev.verify_email("user@example.com")
    assert outcome.allowed is True
    assert outcome.skipped is True


@pytest.mark.asyncio
async def test_disposable_blocked(monkeypatch):
    _patch_service(monkeypatch, {"Status": "Valid", "Disposable_Domain": "true"})
    outcome = await ev.verify_email("user@mailinator.com")
    assert outcome.allowed is False
    assert outcome.disposable is True


@pytest.mark.asyncio
async def test_invalid_blocked(monkeypatch):
    _patch_service(monkeypatch, {"Status": "Invalid", "Diagnosis": "no such mailbox"})
    outcome = await ev.verify_email("nope@example.com")
    assert outcome.allowed is False
    assert outcome.reason == "no such mailbox"


@pytest.mark.asyncio
async def test_unknown_blocked(monkeypatch):
    _patch_service(monkeypatch, {"Status": "Unknown"})
    outcome = await ev.verify_email("maybe@example.com")
    assert outcome.allowed is False


@pytest.mark.asyncio
async def test_valid_allowed(monkeypatch):
    _patch_service(monkeypatch, {"Status": "Valid"})
    outcome = await ev.verify_email("real@example.com")
    assert outcome.allowed is True
    assert outcome.status == "valid"


@pytest.mark.asyncio
async def test_catch_all_status_allowed(monkeypatch):
    _patch_service(monkeypatch, {"Status": "Catch_All"})
    outcome = await ev.verify_email("info@catchall.com")
    assert outcome.allowed is True
    assert outcome.status == "catch_all"


@pytest.mark.asyncio
async def test_catch_all_flag_without_status_labels_catch_all(monkeypatch):
    # Regression: `status or "catch_all" if catch_all else "valid"` previously
    # parsed as `(status or "catch_all") if catch_all else "valid"`, mislabelling
    # a flag-only catch-all as "valid".
    _patch_service(monkeypatch, {"Status": "", "catch_all": "true"})
    outcome = await ev.verify_email("info@catchall.com")
    assert outcome.allowed is True
    assert outcome.catch_all is True
    assert outcome.status == "catch_all"


@pytest.mark.asyncio
async def test_unrecognized_status_blocked(monkeypatch):
    _patch_service(monkeypatch, {"Status": "something-weird"})
    outcome = await ev.verify_email("odd@example.com")
    assert outcome.allowed is False


@pytest.mark.asyncio
async def test_service_error_fails_open(monkeypatch):
    import httpx

    monkeypatch.setenv("MYEMAILVERIFIER_API_KEY", "test-key")

    class _BoomClient(_FakeClient):
        async def get(self, url):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(ev.httpx, "AsyncClient", lambda *a, **k: _BoomClient(None))
    outcome = await ev.verify_email("user@example.com")
    assert outcome.allowed is True
    assert outcome.skipped is True


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("YES", True),
        ("1", True),
        ("false", False),
        ("", False),
        (None, False),
    ],
)
def test_to_bool(value, expected):
    assert ev._to_bool(value) is expected
