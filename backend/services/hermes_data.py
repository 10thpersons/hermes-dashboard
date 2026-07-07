"""Hermes Dashboard Backend - Data service layer.
Reads from Hermes agent data stores: SQLite sessions (state.db), cron JSON, memory/skills/souls markdown, config YAML.
"""
import sqlite3
import json
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional
from config import (
    HERMES_HOME, CRON_DIR, MEMORY_DIR, SKILLS_DIR, SOULS_DIR, CONFIG_FILE, OBSIDIAN_VAULT
)

SESSIONS_DB = HERMES_HOME / "state.db"


def _safe_path(base: Path, user_path: str) -> Path | None:
    """Return resolved path only if it stays inside base. Prevents traversal."""
    try:
        resolved = (base / user_path).resolve()
        base_resolved = base.resolve()
        resolved.relative_to(base_resolved)
        return resolved
    except (ValueError, OSError):
        return None


def _get_db():
    """Get a read-only SQLite connection to the sessions database."""
    if not SESSIONS_DB.exists():
        return None
    conn = sqlite3.connect(f"file:{SESSIONS_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ── Sessions ──────────────────────────────────────────────────────────────────

def get_sessions(limit: int = 50, offset: int = 0, query: Optional[str] = None):
    conn = _get_db()
    if not conn:
        return {"sessions": [], "total": 0}
    try:
        if query:
            rows = conn.execute(
                "SELECT s.id, s.source, s.model, s.started_at, s.ended_at, s.message_count "
                "FROM sessions s WHERE s.id IN "
                "(SELECT session_id FROM messages_fts WHERE content MATCH ?) "
                "ORDER BY s.started_at DESC LIMIT ? OFFSET ?",
                (query, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM sessions WHERE id IN "
                "(SELECT session_id FROM messages_fts WHERE content MATCH ?)",
                (query,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, source, model, started_at, ended_at, message_count "
                "FROM sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        return {
            "sessions": [dict(r) for r in rows],
            "total": total
        }
    finally:
        conn.close()


def get_session_messages(session_id: str, limit: int = 200):
    conn = _get_db()
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT id, role, content, tool_calls, tool_name, timestamp, token_count "
            "FROM messages WHERE session_id = ? ORDER BY id ASC LIMIT ?",
            (session_id, limit)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Cron ──────────────────────────────────────────────────────────────────────

CRON_OUTPUT_DIR = CRON_DIR / "output"


def _scan_cron_output(job_id: str) -> dict:
    """Scan the cron output directory for files belonging to a job.

    Hermes writes output in two layouts:
      - Loose files: <output>/<job_id>_<YYYYMMDD>_<HHMMSS>.txt
      - Per-job dirs: <output>/<job_id>/<YYYY-MM-DD_HH-MM-SS>.md
    Also tolerates arbitrary files prefixed with <job_id>.

    Returns {files: [...sorted oldest->newest by mtime], latest: path|None, count: int}.
    """
    result = {"files": [], "latest": None, "count": 0}
    if not CRON_OUTPUT_DIR.exists():
        return result

    matches: list[Path] = []
    # Per-job subdirectory (newer format)
    job_dir = CRON_OUTPUT_DIR / job_id
    if job_dir.is_dir():
        for f in job_dir.iterdir():
            if f.is_file() and not f.name.startswith(".") and f.suffix in (".txt", ".md"):
                matches.append(f)

    # Loose files prefixed with <job_id>_
    for f in CRON_OUTPUT_DIR.iterdir():
        if f.is_file() and f.name.startswith(f"{job_id}_") and f.suffix in (".txt", ".md"):
            matches.append(f)

    if not matches:
        return result

    # Dedupe (a file could theoretically match both loops) and sort by mtime ascending
    seen = set()
    unique = []
    for f in matches:
        rp = str(f.resolve())
        if rp not in seen:
            seen.add(rp)
            unique.append(f)
    unique.sort(key=lambda p: p.stat().st_mtime)

    entries = []
    for f in unique:
        st = f.stat()
        entries.append({
            "filename": f.name,
            "path": str(f),
            "size": st.st_size,
            "mtime": st.st_mtime,
            "mtime_iso": datetime.fromtimestamp(st.st_mtime).isoformat(),
        })

    result["files"] = entries
    result["latest"] = entries[-1] if entries else None
    result["count"] = len(entries)
    return result


def get_cron_jobs():
    """Return the list of cron jobs, enriched with output-directory metadata.

    Each job gets:
      - last_run_time: from job.last_run_at (falls back to latest output mtime)
      - last_run_status: from job.last_status ("ok"/"error"), or "never"
      - output_file_count: number of output files on disk for this job
    Returns a plain list so the frontend's Array.isArray checks keep working.
    """
    jobs_file = CRON_DIR / "jobs.json"
    if not jobs_file.exists():
        return []
    with open(jobs_file) as f:
        data = json.load(f)

    # jobs.json is {"jobs": [...], "updated_at": ...}; tolerate a bare array too
    jobs = data["jobs"] if isinstance(data, dict) and "jobs" in data else data
    if not isinstance(jobs, list):
        return []

    for job in jobs:
        jid = job.get("id")
        scan = _scan_cron_output(jid) if jid else {"files": [], "latest": None, "count": 0}

        job["output_file_count"] = scan["count"]

        raw_status = job.get("last_status")
        if raw_status == "ok":
            job["last_run_status"] = "success"
        elif raw_status == "error":
            job["last_run_status"] = "failed"
        elif raw_status:
            job["last_run_status"] = str(raw_status)
        else:
            job["last_run_status"] = "never"

        # Prefer the explicit last_run_at field; fall back to latest output mtime
        last_run_at = job.get("last_run_at")
        if not last_run_at and scan["latest"]:
            last_run_at = scan["latest"]["mtime_iso"]
        job["last_run_time"] = last_run_at

    return jobs


def get_cron_output(job_id: str, max_bytes: int = 512_000):
    """Return the most recent output for a job, or None if none exists."""
    scan = _scan_cron_output(job_id)
    if not scan["latest"]:
        return None
    path = Path(scan["latest"]["path"])
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    truncated = False
    if len(content) > max_bytes:
        content = content[:max_bytes] + f"\n\n... [truncated, full size {len(content)} bytes]"
        truncated = True
    return {
        "job_id": job_id,
        "filename": scan["latest"]["filename"],
        "content": content,
        "size": scan["latest"]["size"],
        "mtime_iso": scan["latest"]["mtime_iso"],
        "truncated": truncated,
    }


def get_cron_history(job_id: str):
    """Return output files for a job, newest first."""
    scan = _scan_cron_output(job_id)
    files = list(reversed(scan["files"]))  # newest first
    return {
        "job_id": job_id,
        "count": scan["count"],
        "files": files,
    }


def read_cron_output_file(job_id: str, filename: str, max_bytes: int = 512_000):
    """Read a specific output file for a job by filename. Returns None if not found.

    Looks in both the per-job subdirectory and the loose-file layout, but only
    returns files that actually belong to this job (prevents cross-job reads).
    """
    scan = _scan_cron_output(job_id)
    target = next((f for f in scan["files"] if f["filename"] == filename), None)
    if not target:
        return None
    path = Path(target["path"])
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    truncated = False
    if len(content) > max_bytes:
        content = content[:max_bytes] + f"\n\n... [truncated, full size {len(content)} bytes]"
        truncated = True
    return {
        "job_id": job_id,
        "filename": filename,
        "content": content,
        "size": target["size"],
        "mtime_iso": target["mtime_iso"],
        "truncated": truncated,
    }


def toggle_cron_job(job_id: str, enabled: bool):
    jobs_file = CRON_DIR / "jobs.json"
    if not jobs_file.exists():
        return None
    with open(jobs_file) as f:
        data = json.load(f)
    jobs = data["jobs"] if isinstance(data, dict) and "jobs" in data else data
    if not isinstance(jobs, list):
        return None
    for job in jobs:
        if job.get("id") == job_id:
            job["enabled"] = enabled
            with open(jobs_file, "w") as f:
                json.dump(data, f, indent=2)
            return job
    return None


# ── Knowledge ─────────────────────────────────────────────────────────────────

def _read_markdown_dir(directory: Path, max_files: int = 200) -> list[dict]:
    """Read .md files from a directory tree, capped at max_files."""
    items = []
    if not directory.exists():
        return items
    for md_file in sorted(directory.rglob("*.md"))[:max_files]:
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            items.append({
                "name": md_file.stem,
                "path": str(md_file),
                "relative": str(md_file.relative_to(directory)),
                "content": content[:10000],
                "size": len(content),
            })
        except Exception:
            continue
    return items


def get_memory():
    return _read_markdown_dir(MEMORY_DIR)


def get_skills():
    return _read_markdown_dir(SKILLS_DIR)


def get_souls():
    items = []
    if not SOULS_DIR.exists():
        return items
    for md_file in SOULS_DIR.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            items.append({
                "name": md_file.stem,
                "path": str(md_file),
                "content": content[:10000],
                "size": len(content),
            })
        except Exception:
            continue
    return items


def get_skill_detail(skill_path: str):
    full_path = _safe_path(SKILLS_DIR, skill_path)
    if not full_path or not full_path.exists():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")


# ── Config ────────────────────────────────────────────────────────────────────

def get_config():
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def update_config(updates: dict):
    """Merge updates into config.yaml. Creates a backup first. Returns the updated config."""
    if not CONFIG_FILE.exists():
        return {}
    current = get_config()
    # Backup before writing
    import shutil
    from datetime import datetime
    backup_name = f"config.yaml.bak.{datetime.now().strftime('%Y%m%d%H%M%S')}"
    backup_path = CONFIG_FILE.parent / backup_name
    shutil.copy2(CONFIG_FILE, backup_path)
    # Keep only the 5 most recent backups
    backups = sorted(CONFIG_FILE.parent.glob("config.yaml.bak.*"))
    for old in backups[:-5]:
        old.unlink()
    _deep_merge(current, updates)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(current, f, default_flow_style=False, sort_keys=False)
    return current


def _deep_merge(base: dict, override: dict):
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v


# ── Obsidian ──────────────────────────────────────────────────────────────────

def get_obsidian_tree(path: str = ""):
    target = OBSIDIAN_VAULT / path if path else OBSIDIAN_VAULT
    if not target.exists():
        return []
    items = []
    for item in sorted(target.iterdir()):
        if item.name.startswith("."):
            continue
        items.append({
            "name": item.name,
            "path": str(item.relative_to(OBSIDIAN_VAULT)),
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None,
        })
    return items


def get_obsidian_file(file_path: str):
    full_path = _safe_path(OBSIDIAN_VAULT, file_path)
    if not full_path or not full_path.exists() or not full_path.is_file():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")


# ── Usage ──────────────────────────────────────────────────────────────────────

def get_usage_summary():
    """Aggregate token usage across all sessions, with a by-model breakdown."""
    conn = _get_db()
    if not conn:
        return {"total_tokens": 0, "total_sessions": 0, "avg_tokens_per_session": 0, "by_model": []}
    try:
        row = conn.execute(
            "SELECT "
            "  COALESCE(SUM(input_tokens), 0) AS input_tokens, "
            "  COALESCE(SUM(output_tokens), 0) AS output_tokens, "
            "  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens, "
            "  COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens, "
            "  COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens, "
            "  COUNT(*) AS session_count "
            "FROM sessions"
        ).fetchone()
        input_tokens = row["input_tokens"]
        output_tokens = row["output_tokens"]
        cache_read = row["cache_read_tokens"]
        cache_write = row["cache_write_tokens"]
        reasoning = row["reasoning_tokens"]
        total_tokens = input_tokens + output_tokens + cache_read + cache_write + reasoning
        session_count = row["session_count"]
        avg = round(total_tokens / session_count) if session_count else 0

        model_rows = conn.execute(
            "SELECT "
            "  COALESCE(NULLIF(model, ''), 'unknown') AS model, "
            "  COUNT(*) AS sessions, "
            "  COALESCE(SUM(input_tokens), 0) AS input_tokens, "
            "  COALESCE(SUM(output_tokens), 0) AS output_tokens, "
            "  COALESCE(SUM(input_tokens + output_tokens + "
            "    COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0) + "
            "    COALESCE(reasoning_tokens, 0)), 0) AS total_tokens "
            "FROM sessions GROUP BY COALESCE(NULLIF(model, ''), 'unknown') "
            "ORDER BY total_tokens DESC"
        ).fetchall()
        by_model = [dict(r) for r in model_rows]

        return {
            "total_tokens": total_tokens,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read,
            "cache_write_tokens": cache_write,
            "reasoning_tokens": reasoning,
            "total_sessions": session_count,
            "avg_tokens_per_session": avg,
            "by_model": by_model,
        }
    finally:
        conn.close()


def get_usage_daily(days: int = 30):
    """Daily token usage for the last N days, grouped by session start date."""
    conn = _get_db()
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT "
            "  date(started_at, 'unixepoch') AS date, "
            "  COUNT(*) AS sessions, "
            "  COALESCE(SUM(input_tokens), 0) AS input_tokens, "
            "  COALESCE(SUM(output_tokens), 0) AS output_tokens, "
            "  COALESCE(SUM(input_tokens + output_tokens + "
            "    COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0) + "
            "    COALESCE(reasoning_tokens, 0)), 0) AS total_tokens "
            "FROM sessions "
            "WHERE started_at >= strftime('%s', 'now', ?) "
            "GROUP BY date(started_at, 'unixepoch') "
            "ORDER BY date ASC",
            (f"-{days} days",)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_usage_by_model():
    """Token usage grouped by model, ordered by total tokens descending."""
    conn = _get_db()
    if not conn:
        return []
    try:
        rows = conn.execute(
            "SELECT "
            "  COALESCE(NULLIF(model, ''), 'unknown') AS model, "
            "  COUNT(*) AS sessions, "
            "  COALESCE(SUM(input_tokens), 0) AS input_tokens, "
            "  COALESCE(SUM(output_tokens), 0) AS output_tokens, "
            "  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens, "
            "  COALESCE(SUM(cache_write_tokens), 0) AS cache_write_tokens, "
            "  COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens, "
            "  COALESCE(SUM(input_tokens + output_tokens + "
            "    COALESCE(cache_read_tokens, 0) + COALESCE(cache_write_tokens, 0) + "
            "    COALESCE(reasoning_tokens, 0)), 0) AS total_tokens "
            "FROM sessions GROUP BY COALESCE(NULLIF(model, ''), 'unknown') "
            "ORDER BY total_tokens DESC"
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["avg_tokens_per_session"] = round(d["total_tokens"] / d["sessions"]) if d["sessions"] else 0
            result.append(d)
        return result
    finally:
        conn.close()
