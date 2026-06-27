from fastapi import APIRouter, Depends
from backend.app.dependencies import get_current_user, get_db, get_kb, get_providers
from backend.app.models.api import SaveOnboardReq
import backend.app.controllers.onboard as ctrl

router = APIRouter()


@router.post("/api/onboard/glossary")
async def onboard_glossary(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    return await ctrl.get_glossary(db, providers)


@router.post("/api/onboard/starters")
async def onboard_starters(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    return await ctrl.get_starters(db, providers)


@router.post("/api/onboard/save")
async def onboard_save(
    req: SaveOnboardReq,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    return await ctrl.save(db, kb, req)
