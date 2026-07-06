"""Hermes Dashboard Backend - Data service layer.
Reads from Hermes agent data stores: SQLite sessions (state.db), cron JSON, memory/skills/souls markdown, config YAML.
"""
import sqlite3
import json
import yaml
from pathlib import Path
from typing import Optional
from config import (
    HERMES_HOME, CRON_DIR, MEMORY_DIR, SKILLS_DIR, SOULS_DIR, CONFIG_FILE, OBSIDIAN_VAULT
)

SESSIONS_DB = HERMES_HOME / "state.db"


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

def get_cron_jobs():
    jobs_file = CRON_DIR / "jobs.json"
    if not jobs_file.exists():
        return []
    with open(jobs_file) as f:
        jobs = json.load(f)
    return jobs


def toggle_cron_job(job_id: str, enabled: bool):
    jobs_file = CRON_DIR / "jobs.json"
    if not jobs_file.exists():
        return None
    with open(jobs_file) as f:
        jobs = json.load(f)
    for job in jobs:
        if job.get("id") == job_id:
            job["enabled"] = enabled
            with open(jobs_file, "w") as f:
                json.dump(jobs, f, indent=2)
            return job
    return None


# ── Knowledge ─────────────────────────────────────────────────────────────────

def _read_markdown_dir(directory: Path) -> list[dict]:
    """Read all .md files from a directory tree."""
    items = []
    if not directory.exists():
        return items
    for md_file in directory.rglob("*.md"):
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
    full_path = SKILLS_DIR / skill_path
    if not full_path.exists():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")


# ── Config ────────────────────────────────────────────────────────────────────

def get_config():
    if not CONFIG_FILE.exists():
        return {}
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def update_config(updates: dict):
    """Merge updates into config.yaml. Returns the updated config."""
    current = get_config()
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
    full_path = OBSIDIAN_VAULT / file_path
    if not full_path.exists() or not full_path.is_file():
        return None
    return full_path.read_text(encoding="utf-8", errors="replace")
