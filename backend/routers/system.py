"""System health router — enriched with CPU, memory, load, uptime, and process count."""
import subprocess
import platform
import os
import time
from datetime import datetime, timezone
from fastapi import APIRouter
from config import HERMES_HOME, SESSIONS_DB, OBSIDIAN_VAULT

router = APIRouter()


def _read_proc_meminfo() -> dict:
    """Parse /proc/meminfo for memory stats (works in containers)."""
    info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = parts[1].strip().split()[0]  # kB value
                    info[key] = int(val)
    except Exception:
        return {}
    return info


def _read_cpu_usage() -> dict:
    """Read CPU usage from /proc/stat (instantaneous snapshot)."""
    try:
        with open("/proc/stat") as f:
            line = f.readline()
        parts = line.split()
        # user, nice, system, idle, iowait, irq, softirq, steal
        vals = [int(x) for x in parts[1:9]]
        idle = vals[3] + vals[4]  # idle + iowait
        total = sum(vals)
        return {"idle": idle, "total": total}
    except Exception:
        return {}


def _get_cpu_percent() -> float | None:
    """Calculate CPU usage % by sampling /proc/stat twice with 0.1s gap."""
    try:
        s1 = _read_cpu_usage()
        if not s1:
            return None
        time.sleep(0.1)
        s2 = _read_cpu_usage()
        if not s2:
            return None
        idle_delta = s2["idle"] - s1["idle"]
        total_delta = s2["total"] - s1["total"]
        if total_delta == 0:
            return 0.0
        return round((1.0 - idle_delta / total_delta) * 100, 1)
    except Exception:
        return None


def _get_memory() -> dict:
    """Get memory usage from /proc/meminfo."""
    info = _read_proc_meminfo()
    if not info:
        return {"error": "unavailable"}
    total_kb = info.get("MemTotal", 0)
    available_kb = info.get("MemAvailable", info.get("MemFree", 0))
    used_kb = total_kb - available_kb
    total_mb = round(total_kb / 1024)
    used_mb = round(used_kb / 1024)
    available_mb = round(available_kb / 1024)
    percent = round((used_kb / total_kb) * 100, 1) if total_kb > 0 else 0
    return {
        "total_mb": total_mb,
        "used_mb": used_mb,
        "available_mb": available_mb,
        "percent": f"{percent}%",
        "percent_value": percent,
    }


def _get_load_average() -> dict:
    """Get system load averages."""
    try:
        load1, load5, load15 = os.getloadavg()
        return {
            "load1": round(load1, 2),
            "load5": round(load5, 2),
            "load15": round(load15, 2),
        }
    except Exception:
        return {"load1": 0, "load5": 0, "load15": 0}


def _get_uptime_seconds() -> float:
    """Read uptime in seconds from /proc/uptime."""
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0


def _format_uptime(seconds: float) -> str:
    """Format uptime seconds into human-readable string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    mins = int((seconds % 3600) // 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")
    return " ".join(parts)


def _get_process_count() -> int:
    """Count running processes."""
    try:
        result = subprocess.run(
            ["ps", "aux", "--no-headers"], capture_output=True, text=True, timeout=5
        )
        return len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
    except Exception:
        return 0


@router.get("/health")
async def health():
    """Full system health check with CPU, memory, load, uptime, process count."""
    # Check Hermes components
    hermes_dir_exists = HERMES_HOME.exists()
    sessions_db_exists = SESSIONS_DB.exists()
    obsidian_exists = OBSIDIAN_VAULT.exists()

    # Get disk usage
    disk = {}
    try:
        df = subprocess.run(["df", "-h", "/"], capture_output=True, text=True, timeout=5)
        lines = df.stdout.strip().split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            disk = {
                "total": parts[1],
                "used": parts[2],
                "available": parts[3],
                "percent": parts[4],
            }
    except Exception:
        disk = {"error": "unavailable"}

    # Get uptime
    uptime_seconds = _get_uptime_seconds()
    uptime_human = _format_uptime(uptime_seconds) if uptime_seconds > 0 else ""

    # Fallback to uptime command if /proc/uptime fails
    if not uptime_human:
        try:
            up = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
            uptime_human = up.stdout.strip()
        except Exception:
            pass

    # Get running services
    services = {}
    for svc in ["hermes-gateway", "docker"]:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5,
            )
            services[svc] = result.stdout.strip()
        except Exception:
            services[svc] = "unknown"

    # CPU, memory, load, process count
    cpu_percent = _get_cpu_percent()
    memory = _get_memory()
    load = _get_load_average()
    process_count = _get_process_count()

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": platform.node(),
        "uptime": uptime_human,
        "uptime_seconds": uptime_seconds,
        "cpu_percent": cpu_percent,
        "memory": memory,
        "load_average": load,
        "process_count": process_count,
        "disk": disk,
        "hermes": {
            "home_exists": hermes_dir_exists,
            "sessions_db_exists": sessions_db_exists,
            "obsidian_exists": obsidian_exists,
        },
        "services": services,
    }
