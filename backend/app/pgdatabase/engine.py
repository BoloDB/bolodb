"""Async PostgreSQL engine and session management."""

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

load_dotenv()

_ENGINE_URL = os.getenv("DATABASE_URL")
_engine = None
_session_factory = None


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
        _engine = create_async_engine(
            db_url,
            pool_size=5,
            max_overflow=10,
            pool_recycle=300,
            pool_pre_ping=True,
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
