import base64
import hashlib
import os
from datetime import datetime

from cryptography.fernet import Fernet, InvalidToken
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient

from backend.app.models.user import UserInDB
from backend.app.config import CONFIG_DIR

load_dotenv()
mongouri = os.getenv("MONGO_URI") or "mongodb://localhost:27017"
client = MongoClient(mongouri)
db = client["bolodb"]

_CONNECTIONS_KEY_FILE = CONFIG_DIR / "connections.key"


def _recent_connection_cipher():
    """Derive a Fernet cipher for encrypting stored database URLs.

    Uses RECENT_CONNECTIONS_KEY env var if set; otherwise generates and
    persists a key file at ~/.bolodb/connections.key.  Falls back to a
    fresh key only for backward-compat decryption of legacy records.
    """
    secret = os.getenv("RECENT_CONNECTIONS_KEY")
    if secret:
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
        return Fernet(key), None

    # Try to load or create a persisted key file.
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if _CONNECTIONS_KEY_FILE.exists():
        persisted = _CONNECTIONS_KEY_FILE.read_text().strip()
        key = base64.urlsafe_b64encode(hashlib.sha256(persisted.encode()).digest())
        return Fernet(key), None

    # Generate a new key and persist it for next time.
    new_secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
    _CONNECTIONS_KEY_FILE.write_text(new_secret)
    key = base64.urlsafe_b64encode(hashlib.sha256(new_secret.encode()).digest())
    return Fernet(key), None


def _encrypt_connection_url(db_url):
    return _recent_connection_cipher()[0].encrypt(db_url.encode()).decode()


def _decrypt_connection_url(value):
    try:
        return _recent_connection_cipher()[0].decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        # Backward compatibility: try the legacy JWT_SECRET-based key.
        jwt_secret = os.getenv("JWT_SECRET")
        if jwt_secret:
            try:
                legacy_key = base64.urlsafe_b64encode(
                    hashlib.sha256(jwt_secret.encode()).digest()
                )
                return Fernet(legacy_key).decrypt(value.encode()).decode()
            except (InvalidToken, ValueError, TypeError):
                pass
        # Last resort: treat as plaintext (older records stored unencrypted).
        return value


def get_user_by_email(email):
    users = db["users"]
    user_data = users.find_one({"email": email})
    return user_data


def create_user(user_data: UserInDB):
    users = db["users"]
    return users.insert_one(
        user_data.model_dump(mode="json", by_alias=True, exclude_none=True)
    )


def get_user_by_id(user_id):
    users = db["users"]
    try:
        oid = ObjectId(user_id)
    except (InvalidId, TypeError):
        return None
    return users.find_one({"_id": oid})


def update_user(user_filter, update_op):
    users = db["users"]
    users.update_one(user_filter, update_op)
    return True


def serialize_doc(doc):
    if doc is None:
        return None
    doc["_id"] = str(doc["_id"])
    for k, v in doc.items():
        if isinstance(v, datetime):
            doc[k] = v.isoformat()
    return doc


def save_query(
    user_id, question, sql, result, confidence, conversation_id=None, restatement=""
):
    history = db["query_history"]
    doc = {
        "user_id": str(user_id),
        "question": question,
        "sql": sql,
        "result": result,
        "confidence": confidence,
        "restatement": restatement,
        "timestamp": datetime.utcnow(),
    }
    if conversation_id:
        doc["conversation_id"] = str(conversation_id)
    history.insert_one(doc)


def get_query_history(user_id, limit=100):
    history = db["query_history"]
    cursor = history.find({"user_id": str(user_id)}).sort("timestamp", -1).limit(limit)
    return [serialize_doc(doc) for doc in cursor]


