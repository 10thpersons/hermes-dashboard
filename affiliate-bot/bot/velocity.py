"""Velocity governor: weekly ramp quotas, platform hard limits, content mix.

Ported from the legacy threads-pipeline velocity_governor. The ramp schedule,
platform limits and 2:1 content-mix rule are unchanged. Persistence goes
through bot.state.State (key ``velocity`` inside State.data) instead of a
private JSON file, and "today" is the MYT date from bot.state.

Buckets:
  original_posts      new top-level posts (each also costs one story chapter)
  story_chapters      parts of a multi-part story thread (post + its replies)
  engagement_replies  replies to other people's comments
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Callable, Iterable

from .state import State, today as _myt_today

# week -> cap per day. Weeks past the last key use the last value.
DAILY_CAPS: dict[str, dict[int, int]] = {
    "story_chapters":     {1: 16, 2: 16, 3: 30, 4: 30, 5: 30},
    "engagement_replies": {1: 5,  2: 15, 3: 40, 4: 40, 5: 40},
    "original_posts":     {1: 1,  2: 1,  3: 2,  4: 2,  5: 3},
}

# Threads API hard limits per day.
PLATFORM_LIMITS = {"posts_per_day": 250, "replies_per_day": 1000}

CONTENT_MIX_RATIO = 2.0   # min non-affiliate posts per affiliate post
MIX_LOOKBACK_DAYS = 7
HISTORY_KEEP_DAYS = 30

_BUCKETS = ("story_chapters", "engagement_replies", "original_posts")


def cap_for(bucket: str, week: int) -> int:
    """Daily cap for ``bucket`` in ramp ``week`` (1-based; clamps both ends)."""
    caps = DAILY_CAPS[bucket]
    week = max(1, min(int(week), max(caps)))
    return caps[week]


class VelocityGovernor:
    def __init__(
        self,
        state: State | None = None,
        current_week: int | None = None,
        today_fn: Callable[[], str] = _myt_today,
    ):
        """
        state:        shared State (created if omitted).
        current_week: force the ramp week. If None, derived from the ramp
                      start date stored in state (set on first use).
        today_fn:     returns 'YYYY-MM-DD'; injectable for tests.
        """
        self.state = state or State()
        self._week_override = current_week
        self._today = today_fn
        self._v = self._load()

    # ------------------------------------------------------------ persistence
    def _blank(self, day: str, history: list | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {"date": day, "history": history or []}
        d.update({b: 0 for b in _BUCKETS})
        return d

    def _load(self) -> dict[str, Any]:
        day = self._today()
        v = self.state.data.setdefault("velocity", None) or self._blank(day)
        v.setdefault("history", [])
        for b in _BUCKETS:
            v.setdefault(b, 0)
        v.setdefault("start_date", day)
        self.state.data["velocity"] = v
        return v

    def _roll(self) -> None:
        """Reset daily counters when the date changes. Called on EVERY access
        so a long-running process rolls over at midnight."""
        day = self._today()
        if self._v.get("date") != day:
            start = self._v.get("start_date", day)
            self._v = self._blank(day, self._v.get("history", []))
            self._v["start_date"] = start
            self.state.data["velocity"] = self._v
            self.state.save()

    def _save(self) -> None:
        self.state.save()

    # ------------------------------------------------------------------- week
    @property
    def current_week(self) -> int:
        if self._week_override is not None:
            return max(1, int(self._week_override))
        try:
            start = date.fromisoformat(self._v.get("start_date", self._today()))
            now = date.fromisoformat(self._today())
        except ValueError:
            return 1
        return max(1, (now - start).days // 7 + 1)

    def set_week(self, week: int | None) -> None:
        self._week_override = week

    def cap(self, bucket: str) -> int:
        return cap_for(bucket, self.current_week)

    # ----------------------------------------------------------------- checks
    def _platform_block(self, posts_needed: int = 0, replies_needed: int = 0) -> str | None:
        v = self._v
        if v["original_posts"] + posts_needed > PLATFORM_LIMITS["posts_per_day"]:
            return f"Platform posts/day limit ({PLATFORM_LIMITS['posts_per_day']}) would be exceeded"
        replies = v["story_chapters"] - v["original_posts"] + v["engagement_replies"]
        if replies + replies_needed > PLATFORM_LIMITS["replies_per_day"]:
            return f"Platform replies/day limit ({PLATFORM_LIMITS['replies_per_day']}) would be exceeded"
        return None

    def can_post(self) -> tuple[bool, str]:
        """Can we start a new original post?"""
        self._roll()
        v = self._v
        post_cap, story_cap = self.cap("original_posts"), self.cap("story_chapters")
        if v["original_posts"] >= post_cap:
            return False, f"Original posts cap reached ({v['original_posts']}/{post_cap})"
        if v["story_chapters"] >= story_cap:
            return False, f"Story chapters cap reached ({v['story_chapters']}/{story_cap})"
        blocked = self._platform_block(posts_needed=1)
        if blocked:
            return False, blocked
        return True, f"OK ({v['original_posts']}/{post_cap} posts, {v['story_chapters']}/{story_cap} chapters)"

    def can_reply(self, is_story_chapter: bool = False) -> tuple[bool, str]:
        """Can we post a reply (story chapter or engagement reply)?"""
        self._roll()
        v = self._v
        bucket = "story_chapters" if is_story_chapter else "engagement_replies"
        cap = self.cap(bucket)
        label = "Story chapters" if is_story_chapter else "Engagement replies"
        if v[bucket] >= cap:
            return False, f"{label} cap reached ({v[bucket]}/{cap})"
        blocked = self._platform_block(replies_needed=1)
        if blocked:
            return False, blocked
        return True, f"OK ({v[bucket]}/{cap} {label.lower()})"

    def can_post_thread(self, part_count: int) -> tuple[bool, str]:
        """Can we post a whole thread (1 post + part_count-1 chapter replies)?"""
        ok, msg = self.can_post()
        if not ok:
            return False, f"Cannot start thread: {msg}"
        remaining = self.cap("story_chapters") - self._v["story_chapters"]
        if remaining < part_count:
            return False, f"Not enough chapter budget: need {part_count}, have {remaining}"
        blocked = self._platform_block(posts_needed=1, replies_needed=max(0, part_count - 1))
        if blocked:
            return False, blocked
        return True, f"OK: thread of {part_count} parts fits"

    # --------------------------------------------------------------- recording
    def record_post(self, content_class: str = "non_affiliate") -> None:
        """Record a new original post (also counts as one story chapter).
        content_class: 'affiliate' or anything else (non-affiliate)."""
        self._roll()
        self._v["original_posts"] += 1
        self._v["story_chapters"] += 1
        hist = self._v["history"]
        hist.append({"date": self._today(), "content_class": content_class})
        cutoff = (date.fromisoformat(self._today()) - timedelta(days=HISTORY_KEEP_DAYS)).isoformat()
        self._v["history"] = [h for h in hist if h.get("date", "") >= cutoff]
        self._save()

    def record_story_reply(self) -> None:
        self._roll()
        self._v["story_chapters"] += 1
        self._save()

    def record_engagement_reply(self) -> None:
        self._roll()
        self._v["engagement_replies"] += 1
        self._save()

    # ------------------------------------------------------------------ status
    def get_status(self) -> dict[str, Any]:
        self._roll()
        v = self._v
        return {
            "week": self.current_week,
            "date": v["date"],
            "original_posts": f"{v['original_posts']}/{self.cap('original_posts')}",
            "story_chapters": f"{v['story_chapters']}/{self.cap('story_chapters')}",
            "engagement_replies": f"{v['engagement_replies']}/{self.cap('engagement_replies')}",
        }

    # ------------------------------------------------------------- content mix
    def get_content_mix(self, post_log: Iterable[dict] | None = None) -> dict[str, Any]:
        """Trailing 7-day mix. post_log: dicts with 'content_class' and
        'posted_at' (ISO string). Defaults to this governor's own history."""
        self._roll()
        cutoff = (date.fromisoformat(self._today()) - timedelta(days=MIX_LOOKBACK_DAYS)).isoformat()
        if post_log is None:
            recent = [h for h in self._v["history"] if h.get("date", "") >= cutoff]
        else:
            recent = [p for p in post_log if str(p.get("posted_at", ""))[:10] >= cutoff]
        affiliate = sum(1 for p in recent if p.get("content_class") == "affiliate")
        non_aff = len(recent) - affiliate
        ratio = non_aff / affiliate if affiliate else float("inf")
        return {
            "affiliate": affiliate,
            "non_affiliate": non_aff,
            "ratio": round(ratio, 2),
            "healthy": ratio >= CONTENT_MIX_RATIO,
        }

    def can_post_affiliate(self, post_log: Iterable[dict] | None = None) -> tuple[bool, str]:
        """Would one more affiliate post keep the mix at >= 2:1?"""
        mix = self.get_content_mix(post_log)
        proj = mix["non_affiliate"] / (mix["affiliate"] + 1)
        if proj < CONTENT_MIX_RATIO:
            need = int(CONTENT_MIX_RATIO * (mix["affiliate"] + 1) - mix["non_affiliate"] + 0.999)
            return False, (
                f"Content mix: {mix['non_affiliate']} non-affiliate / {mix['affiliate']} affiliate; "
                f"another affiliate post drops it to {proj:.1f}:1 (need {CONTENT_MIX_RATIO:g}:1). "
                f"Post {need} more non-affiliate first."
            )
        return True, f"OK: mix {mix['ratio']}:1, projected {proj:.1f}:1"
