from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool
from backend.app.dependencies import get_current_user
import backend.app.mongodatabase as mdb

router = APIRouter()


@router.get("/api/connections")
async def get_connections(user_token=Depends(get_current_user)):
    connections = await run_in_threadpool(
        mdb.get_recent_connections, user_token["user_id"]
    )
    # Strip full db_url from response — frontend doesn't need it for display
    for c in connections:
        c.pop("db_url", None)
    return {"connections": connections}


@router.delete("/api/connections/{connection_id}")
async def delete_connection(connection_id: str, user_token=Depends(get_current_user)):
    deleted = await run_in_threadpool(
        mdb.delete_recent_connection, user_token["user_id"], connection_id
    )
    return {"ok": deleted}
