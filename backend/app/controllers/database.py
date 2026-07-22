from fastapi import HTTPException
from backend.app.database import sanitize_url
from backend.sample_data import ensure_sample_db
import backend.app.pgdatabase as mdb
import logging

logger = logging.getLogger(__name__)


async def connect(db, kb, cfg, req_data, workspace_id=None):
    result = db.connect(workspace_id, req_data.db_url)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    db_id = result["db_id"]
    result["trust"] = await kb.trust_level(workspace_id, db_id)
    result["glossary"] = await kb.get_glossary(workspace_id, db_id)
    result["has_knowledge"] = (await kb.count_verified(workspace_id, db_id)) > 0
    result["starters"] = [
        v["question"] for v in (await kb.get_verified(workspace_id, db_id))[:6]
    ]

    if workspace_id:
        try:
            await mdb.save_recent_connection(
                workspace_id=workspace_id,
                db_url=req_data.db_url,
                display_url=sanitize_url(req_data.db_url),
                dialect=result["dialect"],
                db_id=result["db_id"],
                table_count=result["tables"],
                alias_name=getattr(req_data, "alias_name", None),
            )
        except Exception as e:
            logger.warning("Failed to save recent connection: %s", e)

    return result


async def connect_sample(db, kb, cfg, workspace_id=None):
    """
    Connect to the sample database and return its connection details and knowledge metadata.

    Parameters:
        workspace_id: Identifier of the workspace establishing the connection.

    Returns:
        dict: Connection details enriched with trust, glossary, knowledge availability, starter questions, and a sample-database flag.
    """
    url = ensure_sample_db()
    result = db.connect(workspace_id, url)
    if not result["ok"]:
        raise HTTPException(500, result["error"])

    dbid = db.get_db_id(workspace_id)
    await kb.seed_sample(workspace_id, dbid)

    result["trust"] = await kb.trust_level(workspace_id, dbid)
    result["glossary"] = await kb.get_glossary(workspace_id, dbid)
    result["has_knowledge"] = (await kb.count_verified(workspace_id, dbid)) > 0
    result["starters"] = [
        v["question"] for v in (await kb.get_verified(workspace_id, dbid))[:6]
    ]
    result["is_sample"] = True

    if workspace_id:
        try:
            await mdb.save_recent_connection(
                workspace_id=workspace_id,
                db_url=url,
                display_url=sanitize_url(url),
                dialect=result["dialect"],
                db_id=result["db_id"],
                table_count=result["tables"],
            )
        except Exception as e:
            logger.warning("Failed to save recent connection: %s", e)

    return result


async def disconnect(workspace_id, db, cfg, db_id=None):
    db.disconnect(workspace_id, db_id)
    return {"ok": True}


async def get_schema(workspace_id, db, refresh, db_id=None):
    if not db.connected(workspace_id, db_id):
        raise HTTPException(409, "No database connected")
    return db.get_schema(workspace_id, db_id=db_id, refresh=refresh)
