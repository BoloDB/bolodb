from fastapi import APIRouter, Depends

from backend.app.dependencies import get_current_user, get_db, get_kb, get_providers
from backend.app.models.api import CatalogPayload
import backend.app.controllers.catalog as ctrl

router = APIRouter()


@router.get("/api/catalog")
async def get_catalog(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    """Return the saved semantic catalog for the connected database."""
    return ctrl.get_catalog(user_token["user_id"], db, kb)


@router.post("/api/catalog")
async def save_catalog(
    payload: CatalogPayload,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    """Replace the connected database's semantic catalog with ``payload``."""
    return ctrl.save_catalog(user_token["user_id"], db, kb, payload)


@router.post("/api/catalog/suggest")
async def suggest_catalog(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    """Return AI + schema-derived catalog suggestions (not yet saved)."""
    return await ctrl.suggest(user_token["user_id"], db, providers)
