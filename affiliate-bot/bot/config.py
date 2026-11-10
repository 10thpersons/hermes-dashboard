"""Configuration loader for the Threads/Shopee affiliate bot.

Reads credentials from the operator's env file. Never prints secret values.
Env var names are configurable so the same code works in dev and in the live profile.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

WORKDIR = Path(__file__).resolve().parent.parent
RESEARCH = WORKDIR / "research"
DRAFTS = WORKDIR / "drafts"
STATE = WORKDIR / "state"

DEFAULT_ENV_FILES = (
    Path("/root/.hermes/.env"),
    WORKDIR / ".env",
    Path("/root/.hermes/profiles/default/.env"),
)


def load_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file without executing it."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        out[key.strip()] = val
    return out


def collect_env() -> dict[str, str]:
    merged: dict[str, str] = {}
    for f in DEFAULT_ENV_FILES:
        merged.update(load_env_file(f))
    merged.update({k: v for k, v in os.environ.items() if k in _KNOWN})
    return merged


_KNOWN = {
    "ROOTSYS_API_KEY",
    "SHOPEE_API_APP_ID",
    "SHOPEE_API_SECRET",
    "THREADS_ACCESS_TOKEN",
    "THREADS_USER_ID",
    "THREADS_APP_ID",
    "THREADS_APP_SECRET",
    "THREADS_REDIRECT_URI",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "AFFILIATE_MODEL",
    "AFFILIATE_SUBID_PREFIX",
}

ENV = collect_env()


@dataclass
class Settings:
    # --- model ---
    rootsys_key: str = field(default_factory=lambda: ENV.get("ROOTSYS_API_KEY", ""))
    rootsys_base: str = "https://rootsys.cloud/v1"
    model: str = field(default_factory=lambda: ENV.get("AFFILIATE_MODEL", "glm-5.3-mod"))

    # --- shopee ---
    shopee_app_id: str = field(default_factory=lambda: ENV.get("SHOPEE_API_APP_ID", ""))
    shopee_secret: str = field(default_factory=lambda: ENV.get("SHOPEE_API_SECRET", ""))
    shopee_graphql: str = "https://open-api.affiliate.shopee.com.my/graphql"

    # --- threads ---
    threads_token: str = field(default_factory=lambda: ENV.get("THREADS_ACCESS_TOKEN", ""))
    threads_user_id: str = field(default_factory=lambda: ENV.get("THREADS_USER_ID", ""))
    threads_app_id: str = field(default_factory=lambda: ENV.get("THREADS_APP_ID", ""))
    threads_app_secret: str = field(default_factory=lambda: ENV.get("THREADS_APP_SECRET", ""))
    threads_redirect: str = field(default_factory=lambda: ENV.get("THREADS_REDIRECT_URI", ""))

    # --- telegram review channel ---
    telegram_token: str = field(default_factory=lambda: ENV.get("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat: str = field(default_factory=lambda: ENV.get("TELEGRAM_CHAT_ID", ""))

    subid_prefix: str = field(default_factory=lambda: ENV.get("AFFILIATE_SUBID_PREFIX", "th"))

    # --- behaviour ---
    max_posts_per_day: int = 12
    max_replies_per_day: int = 40
    require_approval: bool = True

    @property
    def shopee_ready(self) -> bool:
        return bool(self.shopee_app_id and self.shopee_secret)

    @property
    def threads_ready(self) -> bool:
        return bool(self.threads_token and self.threads_user_id)

    def status(self) -> str:
        def yn(flag: bool) -> str:
            return "ready" if flag else "MISSING"

        return (
            f"model       : {self.model} @ {self.rootsys_base}\n"
            f"rootsys key : {yn(bool(self.rootsys_key))}\n"
            f"shopee api  : {yn(self.shopee_ready)} (app_id + secret)\n"
            f"threads api : {yn(self.threads_ready)} (token + user_id)\n"
            f"telegram    : {yn(bool(self.telegram_token and self.telegram_chat))}\n"
            f"approval    : {'required before publish' if self.require_approval else 'AUTO-PUBLISH'}"
        )


SETTINGS = Settings()

for _d in (DRAFTS, STATE, RESEARCH):
    _d.mkdir(parents=True, exist_ok=True)
