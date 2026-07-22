"""FastAPI application."""

import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app import config as cfgmod
from backend.app.database import DatabaseManager
from backend.app.logbook import SessionLog
from backend.app.llm import ProviderManager
from backend.app.ratelimit import limiter
from backend.app.pgdatabase import KnowledgeService
from backend.app.pgdatabase.engine import async_session

from backend.app.routes import (
    auth,
    catalog,
    connections,
    conversations,
    database,
    history,
    onboard,
    query,
    system,
    workspaces,
    dashboards,
    saved_queries,
)

logger = logging.getLogger(__name__)

MAX_BODY_SIZE = 1 * 1024 * 1024  # 1MB


class BodyLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except (ValueError, TypeError):
                return Response(
                    content="Invalid Content-Length",
                    status_code=400,
                )
            if size > MAX_BODY_SIZE:
                return Response(
                    content="Request body too large",
                    status_code=413,
                )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app):
    skip_lock = os.getenv("SKIP_DB_LOCK", "").lower() == "true"

    if not skip_lock:
        from alembic.config import Config
        from alembic import command
        from sqlalchemy import text

        alembic_ini = Path(__file__).resolve().parents[1] / "alembic.ini"
        alembic_cfg = Config(str(alembic_ini))
        alembic_cfg.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        from backend.app.pgdatabase import get_engine, dispose_db

        engine = get_engine()
        async with engine.begin() as lock_conn:
            await lock_conn.execute(
                text("SELECT pg_advisory_xact_lock(2305843009213693951)")
            )
            await run_in_threadpool(command.upgrade, alembic_cfg, "head")
    else:
        from backend.app.pgdatabase import dispose_db

    yield

    await dispose_db()


def create_app(initial_db_url="", readonly=True):
    """
    Create and configure the FastAPI application and its backend services.

    Parameters:
        initial_db_url (str): Ignored legacy database URL; connections are established per authenticated user.
        readonly (bool): Whether database access should be read-only.

    Returns:
        FastAPI: The configured application instance.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )

    # IMPORTANT — single-process only. `cfg`, `providers`, `db`, `kb` and
    # `session_log` are per-process in-memory state. `db` holds live database
    # connections keyed by user_id, and `cfg` (including saved API keys) is
    # loaded once and rewritten in place. Running more than one worker/replica
    # (e.g. uvicorn --workers N, gunicorn, or multiple containers) means a user
    # who connects on one worker gets "No database connected" on another, and
    # concurrent config saves on different workers clobber config.json. Run this
    # as a single process, or externalize this state before scaling out.
    cfg = cfgmod.load_config()
    providers = ProviderManager(cfg)
    db = DatabaseManager(readonly=readonly)
    kbs = KnowledgeService(async_session)
    session_log = SessionLog(cfgmod.CONFIG_DIR)

    app = FastAPI(title="BoloDB", version="2.0.0", lifespan=lifespan)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    cors_origins = os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://localhost"
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(BodyLimitMiddleware)

    app.state.cfg = cfg
    app.state.providers = providers
    app.state.db = db
    app.state.kbs = kbs
    app.state.session_log = session_log

    if initial_db_url:
        # Pre-connect is not supported by the multi-user server: database
        # connections are keyed per authenticated user (db.connect(user_id, url)),
        # and there is no user at startup. Previously this crashed with a
        # TypeError; now it is a logged no-op. Connect from the UI instead.
        logger.warning(
            "initial_db_url/--db is ignored: connections are per-authenticated-user "
            "in the server. Connect from the UI after signing in."
        )

    app.include_router(auth.router)
    app.include_router(system.router)
    app.include_router(database.router)
    app.include_router(onboard.router)
    app.include_router(query.router)
    app.include_router(history.router)
    app.include_router(connections.router)
    app.include_router(catalog.router)
    app.include_router(conversations.router)
    app.include_router(workspaces.router)
    app.include_router(dashboards.router)
    app.include_router(saved_queries.router)

    # Catch-all for API 404app

    return app
