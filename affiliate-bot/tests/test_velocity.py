"""Run: python3 tests/test_velocity.py  (no pytest needed)"""
import sys, tempfile, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bot.state import State
from bot import velocity as V
from bot.velocity import VelocityGovernor, cap_for


class Clock:
    def __init__(self, d="2026-11-02"): self.d = d
    def __call__(self): return self.d


def gov(week=None, clock=None):
    tmp = Path(tempfile.mkdtemp()) / "state.json"
    clock = clock or Clock()
    return VelocityGovernor(State(tmp), current_week=week, today_fn=clock), clock, tmp


def test_ramp_table():
    exp = {
        "story_chapters": [16, 16, 30, 30, 30],
        "engagement_replies": [5, 15, 40, 40, 40],
        "original_posts": [1, 1, 2, 2, 3],
    }
    for b, vals in exp.items():
        for w, v in enumerate(vals, 1):
            assert cap_for(b, w) == v, (b, w)
    assert cap_for("original_posts", 99) == 3      # clamps high
    assert cap_for("engagement_replies", 0) == 5   # clamps low
    assert cap_for("engagement_replies", -3) == 5


def test_platform_limits():
    assert V.PLATFORM_LIMITS == {"posts_per_day": 250, "replies_per_day": 1000}


def test_week_derived_from_start_date():
    g, clock, _ = gov()
    assert g.current_week == 1
    clock.d = "2026-11-08"; assert g.current_week == 1
    clock.d = "2026-11-09"; assert g.current_week == 2
    clock.d = "2026-11-29"; assert g.current_week == 4
    clock.d = "2026-11-30"; assert g.current_week == 5
    assert g.cap("engagement_replies") == 40


def test_engagement_quota_exhaustion_week1():
    g, _, _ = gov(week=1)
    for i in range(5):
        ok, _m = g.can_reply(); assert ok, i
        g.record_engagement_reply()
    ok, msg = g.can_reply()
    assert not ok and "5/5" in msg
    assert g.get_status()["engagement_replies"] == "5/5"


def test_post_cap_and_thread_week1():
    g, _, _ = gov(week=1)
    ok, _m = g.can_post_thread(16); assert ok
    g.record_post()
    for _ in range(15): g.record_story_reply()
    assert g.get_status()["story_chapters"] == "16/16"
    ok, msg = g.can_post(); assert not ok and "posts cap" in msg
    ok, _m = g.can_reply(is_story_chapter=True); assert not ok
    ok, msg = g.can_post_thread(16); assert not ok and msg.startswith("Cannot start")


def test_thread_needs_chapter_budget():
    g, _, _ = gov(week=3)             # 2 posts, 30 chapters
    g.record_post()
    for _ in range(19): g.record_story_reply()   # 20 used, 10 left, 1 post left
    ok, msg = g.can_post_thread(11); assert not ok and "need 11, have 10" in msg
    ok, _m = g.can_post_thread(10); assert ok     # borderline fits exactly


def test_daily_reset_and_persistence():
    g, clock, path = gov(week=2)
    for _ in range(15): g.record_engagement_reply()
    assert not g.can_reply()[0]
    clock.d = "2026-11-03"            # next day, same instance (long-running process)
    assert g.can_reply()[0]
    assert g.get_status()["engagement_replies"] == "0/15"
    # persisted + reloaded in a new process the same day
    g.record_engagement_reply()
    g2 = VelocityGovernor(State(path), current_week=2, today_fn=clock)
    assert g2.get_status()["engagement_replies"] == "1/15"
    # new instance next day resets
    clock.d = "2026-11-04"
    g3 = VelocityGovernor(State(path), current_week=2, today_fn=clock)
    assert g3.get_status()["engagement_replies"] == "0/15"


def test_reset_keeps_start_date_and_history():
    g, clock, path = gov()
    g.record_post("affiliate")
    clock.d = "2026-11-10"
    g._roll()
    assert g.current_week == 2
    assert len(g._v["history"]) == 1


def test_platform_hard_limit():
    g, _, _ = gov(week=5)
    g._v["story_chapters"] = 0; g._v["engagement_replies"] = 0
    g._v["original_posts"] = 250
    assert g.can_post()[0] is False                # per-ramp cap hits first (3)
    # isolate the platform check directly
    assert g._platform_block(posts_needed=1) is not None
    g._v["original_posts"] = 249
    assert g._platform_block(posts_needed=1) is None
    g._v["original_posts"] = 0
    g._v["engagement_replies"] = 1000
    assert "replies/day" in g._platform_block(replies_needed=1)
    g._v["engagement_replies"] = 999
    assert g._platform_block(replies_needed=1) is None


def test_content_mix():
    g, _, _ = gov()
    ok, _m = g.can_post_affiliate(); assert not ok          # 0 non-aff: 0/1 < 2
    g.record_post("story")
    ok, _m = g.can_post_affiliate(); assert not ok          # 1/1 < 2
    g.record_post("story")
    ok, _m = g.can_post_affiliate(); assert ok              # 2/1 == 2.0 borderline OK
    g.record_post("affiliate")
    mix = g.get_content_mix()
    assert (mix["affiliate"], mix["non_affiliate"], mix["ratio"]) == (1, 2, 2.0) and mix["healthy"]
    ok, msg = g.can_post_affiliate(); assert not ok         # 2/2 = 1.0
    assert "2 more" in msg


def test_content_mix_window_and_external_log():
    g, clock, _ = gov()
    g.record_post("story"); g.record_post("affiliate")
    clock.d = "2026-11-12"                                  # first two now 10 days old
    assert g.get_content_mix() == {"affiliate": 0, "non_affiliate": 0, "ratio": float("inf"), "healthy": True}
    log = [{"content_class": "affiliate", "posted_at": "2026-11-11T10:00:00"},
           {"content_class": "x", "posted_at": "2026-11-11T11:00:00"},
           {"content_class": "x", "posted_at": "2026-11-01T11:00:00"}]
    mix = g.get_content_mix(log)
    assert mix["affiliate"] == 1 and mix["non_affiliate"] == 1


def run():
    fails = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn(); print("PASS", name)
            except Exception:
                fails += 1; print("FAIL", name); traceback.print_exc()
    print(f"{'FAILED' if fails else 'ALL PASSED'} ({fails} failures)")
    return fails


if __name__ == "__main__":
    sys.exit(1 if run() else 0)
