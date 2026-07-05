import logging
from fastapi import APIRouter, Depends, BackgroundTasks
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


def _save_query_task(user_id, question, sql, result, confidence):
    """
    Background task wrapper to save query history.
    Includes exception handling because exceptions in background tasks
    are not caught by try/except around add_task.
    """
    try:
        import backend.app.mongodatabase as mdb

        mdb.save_query(
            user_id=user_id,
            question=question,
            sql=sql,
            result=result,
            confidence=confidence,
        )
    except Exception:
        log.warning("Failed to persist query history in background", exc_info=True)


@router.post("/api/query")
async def query(
    req: QueryReq,
    background_tasks: BackgroundTasks,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
):
    user_id = user_token["user_id"]
    out = await ctrl.run_query(user_id, db, kb, cfg, providers, session_log, req)

    # Performance optimization: fire-and-forget I/O in a background task
    # so we don't delay the API response to the user.
    if out.get("answered") and out.get("sql"):
        conf = out.get("confidence", "low")
        conf_str = "High" if conf == "high" else "Medium" if conf == "medium" else "Low"

        background_tasks.add_task(
            _save_query_task,
            user_id=user_id,
            question=req.question,
            sql=out["sql"],
            result=out.get("rows", []),
            confidence=conf_str,
        )

    return out


@router.post("/api/feedback")
async def feedback(
    req: FeedbackReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    session_log=Depends(get_session_log),
):
    user_id = user_token["user_id"]
    return await ctrl.feedback(user_id, db, kb, session_log, req)


@router.post("/api/verify")
async def verify(
    req: VerifyReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    user_id = user_token["user_id"]
    return await ctrl.verify(user_id, db, kb, req)


@router.post("/api/execute")
async def execute(
    req: RawSQLReq, user_token=Depends(get_current_user), db=Depends(get_db)
):
    user_id = user_token["user_id"]
    return await ctrl.execute(user_id, db, req)
