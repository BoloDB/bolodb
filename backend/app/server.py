"""FastAPI application."""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

logger = logging.getLogger(__name__)

def create_app(initial_db_url="", readonly=True):
    cfg = cfgmod.load_config()
    providers = ProviderManager(cfg)
    db = DatabaseManager(readonly=readonly)
    kb = KnowledgeBase(cfgmod.KB_FILE)
    session_log = SessionLog(cfgmod.CONFIG_DIR)

    app = FastAPI(title="BoloDB", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    return app
