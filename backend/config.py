"""Hermes Dashboard Backend - Configuration."""
import os
from pathlib import Path

HERMES_HOME = Path(os.getenv("HERMES_HOME", "/root/.hermes"))
OBSIDIAN_VAULT = Path(os.getenv("OBSIDIAN_VAULT", "/root/obsidian-vault"))
SESSIONS_DB = HERMES_HOME / "state.db"
CRON_DIR = HERMES_HOME / "cron"
MEMORY_DIR = HERMES_HOME / "memory"
SKILLS_DIR = HERMES_HOME / "skills"
SOULS_DIR = HERMES_HOME / "souls"
CONFIG_FILE = HERMES_HOME / "config.yaml"

def require_api_key(value: str | None) -> str:
    # Match frontend/lib/dashboard-key.ts; operators must supply random material.
    if (not value or len(value) < 32 or len(set(value)) < 8
            or any(not 33 <= ord(char) <= 126 for char in value)):
        raise RuntimeError("DASHBOARD_API_KEY requires at least 32 printable ASCII "
                           "characters without whitespace and at least 8 distinct characters")
    return value


API_KEY = require_api_key(os.getenv("DASHBOARD_API_KEY"))
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
