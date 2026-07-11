import base64
import hashlib
import json
import os
import threading
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from dotenv import load_dotenv

from backend.app.models.user import UserInDB

load_dotenv()

# ── Decide: use MongoDB or local JSON store ──
mongouri = os.getenv("MONGO_URI")
_use_mongo = bool(mongouri and str(mongouri).strip())

if _use_mongo:
    from pymongo import MongoClient
    client = MongoClient(mongouri, serverSelectionTimeoutMS=3000)
    db = client["bolodb"]
else:
    # ── Local JSON file store ──
    _lock = threading.Lock()
    _data_path = Path(os.path.expanduser("~")) / ".bolodb" / "local_data.json"
    _data_path.parent.mkdir(parents=True, exist_ok=True)

    def _load():
        if _data_path.exists():
            try:
                return json.loads(_data_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"users": {}, "query_history": [], "recent_connections": []}

    def _save(data):
        _data_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def _next_id():
        import secrets
        return secrets.token_hex(12)


def _recent_connection_cipher():
    secret = os.getenv("RECENT_CONNECTIONS_KEY") or os.getenv(
        "JWT_SECRET", "RANDOM-SECRET"
    )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


def _encrypt_connection_url(db_url):
    return _recent_connection_cipher().encrypt(db_url.encode()).decode()


def _decrypt_connection_url(value):
    try:
        return _recent_connection_cipher().decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, TypeError):
        return value


def get_user_by_email(email):
    if _use_mongo:
        return db["users"].find_one({"email": email})
    with _lock:
        data = _load()
        for uid, u in data["users"].items():
            if u.get("email") == email:
                return {**u, "_id": uid}
        return None


def get_user_by_google_id(google_id):
    if _use_mongo:
        return db["users"].find_one({"google_id": google_id})
    with _lock:
        data = _load()
        for uid, u in data["users"].items():
            if u.get("google_id") == google_id:
                return {**u, "_id": uid}
        return None


def create_user(user_data: UserInDB):
    if _use_mongo:
        return db["users"].insert_one(
            user_data.model_dump(mode="json", by_alias=True, exclude_none=True)
        )
    with _lock:
        data = _load()
        uid = _next_id()
        doc = user_data.model_dump(mode="json", by_alias=True, exclude_none=True)
        doc["_id"] = uid
        data["users"][uid] = doc
        _save(data)
        return type("InsertResult", (), {"inserted_id": uid})()


def get_user_by_id(user_id):
    if _use_mongo:
        from bson import ObjectId, errors as bson_errors
        try:
            oid = ObjectId(user_id)
        except (bson_errors.InvalidId, TypeError):
            return None
        return db["users"].find_one({"_id": oid})
    with _lock:
        data = _load()
        u = data["users"].get(user_id)
        return {**u, "_id": user_id} if u else None


def update_user(user_filter, update_op):
    if _use_mongo:
        db["users"].update_one(user_filter, update_op)
        return True
    with _lock:
        data = _load()
        user_id = user_filter.get("_id")
        if isinstance(user_id, dict):
            user_id = user_id.get("$eq")
        if user_id and str(user_id) in data["users"]:
            set_fields = update_op.get("$set", {})
            data["users"][str(user_id)].update(set_fields)
            _save(data)
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
    if _use_mongo:
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
        return
    with _lock:
        data = _load()
        data["query_history"].insert(0, {
            "_id": _next_id(),
            "user_id": str(user_id),
            "question": question,
            "sql": sql,
            "result": result,
            "confidence": confidence,
            "timestamp": datetime.utcnow().isoformat(),
        })
        _save(data)


def get_query_history(user_id, limit=20):
    if _use_mongo:
        history = db["query_history"]
        cursor = history.find({"user_id": str(user_id)}).sort("timestamp", -1).limit(limit)
        return [serialize_doc(doc) for doc in cursor]
    with _lock:
        data = _load()
        entries = [e for e in data["query_history"] if e.get("user_id") == str(user_id)]
        return entries[:limit]


def delete_history_entry(user_id, entry_id):
    if _use_mongo:
        from bson import ObjectId, errors as bson_errors
        try:
            oid = ObjectId(entry_id)
        except (bson_errors.InvalidId, TypeError):
            return False
        res = db["history"].delete_one({"_id": oid, "user_id": str(user_id)})
        return res.deleted_count > 0
    with _lock:
        data = _load()
        before = len(data["query_history"])
        data["query_history"] = [
            e for e in data["query_history"]
            if not (e.get("_id") == entry_id and e.get("user_id") == str(user_id))
        ]
        _save(data)
        return len(data["query_history"]) < before


def clear_history(user_id):
    if _use_mongo:
        db["query_history"].delete_many({"user_id": str(user_id)})
        return
    with _lock:
        data = _load()
        data["query_history"] = [
            e for e in data["query_history"] if e.get("user_id") != str(user_id)
        ]
        _save(data)


def save_recent_connection(user_id, db_url, display_url, dialect, db_id, table_count):
    if _use_mongo:
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
        return
    with _lock:
        data = _load()
        existing = None
        for i, c in enumerate(data["recent_connections"]):
            if c.get("user_id") == str(user_id) and c.get("db_id") == db_id:
                existing = i
                break
        doc = {
            "_id": _next_id(),
            "user_id": str(user_id),
            "db_url": _encrypt_connection_url(db_url),
            "display_url": display_url,
            "dialect": dialect,
            "db_id": db_id,
            "table_count": table_count,
            "connected_at": datetime.utcnow().isoformat(),
        }
        if existing is not None:
            data["recent_connections"][existing] = doc
        else:
            data["recent_connections"].append(doc)
        _save(data)


def get_recent_connections(user_id, limit=5):
    if _use_mongo:
        connections = db["recent_connections"]
        cursor = (
            connections.find({"user_id": str(user_id)})
            .sort("connected_at", -1)
            .limit(limit)
        )
        return [serialize_doc(doc) for doc in cursor]
    with _lock:
        data = _load()
        entries = [e for e in data["recent_connections"] if e.get("user_id") == str(user_id)]
        entries.sort(key=lambda x: x.get("connected_at", ""), reverse=True)
        return entries[:limit]


def delete_recent_connection(user_id, connection_id):
    if _use_mongo:
        from bson import ObjectId, errors as bson_errors
        try:
            oid = ObjectId(connection_id)
        except (bson_errors.InvalidId, TypeError):
            return False
        res = db["recent_connections"].delete_one({"_id": oid, "user_id": str(user_id)})
        return res.deleted_count > 0
    with _lock:
        data = _load()
        before = len(data["recent_connections"])
        data["recent_connections"] = [
            c for c in data["recent_connections"]
            if not (c.get("_id") == connection_id and c.get("user_id") == str(user_id))
        ]
        _save(data)
        return len(data["recent_connections"]) < before


def get_recent_connection_by_db_id(user_id, db_id):
    if _use_mongo:
        connections = db["recent_connections"]
        doc = connections.find_one({"user_id": str(user_id), "db_id": db_id})
        if doc and "db_url" in doc:
            doc["db_url"] = _decrypt_connection_url(doc["db_url"])
        return serialize_doc(doc) if doc else None
    with _lock:
        data = _load()
        for c in data["recent_connections"]:
            if c.get("user_id") == str(user_id) and c.get("db_id") == db_id:
                c = {**c}
                if "db_url" in c:
                    c["db_url"] = _decrypt_connection_url(c["db_url"])
                return c
        return None
