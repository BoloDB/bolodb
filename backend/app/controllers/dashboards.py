import logging
import asyncio
from backend.app.pgdatabase import dashboards as mdb_dash
from backend.app.pgdatabase import saved_queries as mdb_sq

log = logging.getLogger(__name__)

# --- Saved Queries ---


async def create_saved_query(workspace_id: str, created_by: str, data: dict):
    return await mdb_sq.create_saved_query(workspace_id, created_by, **data)


async def list_saved_queries(workspace_id: str, limit: int = 50, offset: int = 0):
    return await mdb_sq.list_saved_queries(workspace_id, limit, offset)


async def get_saved_query(workspace_id: str, query_id: str):
    return await mdb_sq.get_saved_query(workspace_id, query_id)


async def update_saved_query(workspace_id: str, query_id: str, data: dict):
    return await mdb_sq.update_saved_query(workspace_id, query_id, **data)


async def delete_saved_query(workspace_id: str, query_id: str):
    return await mdb_sq.delete_saved_query(workspace_id, query_id)


# --- Dashboards ---


async def create_dashboard(
    workspace_id: str, created_by: str, name: str, description: str = None
):
    return await mdb_dash.create_dashboard(workspace_id, created_by, name, description)


async def list_dashboards(workspace_id: str):
    return await mdb_dash.list_dashboards(workspace_id)


async def get_dashboard(workspace_id: str, dashboard_id: str):
    return await mdb_dash.get_dashboard(workspace_id, dashboard_id)


async def update_dashboard(workspace_id: str, dashboard_id: str, data: dict):
    return await mdb_dash.update_dashboard(workspace_id, dashboard_id, **data)


async def delete_dashboard(workspace_id: str, dashboard_id: str):
    return await mdb_dash.delete_dashboard(workspace_id, dashboard_id)


# --- Panels ---


async def add_panel(workspace_id: str, dashboard_id: str, data: dict):
    return await mdb_dash.add_panel(workspace_id, dashboard_id, **data)


async def update_panel(workspace_id: str, dashboard_id: str, panel_id: str, data: dict):
    return await mdb_dash.update_panel(workspace_id, dashboard_id, panel_id, **data)


async def delete_panel(workspace_id: str, dashboard_id: str, panel_id: str):
    return await mdb_dash.delete_panel(workspace_id, dashboard_id, panel_id)


async def update_panels_batch(workspace_id: str, dashboard_id: str, updates: list):
    return await mdb_dash.update_panels_batch(workspace_id, dashboard_id, updates)


# --- Execution ---

_NUMERIC_TYPES = ("integer", "float", "numeric", "number")


def _normalize_columns(columns, rows):
    """
    Return columns as [{"name", "type_name"}] whatever shape they were stored in.

    Saved queries persist `columns` as a plain list of names (that is what the
    chat turn carries), while a fresh execution only knows the names too. The
    dashboard renderer picks its value axis by type, so infer the type from the
    values actually returned rather than handing back bare strings.
    """
    out = []
    for col in columns or []:
        if isinstance(col, dict):
            name = col.get("name")
            type_name = col.get("type_name")
        else:
            name = col
            type_name = None
        if name is None:
            continue
        if not type_name:
            type_name = _infer_type(name, rows)
        out.append({"name": name, "type_name": type_name})
    return out


def _infer_type(name, rows):
    for row in (rows or [])[:20]:
        val = row.get(name) if isinstance(row, dict) else None
        if val is None or val == "":
            continue
        if isinstance(val, bool):
            return "string"
        if isinstance(val, int):
            return "integer"
        if isinstance(val, float):
            return "float"
        try:
            float(str(val).replace(",", "").strip())
            return "float"
        except (TypeError, ValueError):
            return "string"
    return "string"


async def execute_dashboard_queries(workspace_id: str, dashboard_id: str, db_manager):
    dash = await mdb_dash.get_dashboard(workspace_id, dashboard_id)
    if not dash:
        return None

    panel_sq_ids = []
    for p in dash["panels"]:
        if p.get("saved_query_id"):
            panel_sq_ids.append(p["saved_query_id"])

    results = {}
    sem = asyncio.Semaphore(5)

    async def run_sq(sq_id):
        sq = await mdb_sq.get_saved_query(workspace_id, str(sq_id))
        if not sq:
            return None
        sq_key = str(sq.get("id") or sq.get("_id") or sq_id)
        try:
            sql = sq.get("sql")
            target_db_id = sq.get("database_id")
            if sql:
                async with sem:
                    data = await asyncio.to_thread(
                        db_manager.execute, workspace_id, sql, target_db_id
                    )

                # data comes back as dict: {"columns": [], "rows": [{}], "error": ""}
                if data.get("error"):
                    return {"id": sq_key, "error": data["error"]}

                # Charts assume array of objects keyed by column name
                rows = data.get("rows", [])[:500]
                # Trust the live result's column list — a saved query's stored
                # columns can be stale if the underlying SQL was edited.
                return {
                    "id": sq_key,
                    "rows": rows,
                    "columns": _normalize_columns(data.get("columns", []), rows),
                }
        except Exception as e:
            log.warning(f"Dashboard panel query failed sq_id={sq_id}: {e}")
            return {"id": sq_key, "error": str(e)}
        return None

    tasks = [run_sq(sq_id) for sq_id in set(panel_sq_ids)]
    fetched = await asyncio.gather(*tasks)

    for res in fetched:
        if res:
            results[res["id"]] = res

    return results
