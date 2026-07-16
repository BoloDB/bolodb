import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.app.dependencies import get_current_user, get_db, get_kb, get_providers
from backend.app.models.api import CatalogPayload
import backend.app.controllers.catalog as ctrl

log = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/catalog")
async def get_catalog(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    """Return the saved semantic catalog for the connected database."""
    try:
        return ctrl.get_catalog(user_token["user_id"], db, kb)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get catalog")
        raise HTTPException(500, "Failed to retrieve catalog")


@router.post("/api/catalog")
async def save_catalog(
    payload: CatalogPayload,
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    kb=Depends(get_kb),
):
    """Replace the connected database's semantic catalog with ``payload``."""
    try:
        return ctrl.save_catalog(user_token["user_id"], db, kb, payload)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to save catalog")
        raise HTTPException(500, "Failed to save catalog")


@router.post("/api/catalog/suggest")
async def suggest_catalog(
    user_token=Depends(get_current_user),
    db=Depends(get_db),
    providers=Depends(get_providers),
):
    """Return AI + schema-derived catalog suggestions (not yet saved)."""
    try:
        return await ctrl.suggest(user_token["user_id"], db, providers)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to suggest catalog")
        raise HTTPException(500, "Failed to generate catalog suggestions")
