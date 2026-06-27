from fastapi import APIRouter, Depends
from backend.app.dependencies import get_current_user, get_db, get_kb, get_cfg, get_providers, get_session_log
from backend.app.models.api import QueryReq, FeedbackReq, VerifyReq, RawSQLReq
import backend.app.controllers.query as ctrl

router = APIRouter()

@router.post("/api/query")
async def query(
    req: QueryReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log)
):
    return await ctrl.run_query(db, kb, cfg, providers, session_log, req)

@router.post("/api/feedback")
async def feedback(
    req: FeedbackReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    session_log=Depends(get_session_log)
):
    return await ctrl.feedback(db, kb, session_log, req)

@router.post("/api/verify")
async def verify(
    req: VerifyReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb)
):
    return await ctrl.verify(db, kb, req)

@router.post("/api/execute")
async def execute(
    req: RawSQLReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db)
):
    return await ctrl.execute(db, req)
