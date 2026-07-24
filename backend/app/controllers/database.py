from fastapi import HTTPException
from backend.app.database import sanitize_url, db_id_for
from backend.sample_data import ensure_sample_db, sample_db_path
import backend.app.pgdatabase as mdb
from backend.app.pgdatabase.connections import ConnectionKeyError
import logging
from backend.app.controllers.activity import log_activity

logger = logging.getLogger(__name__)

# A server-misconfiguration message, distinct from a transient save failure:
# every save fails the same way until an operator sets RECENT_CONNECTIONS_KEY,
# and reconnecting existing databases fails too — so "try again" would mislead.
_KEY_ERROR_MESSAGE = (
    "Connected, but saved connections aren't configured on the server "
    "(RECENT_CONNECTIONS_KEY is missing). Ask an administrator to set it — "
    "until then this database won't be remembered."
)

# Shown wherever a database needs a name — header, switcher, connect screen.
SAMPLE_ALIAS = "Sample Webshop"


def _call_with_db_id(fn, workspace_id, db_id):
    """Call a DatabaseManager accessor, tolerating single-database managers.

    Not every manager the app is handed takes a `db_id` (test doubles, and the
    single-connection manager this grew out of), so fall back to the one-argument
    form rather than requiring every implementation to grow the parameter.
    """
    if db_id is not None:
        try:
            return fn(workspace_id, db_id=db_id)
        except TypeError:
            pass
        try:
            return fn(workspace_id, db_id)
        except TypeError:
            pass
    return fn(workspace_id)


def _sample_db_id() -> str:
    """The db_id the sample database connects under, without building it.

    `db_id` is a hash of the connection URL, so this matches whatever
    `db.connect(ensure_sample_db())` would produce — letting us recognise a
    request for the sample before deciding whether to rebuild it.
    """
    return db_id_for(f"sqlite:///{sample_db_path().as_posix()}")


def _connect_sample_url(db, workspace_id):
    """Build (if needed) and connect the sample database. Returns its db_id."""
    url = ensure_sample_db()
    result = db.connect(workspace_id, url)
    if not result["ok"]:
        logger.warning("Could not connect the sample database: %s", result["error"])
        return None
    logger.info("Restored the sample database for workspace")
    return result["db_id"]


async def ensure_connection(db, workspace_id, db_id=None):
    """Return the db_id this workspace is connected to, reconnecting if needed.

    Live engines live in process memory, so a restart, a redeploy or a request
    landing on a different worker used to look exactly like the user having
    disconnected — they were bounced back to the connect screen with their
    database apparently gone. The credentials are already stored against the
    workspace, so re-establish the connection from them instead.

    Returns None when the workspace has no usable stored connection.
    """
    if not workspace_id:
        return None
    if _call_with_db_id(db.connected, workspace_id, db_id):
        # An explicitly requested database that is connected *is* the answer —
        # asking the manager to name it again would let a manager that ignores
        # db_id hand back the workspace default instead.
        return db_id or db.get_db_id(workspace_id)

    try:
        if db_id:
            conn = await mdb.get_recent_connection_by_db_id(workspace_id, db_id)
        else:
            conn = await mdb.get_latest_recent_connection(workspace_id)
    except RuntimeError:
        # Undecryptable stored credentials — the user has to re-add the
        # connection, and /api/reconnect reports that explicitly.
        logger.exception("Could not decrypt stored connection for workspace")
        conn = None

    if not conn or not conn.get("db_url"):
        # The sample database needs no stored credentials — it's regenerable
        # from the vendored dump. So when the request explicitly targets the
        # sample and there's nothing to restore, rebuild it rather than
        # reporting no database. This keeps "try the sample" working with zero
        # configuration, even if encryption isn't set up or the worker
        # restarted and lost the live connection. A blank db_id is left alone so
        # nothing silently auto-connects the sample.
        if db_id and db_id == _sample_db_id():
            return _connect_sample_url(db, workspace_id)
        return None

    result = db.connect(workspace_id, conn["db_url"])
    if not result["ok"]:
        logger.warning(
            "Could not restore connection %s: %s", conn["db_id"], result["error"]
        )
        return None
    logger.info("Restored stored connection %s from saved credentials", result["db_id"])
    return result["db_id"]


async def connect(db, kb, cfg, req_data, workspace_id=None, user_id=None):
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

    alias_name = getattr(req_data, "alias_name", None) or None
    result["alias_name"] = alias_name

    if workspace_id:
        try:
            await mdb.save_recent_connection(
                workspace_id=workspace_id,
                db_url=req_data.db_url,
                display_url=sanitize_url(req_data.db_url),
                dialect=result["dialect"],
                db_id=result["db_id"],
                table_count=result["tables"],
                alias_name=alias_name,
            )
            if not alias_name:
                # An existing row keeps its alias when we don't send one, so
                # read it back — the header and switcher label from this.
                saved = await mdb.get_recent_connection_by_db_id(workspace_id, db_id)
                result["alias_name"] = saved.get("alias_name") if saved else None
        except ConnectionKeyError:
            logger.exception("Recent-connection encryption key is not configured")
            result["save_error"] = _KEY_ERROR_MESSAGE
        except Exception:
            # The connection itself is live; only its persistence failed. Say so
            # rather than letting it quietly vanish from the connect screen.
            logger.exception("Failed to save recent connection")
            result["save_error"] = (
                "Connected, but this database couldn't be saved to your workspace — "
                "you may have to reconnect it next time."
            )
        await log_activity(
            workspace_id,
            user_id,
            "db.connected",
            "connection",
            str(result.get("db_id", "")),
            {"db_url": sanitize_url(req_data.db_url), "dialect": result.get("dialect")},
        )

    return result


async def connect_sample(db, kb, cfg, workspace_id=None, user_id=None):
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
    result["alias_name"] = SAMPLE_ALIAS

    if workspace_id:
        try:
            await mdb.save_recent_connection(
                workspace_id=workspace_id,
                db_url=url,
                display_url=sanitize_url(url),
                dialect=result["dialect"],
                db_id=result["db_id"],
                table_count=result["tables"],
                alias_name=SAMPLE_ALIAS,
            )
        except ConnectionKeyError:
            logger.exception("Recent-connection encryption key is not configured")
            result["save_error"] = _KEY_ERROR_MESSAGE
        except Exception:
            logger.exception("Failed to save recent connection")
            result["save_error"] = (
                "Connected, but the sample database couldn't be saved to your workspace."
            )
        await log_activity(
            workspace_id,
            user_id,
            "db.connected",
            "connection",
            str(result.get("db_id", "")),
            {"is_sample": True, "dialect": result.get("dialect")},
        )

    return result


async def disconnect(workspace_id, db, cfg, db_id=None, user_id=None):
    db.disconnect(workspace_id, db_id)
    await log_activity(
        workspace_id, user_id, "db.disconnected", "connection", db_id, {}
    )
    return {"ok": True}


async def get_schema(workspace_id, db, refresh, db_id=None):
    actual_db_id = await ensure_connection(db, workspace_id, db_id)
    if not actual_db_id:
        raise HTTPException(409, "No database connected")
    return db.get_schema(workspace_id, db_id=actual_db_id, refresh=refresh)
