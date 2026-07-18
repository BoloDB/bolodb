"""Semantic-catalog endpoints (issue #90): read, save, and AI-suggest the
per-database catalog that maps business language to schema entities."""

import logging

from fastapi import HTTPException

from backend.app.llm import suggest_catalog as llm_suggest_catalog
from backend.app.semantic import merge_catalog_suggestions, suggest_from_schema

log = logging.getLogger(__name__)


async def get_catalog(user_id, db, kb):
    """Return the stored catalog for the user's connected database."""
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    return {"catalog": await kb.get_catalog(user_id, db.get_db_id(user_id))}


async def save_catalog(user_id, db, kb, payload):
    """Persist ``payload`` as the connected database's catalog."""
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    await kb.set_catalog(user_id, db.get_db_id(user_id), payload.model_dump())
    return {"ok": True}


async def suggest(user_id, db, providers):
    """Suggest a catalog: the deterministic backbone (joins + value maps from
    the schema) enriched by the LLM (descriptions, metrics, synonyms, labels).
    The LLM step degrades gracefully — a failure still returns the backbone."""
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    base = suggest_from_schema(db.get_schema(user_id))
    try:
        enriched = await llm_suggest_catalog(
            providers.get(user_id), db.schema_as_text(user_id)
        )
    except Exception:
        # Graceful degradation: still return the schema-only backbone, but log
        # the cause so misconfiguration / rate limits are diagnosable.
        log.warning(
            "catalog suggest: LLM enrichment failed, returning schema-only suggestions",
            exc_info=True,
        )
        enriched = {}
    return {"catalog": merge_catalog_suggestions(base, enriched)}
