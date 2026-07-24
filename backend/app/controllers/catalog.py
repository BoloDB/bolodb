"""Semantic-catalog endpoints (issue #90): read, save, and AI-suggest the
per-database catalog that maps business language to schema entities."""

import logging

from fastapi import HTTPException

from backend.app.llm import suggest_catalog as llm_suggest_catalog
from backend.app.semantic import merge_catalog_suggestions, suggest_from_schema

log = logging.getLogger(__name__)


async def get_catalog(workspace_id, db, kb, db_id=None):
    """Return the stored catalog for the user's connected database."""
    if not db.connected(workspace_id, db_id):
        raise HTTPException(409, "No database connected")
    return {
        "catalog": await kb.get_catalog(workspace_id, db.get_db_id(workspace_id, db_id))
    }


async def save_catalog(workspace_id, db, kb, payload, db_id=None):
    """Persist ``payload`` as the connected database's catalog."""
    if not db.connected(workspace_id, db_id):
        raise HTTPException(409, "No database connected")
    await kb.set_catalog(
        workspace_id, db.get_db_id(workspace_id, db_id), payload.model_dump()
    )
    return {"ok": True}


async def suggest(workspace_id, db, providers, db_id=None):
    """Suggest a catalog: the deterministic backbone (joins + value maps from
    the schema) enriched by the LLM (descriptions, metrics, synonyms, labels).
    The LLM step degrades gracefully — a failure still returns the backbone."""
    if not db.connected(workspace_id, db_id):
        raise HTTPException(409, "No database connected")
    base = suggest_from_schema(db.get_schema(workspace_id, db_id=db_id))
    try:
        enriched = await llm_suggest_catalog(
            providers.get(workspace_id), db.schema_as_text(workspace_id, db_id)
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
