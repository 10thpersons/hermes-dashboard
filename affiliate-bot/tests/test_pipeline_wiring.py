"""Integration test for the velocity + risk wiring in Pipeline.

Runs with mocks so no network and no real Threads/Shopee calls happen.
Run: python3 tests/test_pipeline_wiring.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot.pipeline import Pipeline
from bot.risk import ESCALATE, HOLD, SAFE
from bot.state import State
from bot.velocity import VelocityGovernor
from bot.writer import Draft

PASSED = 0
FAILED = 0


def check(name, cond, detail=""):
    global PASSED, FAILED
    if cond:
        PASSED += 1
        print(f"PASS {name}")
    else:
        FAILED += 1
        print(f"FAIL {name}  {detail}")


class FakeThreads:
    threads_ready = True

    def __init__(self):
        self.published = []

    def publish(self, text, reply_to_id=None):
        self.published.append({"text": text, "reply_to_id": reply_to_id})
        return f"post_{len(self.published)}"

    def token_check(self):
        return "threads token OK"

    def rate_state(self):
        return {}


class FakeShopee:
    def health(self):
        return "shopee api OK"

    def offer_link_for(self, product, sub_ids):
        return "https://s.shopee.com.my/abc"


def make_pipeline(tmp_state):
    state = State(path=tmp_state)
    gov = VelocityGovernor(state=state, current_week=1)
    return Pipeline(threads=FakeThreads(), shopee=FakeShopee(), state=state,
                    governor=gov), state, gov


def test_reply_safe(tmp):
    p, state, gov = make_pipeline(tmp)
    out = p.reply("nice tip bro, sangat membantu!", " obliged bro", comment_id="c1")
    check("safe reply sends", out["action"] == "send", out)
    check("safe reply classified SAFE", out["classification"] == SAFE, out)
    check("safe reply published", len(p.threads.published) == 1, p.threads.published)
    check("safe reply passes reply_to_id",
          p.threads.published[0]["reply_to_id"] == "c1", p.threads.published)
    check("safe reply recorded in state",
          state.already_replied("c1"), state.data.get("replied_to"))


def test_reply_hold(tmp):
    p, state, gov = make_pipeline(tmp)
    out = p.reply("ini cek RM atau apa? guarantee tak?",
                  "yes guaranteed 100%", comment_id="c2")
    check("hold reply queues", out["action"] == "queue", out)
    check("hold reply not published", len(p.threads.published) == 0)
    check("hold reply in review_queue",
          len(state.data.get("review_queue", [])) == 1, state.data.get("review_queue"))
    check("hold reply not marked replied",
          not state.already_replied("c2"))


def test_reply_escalate(tmp):
    p, state, gov = make_pipeline(tmp)
    out = p.reply("scammer! dah tipu orang, refund now!",
                  "sorry about that", comment_id="c3")
    check("escalate skips", out["action"] == "skip", out)
    check("escalate classified ESCALATE", out["classification"] == ESCALATE, out)
    check("escalate not published", len(p.threads.published) == 0)
    check("escalate recorded",
          len(state.data.get("escalations", [])) == 1, state.data.get("escalations"))


def test_publish_blocked_by_governor(tmp):
    p, state, gov = make_pipeline(tmp)
    # exhaust the week-1 original post cap
    cap = gov.cap("original_posts")
    for _ in range(cap):
        gov.record_post("affiliate")
    d = Draft(text="x" * 300, archetype="a", topic="t", product_name="p",
              link="l", sub_ids=[], score=90, flags=[], ok=True)
    try:
        p.publish(d)
        check("governor blocks publish", False, "publish did not raise")
    except RuntimeError as e:
        check("governor blocks publish", "Velocity governor" in str(e), str(e))
    check("governor blocked publish did not post",
          len(p.threads.published) == 0)


def test_publish_allowed(tmp):
    p, state, gov = make_pipeline(tmp)
    d = Draft(text="x" * 300, archetype="a", topic="t", product_name="p",
              link="l", sub_ids=[], score=90, flags=[], ok=True)
    rec = p.publish(d)
    check("publish succeeds", bool(rec.get("post_id")), rec)
    check("publish recorded", len(p.threads.published) == 1)
    check("governor counted post", gov.get_status()["original_posts"].startswith("1/"),
          gov.get_status())


def test_velocity_quota_blocks_reply(tmp):
    p, state, gov = make_pipeline(tmp)
    cap = gov.cap("engagement_replies")
    for _ in range(cap):
        gov.record_engagement_reply()
    out = p.reply("great post thanks!", "thanks bro", comment_id="c9")
    check("quota blocks reply", out["action"] == "queue", out)
    check("quota blocked reply not published", len(p.threads.published) == 0)


def main():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for i, fn in enumerate([
            test_reply_safe, test_reply_hold, test_reply_escalate,
            test_publish_blocked_by_governor, test_publish_allowed,
            test_velocity_quota_blocks_reply,
        ]):
            print(f"\n--- {fn.__name__} ---")
            fn(Path(d) / f"state_{i}.json")
    print(f"\n{PASSED} passed, {FAILED} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())
