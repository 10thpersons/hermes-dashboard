"""Topic -> product -> post pipeline.

Flow:
  1. harvest current topics (Google Trends MY + Google News MY RSS)
  2. map topic -> Shopee search keywords
  3. pull products from the Shopee Affiliate Open API (official, no scraping)
  4. score products for fit (commission x sales x rating x price appeal)
  5. write a Manglish draft for the best fit product
  6. validate the draft against the style rules
  7. either stage it for approval or publish it
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import SETTINGS, DRAFTS
from .risk import ESCALATE, HOLD, SAFE, gate_reply
from .shopee_api import Product, ShopeeOpenAPI, ShopeeError, ShopeeAuthError
from .state import State, now_myt
from .threads_api import ThreadsAPI, ThreadsError, ThreadsAuthError
from .topics import Topic, harvest
from .velocity import VelocityGovernor
from .writer import Writer, Draft


@dataclass
class Candidate:
    topic: Topic | None
    product: Product
    fit_score: float
    reasons: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


def score_product(p: Product, topic: Topic | None, keyword: str) -> tuple[float, list[str]]:
    """Higher is better. Balances commission, proven sales, rating and price appeal."""
    reasons: list[str] = []
    score = 0.0

    # commission, saturating - a 20% offer is not twice as good as 10%
    rate = max(0.0, min(p.commission_rate, 0.30))
    score += min(rate / 0.10, 3.0) * 12
    if p.commission_rate >= 0.05:
        reasons.append(f"commission {p.commission_rate*100:.1f}%")

    # proven sales - the market already voted
    if p.sales > 0:
        sales_score = min(3.0, (p.sales ** 0.5) / 20)
        score += sales_score * 8
        if p.sales >= 100:
            reasons.append(f"{p.sales} sold")

    # rating - low rating means refunds and unhappy buyers
    if p.rating >= 4.5:
        score += 12
        reasons.append(f"{p.rating:.1f}* rating")
    elif p.rating >= 4.0:
        score += 6
    elif 0 < p.rating < 3.5:
        score -= 15
        reasons.append(f"low rating {p.rating:.1f}*")

    # estimated payout per sale - what actually matters for revenue
    if p.commission_est > 0:
        score += min(p.commission_est / 3.0, 3.0) * 6
        if p.commission_est >= 2:
            reasons.append(f"est RM{p.commission_est:.2f}/sale")

    # price appeal - cheap items convert on impulse, but not too cheap (noise)
    if 8 <= p.price_min <= 120:
        score += 10
        reasons.append(f"RM{p.price_min:g} impulse price")
    elif p.price_min > 120:
        score += 2
    elif 0 < p.price_min < 8:
        score -= 5

    # discount
    if p.discount_rate >= 20:
        score += 8
        reasons.append(f"{p.discount_rate}% off")

    # topic alignment
    if topic:
        t = topic.title.lower()
        n = product_name_words(p.name)
        overlap = sum(1 for w in n if w and w in t)
        if overlap:
            score += min(overlap, 3) * 6
            reasons.append(f"matches topic ({overlap} terms)")

    # name quality - affiliate SEO spam has long keyword-stuffed names
    if len(p.name) > 140:
        score -= 8
    if p.name.count("|") > 2:
        score -= 6

    return score, reasons


def product_name_words(name: str) -> list[str]:
    stop = {"the", "and", "for", "with", "new", "free", "hot", "sale", "best", "korea", "original"}
    words = re.findall(r"[a-z]{3,}", name.lower())
    return [w for w in words if w not in stop][:12]


class Pipeline:
    def __init__(self, writer: Writer | None = None, shopee: ShopeeOpenAPI | None = None,
                 threads: ThreadsAPI | None = None, state: State | None = None,
                 governor: VelocityGovernor | None = None):
        self.writer = writer or Writer()
        self.shopee = shopee or ShopeeOpenAPI()
        self.threads = threads or ThreadsAPI()
        self.state = state or State()
        self.governor = governor or VelocityGovernor(state=self.state)

    # ------------------------------------------------------------- discovery
    def gather_candidates(self, topic_limit: int = 12, per_keyword: int = 8,
                          products_per_topic: int = 2) -> list[Candidate]:
        topics = harvest(topic_limit)
        cands: list[Candidate] = []
        seen_items: set[int] = set()

        # keywords: model-mapped per topic, plus a baseline sweep
        keyword_plan: list[tuple[Topic | None, str]] = []
        for t in topics:
            for kw in self.writer.keywords_for_topic(t.title) or []:
                keyword_plan.append((t, kw))
        # baseline evergreen keywords - always have something to post
        for kw in ["organiser", "kitchen organiser", "cable organiser", "rak penyimpan"]:
            keyword_plan.append((None, kw))

        for topic, kw in keyword_plan[:40]:
            try:
                products = self.shopee.product_offers(kw, limit=per_keyword)
            except (ShopeeError, ShopeeAuthError):
                continue
            for p in products:
                if not p.offer_link or not p.name:
                    continue
                if p.item_id in seen_items:
                    continue
                seen_items.add(p.item_id)
                fit, reasons = score_product(p, topic, kw)
                cands.append(Candidate(topic=topic, product=p, fit_score=fit,
                                       reasons=reasons, keywords=[kw]))
            time.sleep(0.4)  # be polite to the API

        cands.sort(key=lambda c: -c.fit_score)
        return cands

    def select(self, cands: list[Candidate], n: int = 3) -> list[Candidate]:
        """Top n, skipping products already promoted and products seen too often."""
        out: list[Candidate] = []
        for c in cands:
            if self.state.item_used(c.product.item_id):
                continue
            if self.state.product_seen_count(c.product.item_id) >= 3:
                continue
            out.append(c)
            if len(out) >= n:
                break
        return out

    # --------------------------------------------------------------- writing
    def build_drafts(self, cands: list[Candidate]) -> list[Draft]:
        drafts: list[Draft] = []
        hooks = self.state.recent_hooks()
        for c in cands:
            link = self.shopee.offer_link_for(c.product, self._sub_ids(c))
            extra = self._product_brief(c)
            d = self.writer.write(
                c.product,
                topic=c.topic.title if c.topic else "",
                extra=extra,
                archetype=self._archetype(c),
                used_hooks=hooks,
            )
            d.link = link
            d.sub_ids = self._sub_ids(c)
            d.topic = c.topic.title if c.topic else "evergreen"
            d.product_name = c.product.name
            d.raw = c.product.short()
            drafts.append(d)
            if d.ok and d.hook:
                pass
            # remember hook even if imperfect, to force variety
            first_line = d.text.split("\n", 1)[0][:80]
            if first_line:
                hooks.append(first_line)
        return drafts

    def _sub_ids(self, c: Candidate) -> list[str]:
        prefix = SETTINGS.subid_prefix
        kind = c.topic.kind if c.topic else "ever"
        sub = [prefix, kind]
        if c.topic:
            slug = re.sub(r"[^a-z0-9]+", "", c.topic.title.lower())[:24]
            if slug:
                sub.append(slug)
        return sub[:5]

    def _product_brief(self, c: Candidate) -> str:
        p = c.product
        bits = []
        if p.sales >= 50:
            bits.append(f"Many people bought this ({p.sales} sold) - you can mention it as proof it sells.")
        if p.rating >= 4.5:
            bits.append(f"Store rating is {p.rating:.1f}/5 - safe to mention.")
        if p.discount_rate >= 15:
            bits.append(f"It is on a {p.discount_rate}% discount right now.")
        if c.reasons:
            bits.append("Reason it fits: " + ", ".join(c.reasons))
        bits.append("Do not invent features that are not in the product name. "
                    "Describe only what the name states.")
        return "\n".join(bits)

    @staticmethod
    def _archetype(c: Candidate) -> str:
        if c.topic and c.topic.kind == "news":
            return "story-driven recommendation"
        if c.product.price_min and c.product.price_min <= 30:
            return "price-drop teaser"
        return "product-as-solution"

    # ------------------------------------------------------------ publishing
    def stage(self, drafts: list[Draft]) -> list[dict[str, Any]]:
        """Write drafts to disk for the operator to approve. Nothing is published."""
        staged = []
        for d in drafts:
            rec = d.to_json()
            rec["created"] = now_myt().isoformat()
            rec["published"] = False
            self.state.add_draft(rec)
            staged.append(rec)
        self.state.save()
        self._write_files(staged)
        return staged

    def _write_files(self, staged: list[dict[str, Any]]) -> None:
        stamp = now_myt().strftime("%Y%m%d-%H%M%S")
        out = DRAFTS / f"drafts-{stamp}.md"
        lines = ["# Threads drafts - staged for approval", "",
                 f"Generated: {now_myt().isoformat()}", ""]
        for i, r in enumerate(staged, 1):
            lines += [
                f"## Draft {i}  |  score {r['score']:.0f}  |  {'OK' if r['ok'] else 'NEEDS FIX'}",
                "",
                f"- product: {r.get('product_name','')}",
                f"- archetype: {r.get('archetype','')}",
                f"- topic: {r.get('topic','')}",
                f"- flags: {r.get('flags') or 'none'}",
                f"- link: {r.get('link','')}",
                f"- subids: {r.get('sub_ids')}",
                "",
                "```text",
                r["text"],
                "```",
                "",
            ]
        out.write_text("\n".join(lines))
        (DRAFTS / "latest.md").write_text("\n".join(lines))

    def publish(self, draft: Draft) -> dict[str, Any]:
        """Publish a single validated draft to Threads."""
        if not self.threads.threads_ready:
            raise ThreadsAuthError("Threads credentials not configured.")
        if self.state.count_today("post") >= SETTINGS.max_posts_per_day:
            raise RuntimeError(f"Daily post budget reached ({SETTINGS.max_posts_per_day}).")

        # weekly ramp quota - the authority is the governor, not the flat cap
        ok, msg = self.governor.can_post()
        if not ok:
            raise RuntimeError(f"Velocity governor blocked the post: {msg}")

        post_id = self.threads.publish(draft.text)
        rec = draft.to_json()
        rec.update({"published": True, "post_id": post_id, "published_at": now_myt().isoformat()})
        self.state.add_post(rec)
        self.state.remember_hook(draft.text.split("\n", 1)[0][:80])
        self.governor.record_post("affiliate")
        self.state.save()
        return rec

    # --------------------------------------------------------------- replies
    def reply(self, comment: str, drafted_reply: str,
              comment_id: str = "") -> dict[str, Any]:
        """Gate and (only if SAFE) send a reply to a comment on our post.

        HOLD    -> queued for human review in the state file
        ESCALATE-> recorded, never answered
        """
        verdict = gate_reply(comment, drafted_reply, state=self.state,
                             comment_id=comment_id)
        if verdict["action"] == "skip":
            return verdict

        ok, msg = self.governor.can_reply()
        if not ok:
            verdict.update({
                "action": "queue",
                "classification": HOLD,
                "message": f"Queued for human review: {msg}",
                "reasons": verdict["reasons"] + [f"velocity:{msg}"],
            })
            self.state.save()
            return verdict

        if verdict["action"] == "send":
            reply_post_id = self.threads.publish(drafted_reply, reply_to_id=comment_id)
            self.governor.record_engagement_reply()
            self.state.remember_reply(comment_id)
            self.state.save()
            verdict.update({"reply_post_id": reply_post_id})
        return verdict

    # ------------------------------------------------------------- reporting
    def health(self) -> str:
        lines = [SETTINGS.status(), "", self.shopee.health(), "", self.threads.token_check()]
        rs = self.threads.rate_state()
        lines += ["", f"budget today: {rs['posts_today']}/{rs['max_posts']} posts, "
                       f"{rs['replies_today']}/{rs['max_replies']} replies"]
        return "\n".join(lines)
