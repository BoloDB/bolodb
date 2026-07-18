from fastapi import HTTPException
from backend.app.database import sanitize_url
from backend.sample_data import ensure_sample_db
import backend.app.pgdatabase as mdb
import logging

logger = logging.getLogger(__name__)


async def connect(db, kb, cfg, req_data, user_id=None):
    """
    Connects to a database and enriches the connection details with knowledge-base information.

    Parameters:
        req_data: Request data containing the database URL.
        user_id: Optional identifier of the user establishing the connection.

    Returns:
        The connection result with trust, glossary, knowledge availability, and starter questions.

    Raises:
        HTTPException: If the database connection fails.
    """
    result = db.connect(user_id, req_data.db_url)
    if not result["ok"]:
        raise HTTPException(400, result["error"])
    db_id = result["db_id"]
    result["trust"] = await kb.trust_level(user_id, db_id)
    result["glossary"] = await kb.get_glossary(user_id, db_id)
    result["has_knowledge"] = (await kb.count_verified(user_id, db_id)) > 0
    result["starters"] = [
        v["question"] for v in (await kb.get_verified(user_id, db_id))[:6]
    ]

    if user_id:
        try:
            await mdb.save_recent_connection(
                user_id=user_id,
                db_url=req_data.db_url,
                display_url=sanitize_url(req_data.db_url),
                dialect=result["dialect"],
                db_id=result["db_id"],
                table_count=result["tables"],
            )
        except Exception as e:
            logger.warning("Failed to save recent connection: %s", e)

    return result


async def connect_sample(db, kb, cfg, user_id=None):
    """
    Connect to the sample database and return its connection details and knowledge metadata.

    Parameters:
        user_id: Optional identifier of the user establishing the connection.

    Returns:
        dict: Connection details enriched with trust, glossary, knowledge availability, starter questions, and a sample-database flag.
    """
    url = ensure_sample_db()
    result = db.connect(user_id, url)
    if not result["ok"]:
        raise HTTPException(500, result["error"])

    dbid = db.get_db_id(user_id)
    await kb.seed_sample(user_id, dbid)

    result["trust"] = await kb.trust_level(user_id, dbid)
    result["glossary"] = await kb.get_glossary(user_id, dbid)
    result["has_knowledge"] = (await kb.count_verified(user_id, dbid)) > 0
    result["starters"] = [
        v["question"] for v in (await kb.get_verified(user_id, dbid))[:6]
    ]
    result["is_sample"] = True

    if user_id:
        try:
            await mdb.save_recent_connection(
                user_id=user_id,
                db_url=url,
                display_url=sanitize_url(url),
                dialect=result["dialect"],
                db_id=result["db_id"],
                table_count=result["tables"],
            )
        except Exception as e:
            logger.warning("Failed to save recent connection: %s", e)

    return result


async def disconnect(user_id, db, cfg):
    db.disconnect(user_id)
    return {"ok": True}


async def get_schema(user_id, db, refresh):
    if not db.connected(user_id):
        raise HTTPException(409, "No database connected")
    return db.get_schema(user_id, refresh=refresh)
