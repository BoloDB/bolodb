"""Pool configuration is read from the environment, with safe defaults.

These assert the knobs are actually wired to create_async_engine — a typo in an
env var name would otherwise fail silently and leave the default in place,
which is exactly the kind of thing nobody notices until a deploy is slow.
"""

import pytest

from backend.app.pgdatabase import engine as engine_mod


@pytest.fixture
def fresh_engine(monkeypatch):
    """Capture the kwargs the engine would be built with."""
    captured = {}

    def fake_create_async_engine(url, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(engine_mod, "create_async_engine", fake_create_async_engine)
    monkeypatch.setattr(engine_mod, "_engine", None)
    monkeypatch.setattr(
        engine_mod, "_ENGINE_URL", "postgresql://u:p@localhost:5432/testdb"
    )
    return captured


def test_defaults_disable_pre_ping_and_keep_recycling(fresh_engine, monkeypatch):
    for var in (
        "DB_POOL_PRE_PING",
        "DB_POOL_RECYCLE",
        "DB_POOL_SIZE",
        "DB_MAX_OVERFLOW",
    ):
        monkeypatch.delenv(var, raising=False)

    engine_mod.get_engine()

    # Pre-ping costs a round trip on every checkout; recycling covers the same
    # window without that cost, so the default is off-but-recycling.
    assert fresh_engine["pool_pre_ping"] is False
    assert fresh_engine["pool_recycle"] == 300
    assert fresh_engine["pool_size"] == 5
    assert fresh_engine["max_overflow"] == 10


def test_pre_ping_can_be_re_enabled_without_a_code_change(fresh_engine, monkeypatch):
    monkeypatch.setenv("DB_POOL_PRE_PING", "true")
    engine_mod.get_engine()
    assert fresh_engine["pool_pre_ping"] is True


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("true", True),
        ("True", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("no", False),
        ("", False),
        ("garbage", False),
    ],
)
def test_bool_env_parsing(fresh_engine, monkeypatch, raw, expected):
    monkeypatch.setenv("DB_POOL_PRE_PING", raw)
    engine_mod.get_engine()
    assert fresh_engine["pool_pre_ping"] is expected


def test_numeric_overrides_are_applied(fresh_engine, monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "20")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "40")
    monkeypatch.setenv("DB_POOL_RECYCLE", "900")
    engine_mod.get_engine()
    assert fresh_engine["pool_size"] == 20
    assert fresh_engine["max_overflow"] == 40
    assert fresh_engine["pool_recycle"] == 900


def test_unparseable_numbers_fall_back_to_defaults(fresh_engine, monkeypatch):
    """A bad value must not take the app down at import time."""
    monkeypatch.setenv("DB_POOL_SIZE", "not-a-number")
    engine_mod.get_engine()
    assert fresh_engine["pool_size"] == 5


def test_statement_cache_stays_disabled_for_transaction_pooling(fresh_engine):
    """pgbouncer transaction mode cannot carry server-side prepared statements."""
    engine_mod.get_engine()
    assert fresh_engine["connect_args"] == {"statement_cache_size": 0}


@pytest.mark.parametrize(
    "given,expected_prefix",
    [
        ("postgresql://u:p@h:5432/d", "postgresql+asyncpg://"),
        ("postgres://u:p@h:5432/d", "postgresql+asyncpg://"),
        ("postgresql+asyncpg://u:p@h:5432/d", "postgresql+asyncpg://"),
    ],
)
def test_url_is_normalised_to_asyncpg(monkeypatch, given, expected_prefix):
    captured = {}
    monkeypatch.setattr(
        engine_mod,
        "create_async_engine",
        lambda url, **kw: captured.update(url=url) or object(),
    )
    monkeypatch.setattr(engine_mod, "_engine", None)
    monkeypatch.setattr(engine_mod, "_ENGINE_URL", given)

    engine_mod.get_engine()
    assert captured["url"].startswith(expected_prefix)


def test_missing_url_raises(monkeypatch):
    monkeypatch.setattr(engine_mod, "_engine", None)
    monkeypatch.setattr(engine_mod, "_ENGINE_URL", None)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        engine_mod.get_engine()
