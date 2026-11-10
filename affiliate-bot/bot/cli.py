"""Threads + Shopee affiliate bot for Adeen.

Public entry points:
  python -m bot.cli health          -> check every credential and connection
  python -m bot.cli topics          -> show current topic harvest
  python -m bot.cli discover        -> topic -> product candidates, scored
  python -m bot.cli draft           -> generate drafts (staged, NOT published)
  python -m bot.cli publish <id>    -> publish one staged draft
  python -m bot.cli reply           -> draft replies to comments on our posts
  python -m bot.cli report          -> local performance snapshot

Nothing publishes unless explicitly told to. Approval mode is the default.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import SETTINGS, DRAFTS
from .pipeline import Pipeline
from .state import State, now_myt
from .threads_api import ThreadsAPI, ThreadsError, ThreadsAuthError
from .writer import Writer, Draft


def _p() -> Pipeline:
    return Pipeline()


def cmd_health(_args: list[str]) -> int:
    p = _p()
    print(p.health())
    return 0


def cmd_topics(_args: list[str]) -> int:
    from .topics import harvest
    for t in harvest(30):
        print(f"[{t.kind}] {t.title}")
        if t.published:
            print(f"        {t.published}")
    return 0


def cmd_discover(args: list[str]) -> int:
    p = _p()
    limit = int(args[0]) if args else 12
    print(f"harvesting topics and querying Shopee affiliate API ...\n")
    cands = p.gather_candidates(topic_limit=limit)
    if not cands:
        print("No candidates. If Shopee credentials are missing, product discovery is skipped")
        print("(topic harvest still works - that needs no credentials).")
        return 1
    sel = p.select(cands, n=15)
    print(f"{len(cands)} candidates found, showing top {len(sel)}\n")
    for i, c in enumerate(sel, 1):
        topic = c.topic.title if c.topic else "evergreen"
        print(f"{i:2}. fit={c.fit_score:6.1f}  {c.product.short()}")
        print(f"     topic : {topic[:90]}")
        print(f"     why   : {', '.join(c.reasons)}")
        print()
    return 0


def cmd_draft(args: list[str]) -> int:
    n = int(args[0]) if args else 3
    p = _p()
    print("gathering candidates ...")
    cands = p.gather_candidates(topic_limit=10)
    if not cands:
        print("No products available - Shopee API credentials likely missing.")
        return 1
    sel = p.select(cands, n=n)
    print(f"writing {len(sel)} drafts with {SETTINGS.model} ...\n")
    drafts = p.build_drafts(sel)
    for d in drafts:
        print(f"--- score {d.score:.0f}  {'OK' if d.ok else 'FLAGS: ' + ','.join(d.flags)}")
        print(f"    product: {d.product_name[:70]}")
        print(f"    topic  : {d.topic}")
        print(f"    text   : {d.text[:300]}")
        print()
    staged = p.stage(drafts)
    print(f"staged {len(staged)} drafts -> {DRAFTS / 'latest.md'}")
    print("NOTHING PUBLISHED. Review the file, then:  python -m bot.cli publish <index>")
    return 0


def cmd_publish(args: list[str]) -> int:
    p = _p()
    st = State()
    drafts = st.pending_drafts()
    if not drafts:
        print("No pending drafts. Run: python -m bot.cli draft")
        return 1
    if not args:
        print("Which draft? Index:")
        for i, d in enumerate(drafts):
            print(f"  {i}: score {d.get('score',0):.0f} | {d.get('product_name','')[:60]}")
        return 1
    idx = int(args[0])
    if idx < 0 or idx >= len(drafts):
        print(f"Index out of range (0-{len(drafts)-1})")
        return 1
    rec = drafts[idx]
    if not rec.get("ok"):
        print("Draft did not pass validation:")
        print("  flags:", rec.get("flags"))
        print("Refusing to publish a failing draft without an explicit override.")
        return 2
    d = Draft(
        text=rec["text"], archetype=rec.get("archetype", ""), hook=rec.get("hook", ""),
        topic=rec.get("topic", ""), product_name=rec.get("product_name", ""),
        link=rec.get("link", ""), sub_ids=rec.get("sub_ids", []),
        score=rec.get("score", 0), flags=rec.get("flags", []), ok=True,
    )
    try:
        out = p.publish(d)
    except (ThreadsAuthError, ThreadsError) as e:
        print(f"Threads rejected the post: {e}")
        return 3
    except Exception as e:  # noqa: BLE001
        print(f"Publish failed: {type(e).__name__}: {e}")
        return 3
    rec["published"] = True
    rec["post_id"] = out.get("post_id")
    st.data["drafts"] = [rec if d2 is rec else d2 for d2 in st.data.get("drafts", [])]
    st.save()
    print(f"published -> post id {out.get('post_id')}")
    print(d.text)
    return 0


def cmd_reply(args: list[str]) -> int:
    p = _p()
    api = p.threads
    if not api.threads_ready:
        print("Threads credentials missing - set THREADS_ACCESS_TOKEN and THREADS_USER_ID")
        return 1
    st = State()
    posts = api.my_posts(limit=25)
    if not posts:
        print("No posts found on the account to reply to.")
        return 1
    print(f"checking {len(posts)} posts for comments ...\n")
    made = 0
    for post in posts:
        pid = post.get("id")
        try:
            replies = api.replies_to(pid, limit=30)
        except (ThreadsError, ThreadsAuthError) as e:
            print(f"  skip post {pid}: {e}")
            continue
        for r in replies:
            if st.already_replied(r.id):
                continue
            if st.count_today("reply") >= SETTINGS.max_replies_per_day:
                print("daily reply budget reached")
                return 0
            print(f"  comment by @{r.username}: {r.text[:110]}")
            print(f"  -> (queued for drafting) reply_to={r.id}")
            st.remember_reply(r.id)
            st.bump("reply")
            made += 1
    st.save()
    print(f"\n{made} new comments queued")
    return 0


def cmd_report(_args: list[str]) -> int:
    st = State()
    posts = st.data.get("posts", [])
    drafts = st.data.get("drafts", [])
    print(f"posts published (local ledger) : {len(posts)}")
    print(f"drafts generated               : {len(drafts)}")
    print(f"pending drafts                 : {len(st.pending_drafts())}")
    print(f"items promoted (anti-duplicate) : {len(st.data.get('items_used', []))}")
    print(f"comments answered              : {len(st.data.get('replied_to', []))}")
    print()
    print("today: posts", st.count_today("post"), "replies", st.count_today("reply"))
    print()
    print("recent posts:")
    for p in posts[-10:]:
        print(f"  {p.get('published_at','?')}  {p.get('product_name','')[:50]}")
    return 0


COMMANDS = {
    "health": cmd_health,
    "topics": cmd_topics,
    "discover": cmd_discover,
    "draft": cmd_draft,
    "publish": cmd_publish,
    "reply": cmd_reply,
    "report": cmd_report,
}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(f"unknown command: {cmd}")
        print("commands:", ", ".join(COMMANDS))
        return 1
    try:
        return fn(argv[1:])
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
