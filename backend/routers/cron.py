"""Cron router with run-now support."""
import os
import subprocess
import signal
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from services.hermes_data import (
    get_cron_jobs,
    toggle_cron_job,
    get_cron_output,
    get_cron_history,
    read_cron_output_file,
)
from config import CRON_DIR

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


@router.post("/{job_id}/run")
async def run_job_now(job_id: str):
    """Trigger a cron job to run immediately by writing a trigger file.

    The Hermes agent's cron runner watches for .trigger files in the cron dir.
    If that mechanism isn't available, we signal the hermes process directly.
    """
    jobs_file = CRON_DIR / "jobs.json"
    if not jobs_file.exists():
        raise HTTPException(status_code=404, detail="No cron jobs found")

    # Verify the job exists
    with open(jobs_file) as f:
        data = json.load(f)
    jobs = data.get("jobs", data) if isinstance(data, dict) else data
    job_exists = any(j.get("id") == job_id for j in (jobs if isinstance(jobs, list) else []))
    if not job_exists:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")

    # Method 1: Write a trigger file that the cron runner watches
    trigger_path = CRON_DIR / f"{job_id}.trigger"
    try:
        trigger_path.write_text(json.dumps({
            "job_id": job_id,
            "triggered_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "source": "dashboard",
        }))
        return {"status": "triggered", "job_id": job_id, "method": "trigger_file"}
    except Exception as e:
        # Method 2: Try to signal the hermes process
        try:
            result = subprocess.run(
                ["pgrep", "-f", "hermes.*cron"],
                capture_output=True, text=True, timeout=5,
            )
            if result.stdout.strip():
                pid = int(result.stdout.strip().split("\n")[0])
                os.kill(pid, signal.SIGUSR1)
                return {"status": "signaled", "job_id": job_id, "method": "signal", "pid": pid}
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail=f"Could not trigger job: {str(e)}"
        )


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
