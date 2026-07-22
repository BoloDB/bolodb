import json
import logging
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from backend.app.dependencies import (
    get_current_workspace,
    get_db,
    get_kb,
    get_cfg,
    get_providers,
    get_session_log,
)
from backend.app.models.api import QueryReq, FeedbackReq, VerifyReq, RawSQLReq
from backend.app.ratelimit import limiter
import backend.app.controllers.query as ctrl
import backend.app.pgdatabase as mdb
from backend.app.pgdatabase.conversations import MAX_SAVED_ROWS

log = logging.getLogger(__name__)
router = APIRouter()


async def _format_sse(stream):
    try:
        async for event in stream:
            yield f"data: {json.dumps(event, default=str)}\n\n"
    except Exception:
        log.error("Unhandled error while streaming query response", exc_info=True)
        yield f"data: {json.dumps({'kind': 'error', 'message': 'An internal error has occurred.'})}\n\n"


@router.post("/api/query")
@limiter.limit("30/minute")
async def query(
    request: Request,
    req: QueryReq,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
) -> dict:
    try:
        workspace_id = workspace["workspace_id"]
        out = await ctrl.run_query(
            workspace_id, db, kb, cfg, providers, session_log, req
        )

        if out.get("answered") and out.get("sql"):
            conf = out.get("confidence", "low")
            conf_str = (
                "High" if conf == "high" else "Medium" if conf == "medium" else "Low"
            )
            conversation_id = req.conversation_id
            if conversation_id and not await mdb.conversation_owned_by(
                workspace_id, conversation_id
            ):
                conversation_id = None
            try:
                await mdb.save_query(
                    workspace_id=workspace_id,
                    question=req.question,
                    sql=out["sql"],
                    result=out.get("rows", []),
                    confidence=conf_str,
                    conversation_id=conversation_id,
                    restatement=out.get("restatement", ""),
                )
                if conversation_id:
                    await mdb.touch_conversation(conversation_id)
            except Exception:
                log.warning("Failed to persist query history", exc_info=True)
        return out
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to process query")
        raise HTTPException(500, "Failed to process your question")


@router.post("/api/query/stream")
@limiter.limit("30/minute")
async def query_stream(
    request: Request,
    req: QueryReq,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
    kb=Depends(get_kb),
    cfg=Depends(get_cfg),
    providers=Depends(get_providers),
    session_log=Depends(get_session_log),
) -> StreamingResponse:
    try:
        workspace_id = workspace["workspace_id"]
        stream = ctrl.run_query_stream(
            workspace_id, db, kb, cfg, providers, session_log, req
        )

        return StreamingResponse(
            _format_sse(stream),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to start streaming query")
        raise HTTPException(500, "Failed to start streaming query")


@router.post("/api/feedback")
async def feedback(
    req: FeedbackReq,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
    kb=Depends(get_kb),
    session_log=Depends(get_session_log),
) -> dict:
    try:
        workspace_id = workspace["workspace_id"]
        return await ctrl.feedback(workspace_id, db, kb, session_log, req)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to process feedback")
        raise HTTPException(500, "Failed to save feedback")


@router.post("/api/verify")
async def verify(
    req: VerifyReq,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
    kb=Depends(get_kb),
) -> dict:
    try:
        workspace_id = workspace["workspace_id"]
        return await ctrl.verify(workspace_id, db, kb, req)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to verify answer")
        raise HTTPException(500, "Failed to verify answer")


@router.post("/api/execute")
@limiter.limit("60/minute")
async def execute(
    request: Request,
    req: RawSQLReq,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
) -> dict:
    try:
        workspace_id = workspace["workspace_id"]
        out = await ctrl.execute(workspace_id, db, req)

        conversation_id = req.conversation_id
        if conversation_id and not await mdb.conversation_owned_by(
            workspace_id, conversation_id
        ):
            conversation_id = None
        try:
            await mdb.save_query(
                workspace_id=workspace_id,
                question=req.sql,
                sql=req.sql,
                result=(out.get("rows") or [])[:MAX_SAVED_ROWS],
                confidence="High",
                conversation_id=conversation_id,
                restatement="Direct SQL execution",
            )
            if conversation_id:
                await mdb.touch_conversation(conversation_id)
        except Exception:
            log.warning("Failed to persist direct SQL history", exc_info=True)
        return out
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to execute SQL")
        raise HTTPException(500, "Failed to execute SQL query")


@router.post("/api/explain")
@limiter.limit("30/minute")
async def explain(
    request: Request,
    req: RawSQLReq,
    workspace=Depends(get_current_workspace),
    db=Depends(get_db),
    providers=Depends(get_providers),
) -> dict:
    try:
        workspace_id = workspace["workspace_id"]
        return await ctrl.explain(workspace_id, db, providers, req)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to explain SQL")
        raise HTTPException(500, "Failed to generate SQL explanation")
