import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from backend.app.dependencies import get_current_workspace, get_current_user
import backend.app.controllers.dashboards as ctrl

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/dashboards", tags=["dashboards"])


class CreateDashboardReq(BaseModel):
    name: str
    description: Optional[str] = None


class UpdateDashboardReq(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddPanelReq(BaseModel):
    saved_query_id: Optional[str] = None
    title: Optional[str] = None
    visualization_type: Optional[str] = None
    viz_config: Optional[dict] = None
    position: Optional[dict] = None


class UpdatePanelReq(BaseModel):
    title: Optional[str] = None
    visualization_type: Optional[str] = None
    viz_config: Optional[dict] = None
    position: Optional[dict] = None


class BatchUpdatePanelPositionReq(BaseModel):
    updates: List[Dict[str, Any]]  # {"id": panel_id, "position": {...}}


@router.get("")
async def list_dashboards(workspace=Depends(get_current_workspace)):
    try:
        dashboards = await ctrl.list_dashboards(workspace["workspace_id"])
        return JSONResponse({"dashboards": dashboards})
    except Exception:
        log.exception("Failed to list dashboards")
        raise HTTPException(500, "Failed to load dashboards")


@router.post("")
async def create_dashboard(
    req: CreateDashboardReq,
    workspace=Depends(get_current_workspace),
    user=Depends(get_current_user),
):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can create dashboards")

        dash = await ctrl.create_dashboard(
            workspace["workspace_id"], user["user_id"], req.name, req.description
        )
        return JSONResponse(dash)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to create dashboard")
        raise HTTPException(500, "Failed to create dashboard")


@router.get("/{dashboard_id}")
async def get_dashboard(dashboard_id: str, workspace=Depends(get_current_workspace)):
    try:
        dash = await ctrl.get_dashboard(workspace["workspace_id"], dashboard_id)
        if not dash:
            raise HTTPException(404, "Dashboard not found")
        return JSONResponse(dash)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get dashboard")
        raise HTTPException(500, "Failed to load dashboard")


@router.patch("/{dashboard_id}")
async def update_dashboard(
    dashboard_id: str, req: UpdateDashboardReq, workspace=Depends(get_current_workspace)
):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can edit dashboards")

        success = await ctrl.update_dashboard(
            workspace["workspace_id"], dashboard_id, req.model_dump(exclude_unset=True)
        )
        if not success:
            raise HTTPException(404, "Dashboard not found")
        return JSONResponse({"message": "Updated successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update dashboard")
        raise HTTPException(500, "Failed to update dashboard")


@router.delete("/{dashboard_id}")
async def delete_dashboard(dashboard_id: str, workspace=Depends(get_current_workspace)):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can delete dashboards")

        success = await ctrl.delete_dashboard(workspace["workspace_id"], dashboard_id)
        if not success:
            raise HTTPException(404, "Dashboard not found")
        return JSONResponse({"message": "Deleted successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete dashboard")
        raise HTTPException(500, "Failed to delete dashboard")


@router.get("/{dashboard_id}/data")
async def get_dashboard_data(
    dashboard_id: str, request: Request, workspace=Depends(get_current_workspace)
):
    try:
        db_manager = request.app.state.db
        results = await ctrl.execute_dashboard_queries(
            workspace["workspace_id"], dashboard_id, db_manager
        )
        if results is None:
            raise HTTPException(404, "Dashboard not found")
        return JSONResponse(results)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to execute dashboard queries")
        raise HTTPException(500, "Failed to execute dashboard queries")


# --- Panels ---


@router.post("/{dashboard_id}/panels")
async def add_panel(
    dashboard_id: str, req: AddPanelReq, workspace=Depends(get_current_workspace)
):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can edit dashboards")

        panel = await ctrl.add_panel(dashboard_id, req.model_dump(exclude_unset=True))
        return JSONResponse(panel)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to add panel")
        raise HTTPException(500, "Failed to add panel")


@router.patch("/{dashboard_id}/panels/batch")
async def batch_update_panels(
    dashboard_id: str,
    req: BatchUpdatePanelPositionReq,
    workspace=Depends(get_current_workspace),
):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can edit dashboards")

        await ctrl.update_panels_batch(
            dashboard_id, req.model_dump(exclude_unset=True)["updates"]
        )
        return JSONResponse({"message": "Updated successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to batch update panels")
        raise HTTPException(500, "Failed to update panels")


@router.patch("/{dashboard_id}/panels/{panel_id}")
async def update_panel(
    dashboard_id: str,
    panel_id: str,
    req: UpdatePanelReq,
    workspace=Depends(get_current_workspace),
):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can edit dashboards")

        success = await ctrl.update_panel(
            dashboard_id, panel_id, req.model_dump(exclude_unset=True)
        )
        if not success:
            raise HTTPException(404, "Panel not found")
        return JSONResponse({"message": "Updated successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update panel")
        raise HTTPException(500, "Failed to update panel")


@router.delete("/{dashboard_id}/panels/{panel_id}")
async def delete_panel(
    dashboard_id: str, panel_id: str, workspace=Depends(get_current_workspace)
):
    try:
        if workspace["role"] not in ["admin", "owner"]:
            raise HTTPException(403, "Only admins can edit dashboards")

        success = await ctrl.delete_panel(dashboard_id, panel_id)
        if not success:
            raise HTTPException(404, "Panel not found")
        return JSONResponse({"message": "Deleted successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete panel")
        raise HTTPException(500, "Failed to delete panel")
