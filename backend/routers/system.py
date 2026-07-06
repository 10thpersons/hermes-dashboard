"""System health router."""
import subprocess
import platform
from datetime import datetime, timezone
from fastapi import APIRouter
from config import HERMES_HOME, SESSIONS_DB, OBSIDIAN_VAULT

router = APIRouter()


@router.get("/health")
async def health():
    """Full system health check."""
    # Check Hermes components
    hermes_dir_exists = HERMES_HOME.exists()
    sessions_db_exists = SESSIONS_DB.exists()
    obsidian_exists = OBSIDIAN_VAULT.exists()

    # Get disk usage
    disk = {}
    try:
        df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True)
        lines = df.stdout.strip().split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            disk = {"total": parts[1], "used": parts[2], "available": parts[3], "percent": parts[4]}
    except Exception:
        disk = {"error": "unavailable"}

    # Get uptime
    uptime = ""
    try:
        up = subprocess.run(["uptime", "-p"], capture_output=True, text=True)
        uptime = up.stdout.strip()
    except Exception:
        pass

    # Get running services
    services = {}
    for svc in ["hermes-gateway", "docker"]:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True
            )
            services[svc] = result.stdout.strip()
        except Exception:
            services[svc] = "unknown"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "uptime": uptime,
        "disk": disk,
        "hermes": {
            "home_exists": hermes_dir_exists,
            "sessions_db_exists": sessions_db_exists,
            "obsidian_exists": obsidian_exists,
        },
        "services": services,
    }