def get_query_stats(user_id):
    """Aggregate stats from query history for dashboard charts."""
    history = db["query_history"]
    user_filter = {"user_id": str(user_id)}
    total = history.count_documents(user_filter)

    confidence_pipeline = [
        {"$match": user_filter},
        {
            "$group": {
                "_id": {"$toLower": {"$ifNull": ["$confidence", "low"]}},
                "count": {"$sum": 1},
            }
        },
    ]
    confidence_counts = {}
    for doc in history.aggregate(confidence_pipeline):
        key = (doc["_id"] or "low").capitalize()
        confidence_counts[key] = doc["count"]

    day_pipeline = [
        {"$match": user_filter},
        {
            "$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": -1}},
        {"$limit": 90},
        {"$sort": {"_id": 1}},
    ]
    daily = [
        {"date": doc["_id"], "count": doc["count"]}
        for doc in history.aggregate(day_pipeline)
    ]

    sql_pipeline = [
        {"$match": user_filter},
        {"$sort": {"timestamp": -1}},
        {"$project": {"sql": 1}},
        {"$limit": 200},
    ]
    table_usage: dict[str, int] = {}
    for doc in history.aggregate(sql_pipeline):
        sql = (doc.get("sql") or "").lower()
        for keyword in ("from ", "join "):
            idx = 0
            while True:
                pos = sql.find(keyword, idx)
                if pos == -1:
                    break
                start = pos + len(keyword)
                end = start
                while end < len(sql) and sql[end] not in (
                    " ",
                    "\n",
                    "\t",
                    ";",
                    "(",
                    ",",
                ):
                    end += 1
                tbl = sql[start:end].strip().strip('"').strip("'").strip("`")
                if (
                    tbl
                    and not tbl.startswith("(")
                    and tbl
                    not in (
                        "select",
                        "where",
                        "on",
                        "and",
                        "or",
                        "set",
                        "into",
                        "values",
                    )
                ):
                    table_usage[tbl] = table_usage.get(tbl, 0) + 1
                idx = end
    top_tables = sorted(table_usage.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_queries": total,
        "confidence": {
            "High": confidence_counts.get("High", 0),
            "Medium": confidence_counts.get("Medium", 0),
            "Low": confidence_counts.get("Low", 0),
        },
        "daily_activity": daily,
        "top_tables": [{"table": t, "count": c} for t, c in top_tables],
    }


def delete_history_entry(user_id, entry_id):
    history = db["query_history"]
    try:
        oid = ObjectId(entry_id)
    except (InvalidId, TypeError):
        return False
    res = history.delete_one({"_id": oid, "user_id": str(user_id)})
    return res.deleted_count > 0


def clear_history(user_id):
    history = db["query_history"]
    history.delete_many({"user_id": str(user_id)})


def save_recent_connection(user_id, db_url, display_url, dialect, db_id, table_count):
    """Upsert a recent connection for this user (keyed by user_id + db_id)."""
    connections = db["recent_connections"]
    connections.update_one(
        {"user_id": str(user_id), "db_id": db_id},
        {
            "$set": {
                "user_id": str(user_id),
                "db_url": _encrypt_connection_url(db_url),
                "display_url": display_url,
                "dialect": dialect,
                "db_id": db_id,
                "table_count": table_count,
                "connected_at": datetime.utcnow(),
            }
        },
        upsert=True,
    )


def get_recent_connections(user_id, limit=5):
    connections = db["recent_connections"]
    cursor = (
        connections.find({"user_id": str(user_id)})
        .sort("connected_at", -1)
        .limit(limit)
    )
    return [serialize_doc(doc) for doc in cursor]


def delete_recent_connection(user_id, connection_id):
    connections = db["recent_connections"]
    try:
        oid = ObjectId(connection_id)
    except (InvalidId, TypeError):
        return False
    res = connections.delete_one({"_id": oid, "user_id": str(user_id)})
    return res.deleted_count > 0


def get_recent_connection_by_db_id(user_id, db_id):
    """Retrieve a specific recent connection by db_id for this user."""
    connections = db["recent_connections"]
    doc = connections.find_one({"user_id": str(user_id), "db_id": db_id})
    if doc and "db_url" in doc:
        doc["db_url"] = _decrypt_connection_url(doc["db_url"])
    return serialize_doc(doc) if doc else None


# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------


def create_conversation(user_id, title="", database_id=None):
    conversations = db["conversations"]
    now = datetime.utcnow()
    doc = {
        "user_id": str(user_id),
        "title": title,
        "database_id": database_id,
        "created_at": now,
        "updated_at": now,
    }
    result = conversations.insert_one(doc)
    doc["_id"] = result.inserted_id
    return serialize_doc(doc)


def conversation_owned_by(user_id, conversation_id):
    """Return True if this conversation exists and belongs to the user.

    Cheap ownership check used before linking a new turn to a conversation, so
    a caller can't attach its query to (or bump) another user's conversation.
    """
    try:
        oid = ObjectId(conversation_id)
    except (InvalidId, TypeError):
        return False
    return (
        db["conversations"].find_one({"_id": oid, "user_id": str(user_id)}, {"_id": 1})
        is not None
    )


def get_conversations(user_id):
    conversations = db["conversations"]
    history = db["query_history"]
    cursor = conversations.find({"user_id": str(user_id)}).sort("updated_at", -1)
    results = []
    for conv in cursor:
        conv = serialize_doc(conv)
        # Count turns and get last question — scope to this user so a turn that
        # was mislinked to this conversation id can't inflate the count.
        turn_count = history.count_documents(
            {"conversation_id": conv["_id"], "user_id": str(user_id)}
        )
        last_turn = history.find_one(
            {"conversation_id": conv["_id"], "user_id": str(user_id)},
            sort=[("timestamp", -1)],
        )
        conv["turn_count"] = turn_count
        conv["last_question"] = last_turn["question"] if last_turn else ""
        results.append(conv)
    return results


def get_conversation(user_id, conversation_id):
    conversations = db["conversations"]
    try:
        oid = ObjectId(conversation_id)
    except (InvalidId, TypeError):
        return None
    conv = conversations.find_one({"_id": oid, "user_id": str(user_id)})
    if not conv:
        return None
    conv = serialize_doc(conv)
    # Fetch turns — scope to this user as well as the conversation so a turn
    # another account mislinked to this id can never surface here.
    history = db["query_history"]
    cursor = history.find(
        {"conversation_id": conv["_id"], "user_id": str(user_id)}
    ).sort("timestamp", 1)
    conv["turns"] = [serialize_doc(doc) for doc in cursor]
    return conv


def rename_conversation(user_id, conversation_id, title):
    conversations = db["conversations"]
    try:
        oid = ObjectId(conversation_id)
    except (InvalidId, TypeError):
        return False
    result = conversations.update_one(
        {"_id": oid, "user_id": str(user_id)},
        {"$set": {"title": title, "updated_at": datetime.utcnow()}},
    )
    return result.modified_count > 0


def touch_conversation(conversation_id):
    """Update the updated_at timestamp (called after each new turn)."""
    conversations = db["conversations"]
    try:
        oid = ObjectId(conversation_id)
    except (InvalidId, TypeError):
        return
    conversations.update_one(
        {"_id": oid},
        {"$set": {"updated_at": datetime.utcnow()}},
    )


def delete_conversation(user_id, conversation_id):
    conversations = db["conversations"]
    history = db["query_history"]
    try:
        oid = ObjectId(conversation_id)
    except (InvalidId, TypeError):
        return False
    result = conversations.delete_one({"_id": oid, "user_id": str(user_id)})
    if result.deleted_count > 0:
        # Cascade delete turns
        history.delete_many({"conversation_id": conversation_id})
        return True
    return False


def clear_conversations(user_id):
    conversations = db["conversations"]
    history = db["query_history"]
    conv_cursor = conversations.find({"user_id": str(user_id)}, {"_id": 1})
    conv_ids = [str(c["_id"]) for c in conv_cursor]
    conversations.delete_many({"user_id": str(user_id)})
    if conv_ids:
        history.delete_many({"conversation_id": {"$in": conv_ids}})
