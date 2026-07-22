"""Shared serialization and UUID utilities."""

import uuid
from datetime import datetime


def _to_uuid(val: str | uuid.UUID) -> uuid.UUID:
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(val)


def serialize_doc(doc):
    if doc is None:
        return None
    out = doc.copy()
    out["_id"] = str(out.pop("id", ""))
    if "user_id" in out and out["user_id"] is not None:
        out["user_id"] = str(out["user_id"])
    if "workspace_id" in out and out["workspace_id"] is not None:
        out["workspace_id"] = str(out["workspace_id"])
    if "conversation_id" in out and out["conversation_id"] is not None:
        out["conversation_id"] = str(out["conversation_id"])
    for key in ("created_at", "updated_at", "timestamp", "connected_at"):
        if key in out and isinstance(out[key], datetime):
            out[key] = out[key].isoformat()
    return out
