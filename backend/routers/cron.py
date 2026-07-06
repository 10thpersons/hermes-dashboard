"""Cron router."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.hermes_data import get_cron_jobs, toggle_cron_job

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
