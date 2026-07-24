"""Alembic async migration environment."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from backend.app.pgdatabase import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override with DATABASE_URL from environment — alembic.ini has no credentials
db_url = os.getenv("DATABASE_URL")
if db_url:
    if db_url.startswith("postgresql://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgresql://") :]
    elif db_url.startswith("postgres://"):
        db_url = "postgresql+asyncpg://" + db_url[len("postgres://") :]
    db_url = db_url.replace("%", "%%")
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


# Any 64-bit constant works; it only has to be the same in every process that
# migrates this database. Derived from the project name so it cannot collide
# with an advisory lock another application takes on a shared cluster.
_MIGRATION_LOCK_ID = 8410231166942030001


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        # Containers start migrations concurrently on a scaled deployment, and
        # two Alembic runs against one database race on alembic_version. The
        # transaction-scoped advisory lock makes the second wait for the first
        # and then find nothing left to apply; it is released on commit or
        # rollback, so a crashed migration cannot wedge later deploys.
        connection.exec_driver_sql(
            f"SELECT pg_advisory_xact_lock({_MIGRATION_LOCK_ID})"
        )
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},
    )
    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
