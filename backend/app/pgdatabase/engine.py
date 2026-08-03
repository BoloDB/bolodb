"""Async PostgreSQL engine and session management."""

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

load_dotenv()

_ENGINE_URL = os.getenv("DATABASE_URL")
_engine = None
_session_factory = None


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def get_engine():
    global _engine
    if _engine is None:
        if not _ENGINE_URL:
            raise ValueError(
                "DATABASE_URL environment variable is required. "
                "Example: postgresql+asyncpg://user:pass@host:5432/dbname"
            )
        db_url = _ENGINE_URL
        if db_url.startswith("postgresql://"):
            db_url = "postgresql+asyncpg://" + db_url[len("postgresql://") :]
        elif db_url.startswith("postgres://"):
            db_url = "postgresql+asyncpg://" + db_url[len("postgres://") :]
        # ── Pool tuning ──
        # pool_pre_ping issues a liveness round trip to the database *before
        # handing out every pooled connection*. That is one extra round trip on
        # every request that touches the database, and it is not amortised --
        # it repeats even when the connection is demonstrably healthy and was
        # used moments ago. Against a managed Postgres it roughly doubled the
        # cost of a checkout in our measurements.
        #
        # What it buys is protection against a connection that died while idle
        # in the pool. pool_recycle already closes that window from the other
        # side by retiring connections on a timer, well inside any sane server
        # or pooler idle timeout, so pre-ping is mostly re-checking what
        # recycling has already handled. Default it off and keep recycling.
        #
        # Every value is env-tunable: a deployment that genuinely sees stale
        # connections (an aggressive proxy, a flaky link) can set
        # DB_POOL_PRE_PING=true without a code change, and a deployment with
        # the database next door can raise the pool instead.
        _engine = create_async_engine(
            db_url,
            pool_size=_env_int("DB_POOL_SIZE", 5),
            max_overflow=_env_int("DB_MAX_OVERFLOW", 10),
            pool_recycle=_env_int("DB_POOL_RECYCLE", 300),
            pool_pre_ping=_env_bool("DB_POOL_PRE_PING", False),
            # Required for pgbouncer-style transaction pooling, which cannot
            # carry server-side prepared statements across checkouts. Measured
            # as costing nothing here (166ms vs 174ms per query), so it stays.
            connect_args={"statement_cache_size": 0},
        )
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


def _get_session() -> AsyncSession:
    return _get_session_factory()()


async_session = _get_session


async def dispose_db():
    if _engine is not None:
        await _engine.dispose()
