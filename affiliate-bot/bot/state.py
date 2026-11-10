"""Local state: published drafts, reply ledger, daily budgets, product memory.

Deliberately separate from the live bot's state directory. Nothing here is
touched by any scheduled job until the operator explicitly promotes it.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .config import STATE

MYT = timezone(timedelta(hours=8))
STATE_FILE = STATE / "state.json"
LEDGER = STATE / "ledger.jsonl"
PRODUCT_MEMORY = STATE / "product_memory.json"


def now_myt() -> datetime:
    return datetime.now(MYT)


def today() -> str:
    return now_myt().strftime("%Y-%m-%d")


class State:
    def __init__(self, path: Path | None = None):
        self.path = path or STATE_FILE
        self.data: dict[str, Any] = self._load()

    def _load(self) -> dict[str, Any]:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "posts": [],          # published post records
            "drafts": [],         # generated but unpublished
            "hooks_used": [],     # recent hook openings, to avoid repetition
            "items_used": [],     # item ids already promoted (anti-duplicate)
            "counts": {},         # "YYYY-MM-DD:post" -> n
            "replied_to": [],     # reply ids already answered
        }

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False))
        tmp.replace(self.path)

    # ---------------------------------------------------------------- counts
    def bump(self, kind: str, n: int = 1) -> None:
        key = f"{today()}:{kind}"
        self.data.setdefault("counts", {})[key] = self.data.get("counts", {}).get(key, 0) + n

    def count_today(self, kind: str) -> int:
        return int(self.data.get("counts", {}).get(f"{today()}:{kind}", 0))

    # ----------------------------------------------------------------- hooks
    def recent_hooks(self, n: int = 15) -> list[str]:
        return list(self.data.get("hooks_used", []))[-n:]

    def remember_hook(self, hook: str) -> None:
        hooks = self.data.setdefault("hooks_used", [])
        hooks.append(hook[:120])
        self.data["hooks_used"] = hooks[-60:]

    # ----------------------------------------------------------------- items
    def item_used(self, item_id: int) -> bool:
        return int(item_id) in {int(x) for x in self.data.get("items_used", [])}

    def remember_item(self, item_id: int) -> None:
        items = self.data.setdefault("items_used", [])
        if int(item_id) not in {int(x) for x in items}:
            items.append(int(item_id))
        self.data["items_used"] = items[-500:]

    # --------------------------------------------------------------- replies
    def already_replied(self, reply_id: str) -> bool:
        return reply_id in set(self.data.get("replied_to", []))

    def remember_reply(self, reply_id: str) -> None:
        rl = self.data.setdefault("replied_to", [])
        if reply_id not in set(rl):
            rl.append(reply_id)
        self.data["replied_to"] = rl[-1000:]

    # --------------------------------------------------------------- drafts
    def add_draft(self, record: dict[str, Any]) -> None:
        self.data.setdefault("drafts", []).append(record)
        self.data["drafts"] = self.data["drafts"][-100:]

    def add_post(self, record: dict[str, Any]) -> None:
        self.data.setdefault("posts", []).append(record)
        self.data["posts"] = self.data["posts"][-300:]
        self.bump("post")

    def pending_drafts(self) -> list[dict[str, Any]]:
        return [d for d in self.data.get("drafts", []) if not d.get("published")]

    # ------------------------------------------------------- product memory
    def product_memory(self) -> dict[str, Any]:
        if not PRODUCT_MEMORY.exists():
            return {}
        try:
            return json.loads(PRODUCT_MEMORY.read_text())
        except (json.JSONDecodeError, OSError):
            return {}

    def note_product(self, item_id: int, record: dict[str, Any]) -> None:
        mem = self.product_memory()
        mem[str(item_id)] = {**record, "seen_at": time.time(), "seen_date": today()}
        PRODUCT_MEMORY.write_text(json.dumps(mem, indent=1, ensure_ascii=False))

    def product_seen_count(self, item_id: int) -> int:
        return int(self.product_memory().get(str(item_id), {}).get("times_seen", 1))

    def bump_product_seen(self, item_id: int) -> None:
        mem = self.product_memory()
        e = mem.get(str(item_id), {"times_seen": 0})
        e["times_seen"] = int(e.get("times_seen", 0)) + 1
        e["seen_date"] = today()
        mem[str(item_id)] = e
        PRODUCT_MEMORY.write_text(json.dumps(mem, indent=1, ensure_ascii=False))
