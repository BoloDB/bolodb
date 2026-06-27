import os
from bson import ObjectId
from bson.errors import InvalidId
from dotenv import load_dotenv
from pymongo import MongoClient
from datetime import datetime
from backend.app.models.user import UserInDB

load_dotenv()
mongouri = os.getenv("MONGO_URI")
client = MongoClient(mongouri)
db = client["bolodb"]


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
