"""Shared test fixtures.

Currently one job: keep the suite off the network. `_validate_db_url` resolves
a hostname before deciding whether it points somewhere internal, and the URLs
throughout these tests name hosts that do not exist. Left alone, every one of
them becomes a real DNS lookup — slow, and dependent on the resolver a CI
runner happens to have, including the ones that answer NXDOMAIN with a search
page's address.

Tests that are *about* resolution monkeypatch `_resolve_all` themselves; this
fixture is autouse, so overriding it inside a test simply replaces the stub.
"""

import pytest


@pytest.fixture(autouse=True)
def no_dns_in_tests(monkeypatch):
    """Make hostname resolution return nothing unless a test says otherwise."""
    monkeypatch.setattr(
        "backend.app.database._resolve_all", lambda hostname: [], raising=False
    )
