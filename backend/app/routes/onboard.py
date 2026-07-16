import logging

from fastapi import APIRouter, Depends, Request, HTTPException
from backend.app.dependencies import get_current_user, get_db, get_kb, get_providers
from backend.app.models.api import SaveOnboardReq
from backend.app.ratelimit import limiter
import backend.app.controllers.onboard as ctrl

log = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/onboard/glossary")
@limiter.limit("20/minute")
async def onboard_glossary(
    request: Request,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    try:
        user_id = user_token["user_id"]
        return await ctrl.get_glossary(user_id, db, providers)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to generate glossary")
        raise HTTPException(500, "Failed to generate glossary")


@router.post("/api/onboard/starters")
@limiter.limit("20/minute")
async def onboard_starters(
    request: Request,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    try:
        user_id = user_token["user_id"]
        return await ctrl.get_starters(user_id, db, providers)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to generate starters")
        raise HTTPException(500, "Failed to generate example questions")


@router.post("/api/onboard/save")
@limiter.limit("20/minute")
async def onboard_save(
    request: Request,
    req: SaveOnboardReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    try:
        user_id = user_token["user_id"]
        return await ctrl.save(user_id, db, kb, req)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to save onboarding data")
        raise HTTPException(500, "Failed to save onboarding data")
