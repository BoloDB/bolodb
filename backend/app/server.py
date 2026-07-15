"""FastAPI application."""

import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from backend.app import config as cfgmod
from backend.app.database import DatabaseManager
from backend.app.knowledge import KnowledgeBase
from backend.app.logbook import SessionLog
from backend.app.llm import ProviderManager

from backend.app.routes.auth import router as auth_router
from backend.app.routes.system import router as system_router
from backend.app.routes.database import router as database_router
from backend.app.routes.onboard import router as onboard_router
from backend.app.routes.query import router as query_router
from backend.app.routes.history import router as history_router
from backend.app.routes.connections import router as connections_router
from backend.app.routes.catalog import router as catalog_router
from backend.app.routes.conversations import router as conversations_router

logger = logging.getLogger(__name__)

MAX_BODY_SIZE = 1 * 1024 * 1024  # 1MB


class BodyLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return Response(
                content="Request body too large",
                status_code=413,
            )
        return await call_next(request)


@asynccontextmanager
async def lifespan(app):
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
    yield

    await dispose_db()


def create_app(initial_db_url="", readonly=True):
    cfg = cfgmod.load_config()
    providers = ProviderManager(cfg)
    db = DatabaseManager(readonly=readonly)
    kb = KnowledgeBase(cfgmod.KB_FILE)
    session_log = SessionLog(cfgmod.CONFIG_DIR)

    limiter = Limiter(key_func=get_remote_address)
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
    app.state.kb = kb
    app.state.session_log = session_log

    if initial_db_url:
        db.connect(initial_db_url)

    app.include_router(auth_router)
    app.include_router(system_router)
    app.include_router(database_router)
    app.include_router(onboard_router)
    app.include_router(query_router)
    app.include_router(history_router)
    app.include_router(connections_router)
    app.include_router(catalog_router)
    app.include_router(conversations_router)

    return app
