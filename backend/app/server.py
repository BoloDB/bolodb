"""FastAPI application."""
import asyncio
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.app import config as cfgmod
from backend.app.database import DatabaseManager, sanitize_url
from backend.app.knowledge import KnowledgeBase
from backend.app.logbook import SessionLog
from backend.app.llm import ProviderManager, generate_sql, generate_glossary, generate_starters
from backend.app.schema_link import model_budget, link_relevant_tables, compact_schema, compute_confidence
from sample_data import ensure_sample_db

STATIC = Path(__file__).parent.parent / "static"
logger = logging.getLogger(__name__)

class ConfigUpdate(BaseModel):
    provider: str | None = None
    model: str | None = None
    ollama_url: str | None = None
    api_key: str | None = None

class ConnectReq(BaseModel): 
    db_url: str
class QueryReq(BaseModel): 
    question: str
class VerifyReq(BaseModel): 
    question: str
    sql: str
    restatement: str = ""
class FeedbackReq(BaseModel):
    query_id: str = ""
    verdict: str
    reason: str = ""
    question: str = ""
    sql: str = ""
    restatement: str = ""
class RawSQLReq(BaseModel): 
    sql: str
class GlossaryItem(BaseModel): 
    term: str
    maps_to: str = ""
    sql_hint: str = ""
class SaveOnboardReq(BaseModel):
    glossary: list[GlossaryItem] = []
    starters: list[dict] = []

