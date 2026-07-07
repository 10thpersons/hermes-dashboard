"""Cron router."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.hermes_data import (
    get_cron_jobs,
    toggle_cron_job,
    get_cron_output,
    get_cron_history,
    read_cron_output_file,
)

router = APIRouter()


class ToggleRequest(BaseModel):
    enabled: bool


@router.get("")
async def list_cron_jobs():
    return get_cron_jobs()


@router.post("/{job_id}/toggle")
async def toggle_job(job_id: str, body: ToggleRequest):
    result = toggle_cron_job(job_id, body.enabled)
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@router.get("/{job_id}/output")
async def get_job_output(job_id: str):
    """Return the most recent output file content for a cron job."""
    result = get_cron_output(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No output found for this job")
    return result


@router.get("/{job_id}/output/{filename}")
async def get_job_output_file(job_id: str, filename: str):
    """Return the content of a specific output file for a cron job."""
    result = read_cron_output_file(job_id, filename)
    if result is None:
        raise HTTPException(status_code=404, detail="Output file not found")
    return result


@router.get("/{job_id}/history")
async def get_job_history(job_id: str, limit: int = Query(50, ge=1, le=500)):
    """List all output files for a job, newest first."""
    result = get_cron_history(job_id)
    result["files"] = result["files"][:limit]
    return result
