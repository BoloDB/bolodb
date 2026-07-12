import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
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
import backend.app.mongodatabase as mdb

log = logging.getLogger(__name__)
router = APIRouter()


async def _format_sse(stream):
    """Wrap an async generator of dicts into SSE ``data: {...}\\n\\n`` lines."""
    try:
        async for event in stream:
            yield f"data: {json.dumps(event, default=str)}\n\n"
    except Exception:
        log.exception("Unhandled error while streaming query results")
        yield f"data: {json.dumps({'kind': 'error', 'message': 'An internal error occurred.'})}\n\n"


def _safe_save_query(user_id, question, sql, result, confidence):
    import backend.app.mongodatabase as mdb

    try:
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
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
):
    user_id = user_token["user_id"]
    out = await ctrl.run_query(user_id, db, kb, cfg, providers, session_log, req)

    if out.get("answered") and out.get("sql"):
        conf = out.get("confidence", "low")
        conf_str = "High" if conf == "high" else "Medium" if conf == "medium" else "Low"
        # Only link the turn to a conversation the caller actually owns —
        # otherwise a request could inject turns into someone else's thread.
        conversation_id = req.conversation_id
        if conversation_id and not await run_in_threadpool(
            mdb.conversation_owned_by, user_id, conversation_id
        ):
            conversation_id = None
        try:
            await run_in_threadpool(
                mdb.save_query,
                user_id=user_token["user_id"],
                question=req.question,
                sql=out["sql"],
                result=out.get("rows", []),
                confidence=conf_str,
                conversation_id=conversation_id,
                restatement=out.get("restatement", ""),
            )
            if conversation_id:
                await run_in_threadpool(mdb.touch_conversation, conversation_id)
        except Exception:
            log.warning("Failed to persist query history", exc_info=True)
    return out


@router.post("/api/query/stream")
async def query_stream(
    req: QueryReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
):
    user_id = user_token["user_id"]
    stream = ctrl.run_query_stream(user_id, db, kb, cfg, providers, session_log, req)

    # Note: we can't easily save the query before the stream ends
    # because we don't have the final SQL yet.
    # The controller's run_query_stream should handle logging
    # and persistence of the result event.

    return StreamingResponse(
        _format_sse(stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.post("/api/explain")
async def explain(
    req: RawSQLReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    """Plain-English explanation of a SQL query (reverse text-to-SQL)."""
    user_id = user_token["user_id"]
    return await ctrl.explain(user_id, db, providers, req)
