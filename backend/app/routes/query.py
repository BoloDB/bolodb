import logging
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from backend.app.dependencies import (
    get_current_user,
    get_db,
    get_kb,
    get_cfg,
    get_providers,
    get_session_log,
)
from backend.app.models.api import QueryReq, FeedbackReq, VerifyReq, RawSQLReq
import backend.app.controllers.query as ctrl

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/query")
async def query(
    req: QueryReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
):
    out = await ctrl.run_query(db, kb, cfg, providers, session_log, req)

    import backend.app.mongodatabase as mdb

    if out.get("answered") and out.get("sql"):
        conf = out.get("confidence", "low")
        conf_str = "High" if conf == "high" else "Medium" if conf == "medium" else "Low"
        try:
            await run_in_threadpool(
                mdb.save_query,
                user_id=user_token["user_id"],
                question=req.question,
                sql=out["sql"],
                result=out.get("rows", []),
                confidence=conf_str,
            )
        except Exception:
            log.warning("Failed to persist query history", exc_info=True)
    return out


@router.post("/api/feedback")
async def feedback(
    req: FeedbackReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    session_log=Depends(get_session_log),
):
    return await ctrl.feedback(db, kb, session_log, req)


@router.post("/api/verify")
async def verify(
    req: VerifyReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    return await ctrl.verify(db, kb, req)


@router.post("/api/execute")
async def execute(
    req: RawSQLReq, user_token=Depends(get_current_user), db=Depends(get_db)
):
    return await ctrl.execute(db, req)
