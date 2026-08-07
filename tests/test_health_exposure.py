"""What an unauthenticated caller may learn from the health endpoint.

/api/health was open to anyone and returned which secrets are configured, the
Supabase project URL and the CORS allowlist — a map of which auth paths are live
and which are unconfigured, for someone deciding where to push. Each call also
made an outbound HTTPS request to Supabase, so a stranger could make this server
talk to a third party on demand.
"""

import pytest

import backend.app.controllers.system as ctrl
from backend.app.routes.system import health_diagnostics

# Keys that describe how this deployment is configured, as opposed to whether
# it is currently able to serve.
OPERATOR_KEYS = {"env", "supabase_jwks"}


@pytest.mark.asyncio
async def test_public_health_says_only_whether_we_can_serve():
    result = await ctrl.get_health("connected")
    assert result["status"] == "ok"
    assert result["postgres"] == "connected"
    assert not OPERATOR_KEYS & result.keys(), result


@pytest.mark.asyncio
async def test_public_health_still_reports_a_bad_database():
    """The probe has to stay useful — a load balancer depends on this."""
    result = await ctrl.get_health("disconnected:OperationalError")
    assert result["status"] == "degraded"


@pytest.mark.asyncio
async def test_public_health_makes_no_outbound_call(monkeypatch):
    """No unauthenticated request may reach out to Supabase on our behalf."""

    async def _boom(_url):
        raise AssertionError("public health probed a third party")

    monkeypatch.setattr(ctrl, "_probe_jwks", _boom)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    await ctrl.get_health("connected")


@pytest.mark.asyncio
async def test_diagnostics_still_carries_the_operator_detail(monkeypatch):
    """Moving it must not mean losing it — operators still need this."""

    async def _reachable(_url):
        return "reachable"

    monkeypatch.setattr(ctrl, "_probe_jwks", _reachable)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    result = await ctrl.get_diagnostics("connected")
    assert OPERATOR_KEYS <= result.keys()
    assert result["supabase_jwks"] == "reachable"
    assert "DATABASE_URL" in result["env"]


def test_diagnostics_is_behind_the_admin_gate():
    """The dependency *is* the control, so assert the route actually carries it.

    Checked on the signature rather than by driving a request: the guard is
    declared, not written inline, and a refactor that dropped it would leave the
    handler working perfectly — just open again, which is the state this change
    exists to end.
    """
    import inspect

    from backend.app.routes.system import _require_admin

    param = inspect.signature(health_diagnostics).parameters["user_token"]
    assert param.default.dependency is _require_admin


def test_being_signed_in_is_not_enough_for_diagnostics():
    """Any stranger who signs up holds a valid session — that is not an operator."""
    import pytest as _pytest
    from fastapi import HTTPException

    from backend.app.routes.system import _require_admin

    with _pytest.raises(HTTPException) as exc:
        _require_admin({"user_id": "u", "role": "user"})
    assert exc.value.status_code == 403

    assert _require_admin({"user_id": "u", "role": "admin"})


def test_public_health_takes_no_dependencies():
    """The readiness probe must stay reachable — orchestrators cannot log in."""
    import inspect

    from backend.app.routes.system import health

    assert inspect.signature(health).parameters == {}