def create_app(initial_db_url="", readonly=True):
    cfg = cfgmod.load_config()
    providers = ProviderManager(cfg)
    db = DatabaseManager(readonly=readonly)
    kb = KnowledgeBase(cfgmod.KB_FILE)
    session_log = SessionLog(cfgmod.CONFIG_DIR)

    app = FastAPI(title="BoloDB", version="2.0.0")

    if initial_db_url:
        db.connect(initial_db_url)

    @app.get("/api/state")
    async def state():
        s = {"connected":db.connected,"config":cfgmod.public_config(cfg)}
        if db.connected:
            s["database"] = {"url":sanitize_url(db.url) if db.url else None,
                             "dialect":db.dialect,"db_id":db.db_id,
                             "tables":db._table_count}
            s["trust"]    = kb.trust_level(db.db_id)
            s["glossary"] = kb.get_glossary(db.db_id)
            # Surface verified starter questions so the UI can show them as chips
            s["starters"] = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
        return s

    @app.get("/api/ollama-check")
    async def ollama_check():
        """Always checks Ollama health regardless of configured provider."""
        import httpx as _httpx
        url = cfg.get("ollama_url", "http://localhost:11434")
        try:
            async with _httpx.AsyncClient(timeout=3) as c:
                r = await c.get(f"{url}/api/tags")
                r.raise_for_status()
                models = [m["name"] for m in r.json().get("models", [])]
                return {"ok": True, "models": models}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    @app.get("/api/health")
    async def health():
        ph = await providers.get().health_check()
        return {"provider":{"name":cfg["provider"],**ph},"connected":db.connected}

    @app.post("/api/config")
    async def update_config(req: ConfigUpdate):
        if req.provider: cfg["provider"] = req.provider
        if req.model is not None: cfg["model"] = req.model
        if req.ollama_url: cfg["ollama_url"] = req.ollama_url
        if req.api_key and req.provider in ("claude","openai","groq"):
            cfg["api_keys"][req.provider] = req.api_key
        cfgmod.save_config(cfg)
        providers.reconfigure(cfg)
        h = await providers.get().health_check()
        return {"config":cfgmod.public_config(cfg),"health":h}

    @app.post("/api/connect")
    async def connect(req: ConnectReq):
        result = db.connect(req.db_url)
        if not result["ok"]: raise HTTPException(400, result["error"])
        cfg["last_db_url"] = req.db_url
        cfgmod.save_config(cfg)
        result["trust"]        = kb.trust_level(db.db_id)
        result["glossary"]     = kb.get_glossary(db.db_id)
        result["has_knowledge"]= kb.count_verified(db.db_id) > 0
        result["starters"]     = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
        return result

    @app.post("/api/connect-sample")
    async def connect_sample():
        url = ensure_sample_db()
        result = db.connect(url)
        if not result["ok"]: raise HTTPException(500, result["error"])
        cfg["last_db_url"] = url
        cfgmod.save_config(cfg)
        result["trust"]        = kb.trust_level(db.db_id)
        result["glossary"]     = kb.get_glossary(db.db_id)
        result["has_knowledge"]= kb.count_verified(db.db_id) > 0
        result["starters"]     = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
        result["is_sample"]    = True
        return result

    @app.post("/api/disconnect")
    async def disconnect():
        db.disconnect()
        cfg.pop("last_db_url", None)
        try:
            cfgmod.save_config(cfg)
        except Exception as e:
            # Disconnect already succeeded in memory; persisting the cleared
            # last_db_url is best-effort, so log and still report success.
            logger.warning("Failed to save config after disconnect: %s", e)
        return {"ok": True}

    @app.get("/api/schema")
    async def schema(refresh: bool = False):
        _need_db(db)
        return db.get_schema(refresh=refresh)

    @app.post("/api/onboard/glossary")
    async def onboard_glossary():
        _need_db(db)
        try:
            terms = await generate_glossary(providers.get(), db.schema_as_text())
            return {"glossary": terms}
        except Exception as e:
            raise HTTPException(502, f"LLM error: {e}")

    @app.post("/api/onboard/starters")
    async def onboard_starters():
        _need_db(db)
        try:
            starters = await generate_starters(providers.get(), db.schema_as_text(), db.dialect)

            async def _run_starter(s):
                res = await run_in_threadpool(db.execute, s.get("sql", ""))
                s["columns"] = res.get("columns", [])
                s["rows"]    = res.get("rows", [])[:5]
                s["error"]   = res.get("error")
                return s

            starters = list(await asyncio.gather(*[_run_starter(s) for s in starters]))
            return {"starters": starters}
        except Exception as e:
            raise HTTPException(502, f"LLM error: {e}")

    @app.post("/api/onboard/save")
    async def onboard_save(req: SaveOnboardReq):
        _need_db(db)
        kb.set_glossary(db.db_id, [g.dict() for g in req.glossary])
        for s in req.starters:
            kb.add_verified(db.db_id, s.get("question",""), s.get("sql",""), s.get("restatement",""))
        return {"ok":True,"trust":kb.trust_level(db.db_id)}

    @app.post("/api/query")
    async def query(req: QueryReq):
        _need_db(db)
        q = req.question.strip()
        if not q: raise HTTPException(400, "Empty question")
        glossary  = kb.get_glossary(db.db_id)
        retrieved = kb.retrieve_similar(db.db_id, q, k=3)
        budget    = model_budget(cfg.get("provider","ollama"), cfg.get("model",""))
        full_schema = db.get_schema()
        tables    = link_relevant_tables(q, full_schema, glossary, retrieved, budget["max_tables"])
        schema_text = compact_schema(full_schema, tables, budget["samples"])
        try:
            gen = await generate_sql(providers.get(), q, schema_text, db.dialect,
                                     glossary, retrieved, budget["max_examples"])
        except Exception as e:
            out = {"answered":True,"sql":"","restatement":"",
                   "confidence":"low","confidence_reason":"Could not form a query - try rephrasing",
                   "based_on_verified":False,"execution_error":str(e),"columns":[],"rows":[]}
            out["query_id"] = session_log.log_query(db.db_id, q, out)
            return out
        sql = gen.get("sql","")
        restatement = gen.get("restatement","")
        exec_result = await run_in_threadpool(db.execute, sql)
        confidence, reason, based = compute_confidence(retrieved, exec_result)
        out = {"answered":True,"sql":sql,"restatement":restatement,
               "confidence":confidence,"confidence_reason":reason,"based_on_verified":based,
               "columns":exec_result.get("columns",[]),
               "rows":exec_result.get("rows",[]),
               "truncated":exec_result.get("truncated",False),
               "tables_used":tables}
        if "error" in exec_result: out["execution_error"] = exec_result["error"]
        out["query_id"] = session_log.log_query(db.db_id, q, out)
        return out

    @app.post("/api/feedback")
    async def feedback(req: FeedbackReq):
        _need_db(db)
        session_log.log_feedback(req.query_id, req.verdict, req.reason)
        if req.verdict == "correct":
            kb.add_verified(db.db_id, req.question, req.sql, req.restatement)
        out = {"ok": True, "trust": kb.trust_level(db.db_id)}
        if req.verdict == "correct":
            out["starters"] = [v["question"] for v in kb.get_verified(db.db_id)[:6]]
        return out

    @app.post("/api/verify")
    async def verify(req: VerifyReq):
        _need_db(db)
        kb.add_verified(db.db_id, req.question, req.sql, req.restatement)
        return {"ok":True,"trust":kb.trust_level(db.db_id)}

    @app.post("/api/execute")
    async def execute(req: RawSQLReq):
        _need_db(db)
        res = await run_in_threadpool(db.execute, req.sql)
        if "error" in res: raise HTTPException(400, res["error"])
        return res

    @app.get("/", response_class=HTMLResponse)
    async def root():
        idx = STATIC / "index.html"
        if idx.exists(): return HTMLResponse(idx.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>BoloDB running</h1>")

    if STATIC.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")

    return app

def _need_db(db):
    if not db.connected: raise HTTPException(409, "No database connected")
