import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import backend.app.controllers.schedules as ctrl
from backend.app.controllers.activity import log_activity
from backend.app.dependencies import get_current_user, require_permission
from backend.app.ratelimit import limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/schedules", tags=["schedules"])


class CreateScheduleReq(BaseModel):
    name: str
    sql: str
    cron: str
    recipients: list[str] = []
    description: Optional[str] = None
    question: Optional[str] = None
    database_id: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    is_active: bool = True
    subject_template: Optional[str] = None
    intro: Optional[str] = None
    footer: Optional[str] = None
    display_columns: Optional[list[str]] = None
    max_rows: int = 50
    attach_csv: bool = False
    send_condition: str = "always"
    condition_value: Optional[int] = None


class UpdateScheduleReq(BaseModel):
    name: Optional[str] = None
    sql: Optional[str] = None
    cron: Optional[str] = None
    recipients: Optional[list[str]] = None
    description: Optional[str] = None
    question: Optional[str] = None
    database_id: Optional[str] = None
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    is_active: Optional[bool] = None
    subject_template: Optional[str] = None
    intro: Optional[str] = None
    footer: Optional[str] = None
    display_columns: Optional[list[str]] = None
    max_rows: Optional[int] = None
    attach_csv: Optional[bool] = None
    send_condition: Optional[str] = None
    condition_value: Optional[int] = None


class PreviewCronReq(BaseModel):
    cron: str
    starts_at: Optional[str] = None
    ends_at: Optional[str] = None
    count: int = 5


@router.get("")
async def list_schedules(workspace=Depends(require_permission("schedules.view"))):
    try:
        items = await ctrl.list_schedules(workspace["workspace_id"])
        return JSONResponse(
            {"schedules": items, "max_schedules": ctrl.MAX_SCHEDULES_PER_WORKSPACE}
        )
    except Exception:
        log.exception("Failed to list schedules")
        raise HTTPException(500, "Failed to load schedules")


@router.post("")
@limiter.limit("20/minute")
async def create_schedule(
    request: Request,
    req: CreateScheduleReq,
    workspace=Depends(require_permission("schedules.manage")),
    user=Depends(get_current_user),
):
    try:
        schedule = await ctrl.create_schedule(
            workspace["workspace_id"],
            user.get("user_id", user.get("sub")),
            req.model_dump(exclude_unset=True),
        )
        await log_activity(
            workspace["workspace_id"],
            workspace.get("user_id"),
            "schedule.created",
            "schedule",
            schedule.get("id"),
            {"name": schedule.get("name"), "cron": schedule.get("cron")},
        )
        return JSONResponse(schedule, status_code=201)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to create schedule")
        raise HTTPException(500, "Failed to create schedule")


@router.get("/{schedule_id}")
async def get_schedule(
    schedule_id: str, workspace=Depends(require_permission("schedules.view"))
):
    try:
        schedule = await ctrl.get_schedule(workspace["workspace_id"], schedule_id)
        if not schedule:
            raise HTTPException(404, "Schedule not found")
        return JSONResponse(schedule)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to get schedule")
        raise HTTPException(500, "Failed to load schedule")


@router.patch("/{schedule_id}")
@limiter.limit("30/minute")
async def update_schedule(
    request: Request,
    schedule_id: str,
    req: UpdateScheduleReq,
    workspace=Depends(require_permission("schedules.manage")),
):
    try:
        schedule = await ctrl.update_schedule(
            workspace["workspace_id"], schedule_id, req.model_dump(exclude_unset=True)
        )
        if not schedule:
            raise HTTPException(404, "Schedule not found")
        await log_activity(
            workspace["workspace_id"],
            workspace.get("user_id"),
            "schedule.updated",
            "schedule",
            schedule_id,
            {"name": schedule.get("name")},
        )
        return JSONResponse(schedule)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to update schedule")
        raise HTTPException(500, "Failed to update schedule")


@router.delete("/{schedule_id}")
async def delete_schedule(
    schedule_id: str, workspace=Depends(require_permission("schedules.manage"))
):
    try:
        deleted = await ctrl.delete_schedule(workspace["workspace_id"], schedule_id)
        if not deleted:
            raise HTTPException(404, "Schedule not found")
        await log_activity(
            workspace["workspace_id"],
            workspace.get("user_id"),
            "schedule.deleted",
            "schedule",
            schedule_id,
            {},
        )
        return JSONResponse({"message": "Deleted successfully"})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to delete schedule")
        raise HTTPException(500, "Failed to delete schedule")


@router.post("/{schedule_id}/pause")
async def pause_schedule(
    schedule_id: str, workspace=Depends(require_permission("schedules.manage"))
):
    """Toggle a schedule between paused and active."""
    try:
        existing = await ctrl.get_schedule(workspace["workspace_id"], schedule_id)
        if not existing:
            raise HTTPException(404, "Schedule not found")

        schedule = await ctrl.set_active(
            workspace["workspace_id"], schedule_id, not existing.get("is_active", True)
        )
        if not schedule:
            raise HTTPException(404, "Schedule not found")
        await log_activity(
            workspace["workspace_id"],
            workspace.get("user_id"),
            "schedule.resumed" if schedule.get("is_active") else "schedule.paused",
            "schedule",
            schedule_id,
            {"name": schedule.get("name")},
        )
        return JSONResponse(schedule)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to toggle schedule")
        raise HTTPException(500, "Failed to update schedule")


@router.post("/{schedule_id}/run")
@limiter.limit("5/minute")
async def run_schedule_now(
    request: Request,
    schedule_id: str,
    workspace=Depends(require_permission("schedules.manage")),
):
    """Run a schedule immediately and email the result, as a delivery test.

    Tightly rate limited: this is the one endpoint that sends mail on demand.
    """
    try:
        outcome = await ctrl.run_now(
            request.app, workspace["workspace_id"], schedule_id
        )
        if not outcome.get("found"):
            raise HTTPException(404, "Schedule not found")
        return JSONResponse(outcome)
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to run schedule")
        raise HTTPException(500, "Failed to run schedule")


@router.get("/{schedule_id}/history")
async def schedule_history(
    schedule_id: str,
    limit: int = 25,
    workspace=Depends(require_permission("schedules.view")),
):
    try:
        schedule = await ctrl.get_schedule(workspace["workspace_id"], schedule_id)
        if not schedule:
            raise HTTPException(404, "Schedule not found")
        runs = await ctrl.list_runs(
            workspace["workspace_id"], schedule_id, limit=max(1, min(limit, 100))
        )
        return JSONResponse({"runs": runs})
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to load schedule history")
        raise HTTPException(500, "Failed to load execution history")


@router.post("/preview")
@limiter.limit("60/minute")
async def preview_cron(
    request: Request,
    req: PreviewCronReq,
    workspace=Depends(require_permission("schedules.view")),
):
    """Validate a cron expression and return the next few firing times.

    Backs the live preview in the schedule dialog, so the frontend never has to
    reimplement cron parsing and the times shown are the times that will fire.
    """
    try:
        return JSONResponse(
            await ctrl.preview(
                req.cron,
                starts_at=req.starts_at,
                ends_at=req.ends_at,
                count=max(1, min(req.count, 10)),
            )
        )
    except HTTPException:
        raise
    except Exception:
        log.exception("Failed to preview cron expression")
        raise HTTPException(500, "Failed to preview schedule")
