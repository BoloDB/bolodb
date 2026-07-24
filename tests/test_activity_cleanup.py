"""Tests for the activity-log retention job (``delete_old_activity`` and the
``activity_cleanup_loop`` that drives it from the app lifespan).
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

import backend.app.controllers.activity as activity


def _patch_session(monkeypatch, session):
    factory = Mock()
    factory.return_value = session
    session.__aenter__.return_value = session
    monkeypatch.setattr(activity, "async_session", factory)
    return factory


def _session_with_rowcount(monkeypatch, rowcount):
    session = AsyncMock()
    result = Mock()
    result.rowcount = rowcount
    session.execute.return_value = result
    _patch_session(monkeypatch, session)
    return session


@pytest.mark.asyncio
async def test_delete_old_activity_returns_rows_removed(monkeypatch):
    _session_with_rowcount(monkeypatch, 12)
    assert await activity.delete_old_activity() == 12


@pytest.mark.asyncio
async def test_delete_old_activity_handles_a_null_rowcount(monkeypatch):
    # Some drivers report -1/None rather than a count; that is "nothing to
    # report", not a crash.
    _session_with_rowcount(monkeypatch, None)
    assert await activity.delete_old_activity() == 0


@pytest.mark.asyncio
async def test_delete_old_activity_cuts_off_at_the_retention_window(monkeypatch):
    session = _session_with_rowcount(monkeypatch, 0)
    before = datetime.now(timezone.utc)

    await activity.delete_old_activity(retention_days=7)

    stmt = session.execute.await_args.args[0]
    # The compiled WHERE clause carries the cutoff as a bound parameter.
    cutoff = next(v for v in stmt.compile().params.values() if isinstance(v, datetime))
    expected = before - timedelta(days=7)
    assert abs((cutoff - expected).total_seconds()) < 5


@pytest.mark.asyncio
async def test_delete_old_activity_respects_an_explicit_zero(monkeypatch):
    """`retention_days=0` means "keep nothing", not "fall back to the default"."""
    session = _session_with_rowcount(monkeypatch, 0)
    before = datetime.now(timezone.utc)

    await activity.delete_old_activity(retention_days=0)

    stmt = session.execute.await_args.args[0]
    cutoff = next(v for v in stmt.compile().params.values() if isinstance(v, datetime))
    assert abs((cutoff - before).total_seconds()) < 5


@pytest.mark.asyncio
async def test_cleanup_loop_survives_a_failing_run(monkeypatch):
    """A broken prune must not be able to take the server down."""
    calls = []

    async def flaky():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("database is down")
        return 0

    monkeypatch.setattr(activity, "delete_old_activity", flaky)

    # A tiny interval keeps the test fast; the loop runs until cancelled.
    task = asyncio.create_task(activity.activity_cleanup_loop(interval_hours=1 / 3600))
    while len(calls) < 3:
        await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 3


@pytest.mark.asyncio
async def test_cleanup_loop_stops_on_cancellation(monkeypatch):
    monkeypatch.setattr(activity, "delete_old_activity", AsyncMock(return_value=0))

    task = asyncio.create_task(activity.activity_cleanup_loop(interval_hours=1))
    await asyncio.sleep(0.02)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert task.cancelled()


@pytest.mark.asyncio
async def test_cleanup_old_activity_logs_alias(monkeypatch):
    _session_with_rowcount(monkeypatch, 5)
    assert await activity.cleanup_old_activity_logs(retention_days=10) == 5
    assert await activity.cleanup_old_activity_logs(None, 10) == 5
    assert await activity.cleanup_old_activity_logs(10) == 5
