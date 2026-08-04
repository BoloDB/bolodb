"""The /api/health JWKS probe must be cheap, cached, and must not leak clients.

The container healthcheck polls this endpoint every 10-30s forever, so a probe
that opens a fresh connection pool per call is a slow leak in production.
"""

import pytest

from backend.app.controllers import system as sysmod


@pytest.fixture(autouse=True)
def reset_probe_state(monkeypatch):
    monkeypatch.setattr(sysmod, "_jwks_probe_cache", None)
    monkeypatch.setattr(sysmod, "_jwks_http_client", None)
    yield
    monkeypatch.setattr(sysmod, "_jwks_probe_cache", None)
    monkeypatch.setattr(sysmod, "_jwks_http_client", None)


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeClient:
    """Stands in for httpx.AsyncClient, counting requests and closures."""

    instances = []

    def __init__(self, *a, **kw):
        self.requests = 0
        self.is_closed = False
        self.status_code = 200
        self.raises = None
        FakeClient.instances.append(self)

    async def get(self, url):
        self.requests += 1
        if self.raises:
            raise self.raises
        return FakeResponse(self.status_code)

    async def aclose(self):
        self.is_closed = True


@pytest.fixture
def fake_httpx(monkeypatch):
    FakeClient.instances = []
    monkeypatch.setattr(sysmod.httpx, "AsyncClient", FakeClient)
    return FakeClient


@pytest.mark.asyncio
async def test_repeated_probes_reuse_one_client(fake_httpx):
    """Every call used to construct — and abandon — its own AsyncClient."""
    for _ in range(5):
        sysmod._jwks_probe_cache = None  # force a real probe each time
        await sysmod._probe_jwks("https://proj.supabase.co")

    assert len(fake_httpx.instances) == 1, "a client was created per probe"
    assert fake_httpx.instances[0].requests == 5


@pytest.mark.asyncio
async def test_result_is_cached_within_ttl(fake_httpx):
    first = await sysmod._probe_jwks("https://proj.supabase.co")
    for _ in range(9):
        await sysmod._probe_jwks("https://proj.supabase.co")

    assert first == "reachable"
    # Ten calls, one network request: the healthcheck no longer hammers Supabase.
    assert fake_httpx.instances[0].requests == 1


@pytest.mark.asyncio
async def test_cache_expires_after_ttl(fake_httpx, monkeypatch):
    clock = {"t": 1000.0}
    monkeypatch.setattr(sysmod.time, "monotonic", lambda: clock["t"])

    await sysmod._probe_jwks("https://proj.supabase.co")
    clock["t"] += sysmod._JWKS_PROBE_TTL_SECONDS + 1
    await sysmod._probe_jwks("https://proj.supabase.co")

    assert fake_httpx.instances[0].requests == 2


@pytest.mark.asyncio
async def test_cache_is_keyed_on_url(fake_httpx):
    await sysmod._probe_jwks("https://one.supabase.co")
    await sysmod._probe_jwks("https://two.supabase.co")
    assert fake_httpx.instances[0].requests == 2


@pytest.mark.asyncio
async def test_non_200_is_reported_and_cached(fake_httpx):
    await sysmod._probe_jwks("https://proj.supabase.co")  # creates the client
    client = fake_httpx.instances[0]
    client.status_code = 503
    sysmod._jwks_probe_cache = None

    assert (
        await sysmod._probe_jwks("https://proj.supabase.co") == "unexpected_status:503"
    )


@pytest.mark.asyncio
async def test_network_failure_is_reported_not_raised(fake_httpx):
    await sysmod._probe_jwks("https://proj.supabase.co")
    client = fake_httpx.instances[0]
    client.raises = ConnectionError("boom")
    sysmod._jwks_probe_cache = None

    # Health must degrade gracefully, never 500 because a third party is down.
    assert (
        await sysmod._probe_jwks("https://proj.supabase.co")
        == "unreachable:ConnectionError"
    )


@pytest.mark.asyncio
async def test_shutdown_closes_the_client(fake_httpx):
    await sysmod._probe_jwks("https://proj.supabase.co")
    client = fake_httpx.instances[0]
    assert not client.is_closed

    await sysmod.close_jwks_http_client()
    assert client.is_closed
    assert sysmod._jwks_http_client is None


@pytest.mark.asyncio
async def test_client_is_recreated_after_close(fake_httpx):
    await sysmod._probe_jwks("https://proj.supabase.co")
    await sysmod.close_jwks_http_client()
    await sysmod._probe_jwks("https://proj.supabase.co")

    assert len(fake_httpx.instances) == 2
    assert not fake_httpx.instances[1].is_closed
