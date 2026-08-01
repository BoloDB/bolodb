"""Shared serialization and UUID utilities."""

import uuid
from datetime import datetime

_UUID_KEYS = (
    "id",
    "user_id",
    "workspace_id",
    "conversation_id",
    "dashboard_id",
    "saved_query_id",
    "database_id",
    "created_by",
    "invited_by",
    "actor_id",
    "schedule_id",
)

_DATETIME_KEYS = (
    "created_at",
    "updated_at",
    "timestamp",
    "connected_at",
    "joined_at",
    "starts_at",
    "ends_at",
    "next_run_at",
    "last_run_at",
    "started_at",
    "finished_at",
)


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(val)


def serialize_doc(doc):
    if doc is None:
        return None
    out = {k: v for k, v in doc.items() if not k.startswith("_")}
    raw_id = out.pop("id", None)
    if raw_id is not None:
        sid = str(raw_id)
        out["_id"] = sid
        out["id"] = sid  # dual keys for API/frontend compatibility
    for key in _UUID_KEYS:
        if key in out and out[key] is not None and key != "id":
            out[key] = str(out[key])
    for key in _DATETIME_KEYS:
        if key in out and isinstance(out[key], datetime):
            out[key] = out[key].isoformat()
    return out
