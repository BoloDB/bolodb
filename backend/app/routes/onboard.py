import logging

from fastapi import APIRouter, Depends, Request, HTTPException
from backend.app.dependencies import (
    require_permission,
    get_db,
    get_kb,
    get_providers,
)
from backend.app.models.api import SaveOnboardReq
from backend.app.ratelimit import limiter
import backend.app.controllers.onboard as ctrl

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/onboard/save")
@limiter.limit("20/minute")
async def onboard_save(
    request: Request,
    req: SaveOnboardReq,
    workspace=Depends(require_permission("catalog.manage")),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    try:
        workspace_id = workspace["workspace_id"]
        return await ctrl.save(workspace_id, db, kb, req)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to save onboarding data")
        raise HTTPException(500, "Failed to save onboarding data")


@router.post("/api/onboard/generate-starters")
@limiter.limit("5/minute")
async def api_generate_starters(
    request: Request,
    workspace=Depends(require_permission("catalog.manage")),
    _execute_permission=Depends(require_permission("queries.execute")),
    db=Depends(get_db),
    kb=Depends(get_kb),
    providers=Depends(get_providers),
):
    try:
        workspace_id = workspace["workspace_id"]
        return await ctrl.generate_starters_async(workspace_id, db, kb, providers)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to generate starters")
        return {"starters": []}
