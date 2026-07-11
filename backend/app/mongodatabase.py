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
mongouri = os.getenv("MONGO_URI")
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


def save_query(user_id, question, sql, result, confidence):
    history = db["query_history"]
    doc = {
        "user_id": str(user_id),
        "question": question,
        "sql": sql,
        "result": result,
        "confidence": confidence,
        "timestamp": datetime.utcnow(),
    }
    history.insert_one(doc)


def get_query_history(user_id, limit=20):
    history = db["query_history"]
    cursor = history.find({"user_id": str(user_id)}).sort("timestamp", -1).limit(limit)
    return [serialize_doc(doc) for doc in cursor]


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
