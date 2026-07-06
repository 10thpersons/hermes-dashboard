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

API_KEY = os.getenv("DASHBOARD_API_KEY", "hermes-dashboard-2026")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
