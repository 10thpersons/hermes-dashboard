"""Manglish post writer.

Grounded in research/manglish_style_guide.md, which was derived from 100 observed
Malaysian Threads accounts. The style guide is loaded verbatim into the system
prompt so the model writes against measured corpus patterns rather than guesses.

Hard filters enforced after generation:
  - no Indonesian/Singlish slang
  - no CJK characters
  - no AI-tell phrases
  - disclosure present
  - length band
  - emoji ceiling
  - exactly one link
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

import requests

from .config import SETTINGS, RESEARCH

# --------------------------------------------------------------------- filters
INDONESIAN_ONLY = [
    "gue", "gua", "nggak", "banget", "kayak", "pake", "doang", "bang", "split",
    "shiok", "shok", "lor", "sia", "tapao", "korek", "snap", "bikin", "ceki",
    "ribet", "rame", "dong", "mobil", "kereta", "kota", "kampus", "bayar",
    "mendingan", "mending", "penginapan", "kekhawatiran", "sinyal", "kejar",
    "gampang", "ribu", "ribet", "kasih", "dong", "biar", "aja",
]
FORBIDDEN_PHRASES = [
    "in today's", "in this digital", "let's dive", "here's the ultimate",
    "whether you're", "game-changer", "game changer", "must-have", "must have",
    "unlock", "elevate", "seamless", "link in bio", "dm me", "shop now",
    "don't miss out", "worth every penny", "go-to", "hidden gem", "unbeatable",
    "premium quality", "best-in-class", "game changing", "revolutionary",
    "shop the", "add to cart", "limited time", "act now", "don't miss",
]
AI_STRUCTURE = [
    "Furthermore", "Moreover", "In conclusion", "Overall,", "Additionally",
    "It is important to note", "In summary", "That being said", "At the end of the day",
]
CJK = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F\u2190-\u21FF]")
MALAY_CORE = [
    "ni", "je", "korang", "aku", "saya", "tak", "boleh", "nak", "guna", "cuba",
    "tengok", "tapi", "dah", "macam", "mcm", "sbb", "mmg", "gila", "kena",
    "rm", "sini", "tu", "bagi", "memang", "sangat", "best", "murah", "pasti",
    "la", "lah", "aku", "kita", "orang", "rumah", "semalam", "harini",
]
DISCLOSURE_MARKERS = ["affiliate", "komisen"]


@dataclass
class Draft:
    text: str
    archetype: str = ""
    hook: str = ""
    topic: str = ""
    product_name: str = ""
    link: str = ""
    sub_ids: list[str] = field(default_factory=list)
    score: float = 0.0
    flags: list[str] = field(default_factory=list)
    ok: bool = False
    raw: str = ""

    def to_json(self) -> dict[str, Any]:
        return {
            "text": self.text, "archetype": self.archetype, "hook": self.hook,
            "topic": self.topic, "product_name": self.product_name, "link": self.link,
            "sub_ids": self.sub_ids, "score": self.score, "flags": self.flags, "ok": self.ok,
        }


def _word_match(word: str, text_lower: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(word) + r"(?![a-z])", text_lower) is not None


def validate(text: str, link_placeholder: str = "[LINK]") -> tuple[float, list[str]]:
    """Score a draft and list violations. 0-100, higher is better."""
    t = text.strip()
    low = t.lower()
    flags: list[str] = []
    score = 100.0

    if not t:
        return 0.0, ["empty"]

    # --- Indonesian / Singlish leak (hard) ---
    leaks = [w for w in INDONESIAN_ONLY if _word_match(w, low)]
    if leaks:
        score -= 30 * min(len(leaks), 3)
        flags.append("indonesian:" + ",".join(leaks[:4]))

    # --- CJK leak (hard) ---
    cjk = CJK.findall(t)
    if cjk:
        score -= 40
        flags.append("cjk:" + "".join(sorted(set(cjk))[:6]))

    # --- AI phrases ---
    ai = [p for p in FORBIDDEN_PHRASES if p in low]
    if ai:
        score -= 8 * min(len(ai), 4)
        flags.append("ai_phrase:" + ",".join(ai[:3]))

    # --- AI structure ---
    st = [p for p in AI_STRUCTURE if p in t]
    if st:
        score -= 10 * min(len(st), 2)
        flags.append("ai_struct:" + ",".join(st[:2]))

    # --- Manglish density ---
    words = re.findall(r"[a-zA-Z']+", low)
    if words:
        hits = sum(1 for w in words if w in MALAY_CORE)
        density = hits / len(words)
        if density < 0.12:
            score -= 20
            flags.append(f"low_manglish:{density:.2f}")
        elif density < 0.18:
            score -= 8
            flags.append(f"thin_manglish:{density:.2f}")

    # --- disclosure ---
    if not any(m in low for m in DISCLOSURE_MARKERS):
        score -= 25
        flags.append("no_disclosure")

    # --- length ---
    n = len(t)
    if n < 100:
        score -= 15
        flags.append(f"too_short:{n}")
    elif n > 560:
        score -= 12
        flags.append(f"too_long:{n}")

    # --- emoji ---
    emo = len(EMOJI.findall(t))
    if emo > 5:
        score -= 10
        flags.append(f"emoji_bomb:{emo}")

    # --- link count ---
    if low.count(link_placeholder.lower()) != 1:
        score -= 12
        flags.append("link_placeholder_count")

    # --- fake personal use claim ---
    if re.search(r"aku (dah|pemang) (guna|try|pakai)", low) and not getattr(validate, "_allow_use", False):
        score -= 12
        flags.append("possible_fake_use")

    # --- fake scarcity ---
    if re.search(r"(hanya (3|tiga|2|dua) (orang|baki)|last chance|hujung dunia|jomlahan|sikit lagi je)", low):
        score -= 15
        flags.append("fake_scarcity")

    return max(0.0, score), flags


class Writer:
    """Generates Manglish drafts against the corpus-derived style guide."""

    def __init__(self, model: str | None = None, base: str | None = None,
                 key: str | None = None, style_guide: Path | None = None):
        self.model = model or SETTINGS.model
        self.base = (base or SETTINGS.rootsys_base).rstrip("/")
        self.key = key or SETTINGS.rootsys_key
        self.style_guide = style_guide or (RESEARCH / "manglish_style_guide.md")
        self.session = requests.Session()
        self._guide_cache: str | None = None

    # ------------------------------------------------------------------ prompt
    def _guide(self) -> str:
        if self._guide_cache is None:
            try:
                self._guide_cache = self.style_guide.read_text()
            except Exception:  # noqa: BLE001
                self._guide_cache = ""
        return self._guide_cache

    def _system(self) -> str:
        guide = self._guide()
        guide_block = guide[:14000] if guide else "(style guide unavailable - follow the rules below)"
        return f"""You write for a Malaysian Shopee-affiliate Threads account that must read like a real Malaysian person, never like AI.

STYLE GUIDE derived from 100 observed Malaysian Threads accounts:
---
{guide_block}
---

NON-NEGOTIABLE RULES:
1. Malaysian Manglish. Never Indonesian (gue, gua, nggak, banget, kayak, pake, doang, bikin, ribet, rame, dong) and never Singlish (shiok, can, lor, sia, tapao).
2. Never output Chinese, Japanese or Korean characters.
3. Never use: "in today's world", "game-changer", "must-have", "unlock", "elevate", "seamless", "link in bio", "DM me", "shop now", "don't miss out", "worth every penny".
4. One plain-language affiliate disclosure near the commercial part. Example: "link ni affiliate link, kalau ada beli aku dapat komisen".
5. Do NOT claim personal use unless the brief explicitly states you used it. Prefer "baru jumpa" / "nak cuba" over "aku dah guna".
6. No fake scarcity. No competitor bashing. No unverifiable superlatives like "paling murah" or "terbaik" - prefer "murah je", "nampak berbaloi".
7. Exactly one link placeholder: [LINK]
8. Under 500 characters. 0 to 3 emoji, placed at an emotional beat, never one per sentence.
9. Lowercase casual tone, short clause-stacked sentences, not polished paragraphs.
10. Do not output anything except the post body itself."""

    # ------------------------------------------------------------------- call
    def _complete(self, prompt: str, max_tokens: int = 500, temperature: float = 0.8) -> str:
        r = self.session.post(
            self.base + "/chat/completions",
            headers={"Authorization": f"Bearer {self.key}", "Content-Type": "application/json"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": self._system()},
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens,
                "temperature": temperature,
            },
            timeout=180,
        )
        if not r.ok:
            raise RuntimeError(f"model {self.model} HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["choices"][0]["message"]["content"].strip()

    # ------------------------------------------------------------------ clean
    # Artefacts some models emit that must never reach a published post.
    _LEADING_META = re.compile(
        r"^(?:\[@[\w .\-]+\]\s*|"
        r"(?:here(?:'s| is)[^\n]{0,120}\n|"
        r"this (?:post|thread|fits|works)[^\n]{0,120}\n|"
        r"(?:draft|post|caption|version)\s*[:\-][^\n]{0,80}\n))",
        re.I,
    )

    @classmethod
    def _clean(cls, raw: str) -> str:
        t = raw.strip()
        # strip markdown fences
        t = re.sub(r"^```(?:text|markdown)?\s*|\s*```$", "", t, flags=re.S).strip()
        # strip any leading marker or meta preamble the model leaked in
        prev = None
        while prev != t:
            prev = t
            t = cls._LEADING_META.sub("", t).strip()
            t = re.sub(r'^["“\']|["”\']$', "", t).strip()
        # strip a trailing meta note like "Archetype: ..." or "Note: ..."
        t = re.split(r"\n\s*(?:archetype|note|hook)\s*[:\-]", t, maxsplit=1, flags=re.I)[0].strip()
        # collapse >2 blank lines
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t

    # ----------------------------------------------------------------- repair
    def _repair_hint(self, flags: list[str], text: str) -> str:
        """Turn validation flags into concrete corrective instructions."""
        hints: list[str] = []
        for f in flags:
            if f.startswith("too_long"):
                n = len(text)
                hints.append(f"Your draft is {n} characters. Cut it to under 460 characters. "
                             f"Drop the middle paragraph. Keep only: one relatable opening line, "
                             f"two short sentences about the product, the disclosure, [LINK].")
            elif f.startswith("too_short"):
                hints.append("Your draft is too short. Add one concrete detail about the "
                             "situation and one about the product. Stay under 460 characters.")
            elif f.startswith("thin_manglish") or f.startswith("low_manglish"):
                hints.append("Too much English, not enough Malay. Rewrite using Malaysian "
                             "particles: korang, je, la, dah, tak, nak, boleh, tengok, "
                             "macam, sbb. Aim for Malay in roughly three out of every four words.")
            elif f.startswith("indonesian"):
                bad = f.split(":", 1)[1] if ":" in f else ""
                hints.append(f"You used Indonesian/Singlish words ({bad}). Replace them with "
                             f"Malaysian equivalents: gue/gua->aku, banget->gila, nggak->tak, "
                             f"kayak->macam, pake->guna, doang->je, dibikin->dibuat.")
            elif f.startswith("cjk"):
                hints.append("You included Chinese characters. Remove every non-Latin "
                             "character and rewrite that part in Malay.")
            elif f.startswith("ai_phrase"):
                bad = f.split(":", 1)[1] if ":" in f else ""
                hints.append(f"Remove the marketing phrases ({bad}). Write plainly, like a "
                             f"person typing on their phone.")
            elif f.startswith("ai_struct"):
                hints.append("Remove the formal connective words. Write like spoken Malay.")
            elif f.startswith("no_disclosure"):
                hints.append("Add one plain line stating the link is an affiliate link and "
                             "that you earn a commission, placed just before [LINK].")
            elif f.startswith("fake_scarcity"):
                hints.append("Remove the scarcity claim. Say only what is verifiable.")
            elif f.startswith("emoji_bomb"):
                hints.append("Too many emoji. Keep at most 2.")
            elif f.startswith("link_placeholder_count"):
                hints.append("Include [LINK] exactly once.")
        if not hints:
            hints.append("Tighten the post. Shorter, more Malay, more natural.")
        return "\n".join(f"- {h}" for h in hints)

    def write(self, product, topic: str = "", extra: str = "",
              archetype: str = "", used_hooks: list[str] | None = None,
              attempts: int = 3) -> Draft:
        """Write one post for one product. Repairs the draft if validation fails."""
        price_line = f"RM{product.price_min:g}" if product.price_min else ""
        if product.price_max and product.price_max != product.price_min:
            price_line += f"-RM{product.price_max:g}"

        facts = [
            f"product name: {product.name}",
            f"price shown on Shopee: {price_line}",
            f"sold count: {product.sales}",
            f"store rating: {product.rating:.1f} / 5" if product.rating else "",
            f"shop: {product.shop_name}",
            f"discount: {product.discount_rate}%" if product.discount_rate else "",
        ]
        facts = [f for f in facts if f]

        arch = archetype or "product-as-solution"
        avoid = ""
        if used_hooks:
            avoid = ("Do not reuse these hook openings that were already used: "
                     + "; ".join(used_hooks[:5]))

        brief = f"""Write ONE Threads post promoting this Shopee product.

PRODUCT FACTS (use only these, do not invent more):
{chr(10).join('- ' + f for f in facts)}

CURRENT TOPIC TO RIDE (tie the post to it only if it fits naturally - if it does not fit, write an evergreen relatable post instead, never force the link):
{topic or '(none - write evergreen relatable)'}

TARGET ARCHETYPE: {arch}

{extra}

{avoid}

HARD LENGTH LIMIT: the whole post must be under 460 characters including [LINK].
Structure: one relatable opening line -> two short sentences about the product -> one disclosure line -> [LINK]
Output only the post body. No preamble, no notes, no explanation of your choices."""

        best: Draft | None = None
        feedback = ""
        for attempt in range(attempts):
            prompt = brief if not feedback else (
                brief + "\n\nYOUR PREVIOUS DRAFT HAD PROBLEMS. FIX THEM:\n" + feedback +
                "\n\nRewrite the whole post from scratch. Output only the post body."
            )
            try:
                raw = self._complete(prompt)
            except Exception:  # noqa: BLE001
                if best is not None:
                    break
                raise
            text = self._clean(raw)
            score, flags = validate(text)
            d = Draft(
                text=text, archetype=arch, topic=topic, product_name=product.name,
                link="[LINK]", score=score, flags=flags,
                ok=(score >= 88 and not flags), raw=raw,
            )
            if best is None or d.score > best.score:
                best = d
            if d.ok:
                return d
            feedback = self._repair_hint(flags, text)
            time.sleep(0.6)
        assert best is not None
        return best

    def write_reply(self, comment: str, product, history: list[str] | None = None) -> Draft:
        """Write a reply to a comment. Short, direct, Manglish."""
        facts = [
            f"price on Shopee: RM{product.price_min:g}",
            f"store rating: {product.rating:.1f}/5" if product.rating else "",
            f"shop: {product.shop_name}",
        ]
        facts = [f for f in facts if f]
        brief = f"""Write ONE short reply to a comment on a Threads post. One to three sentences only.

THE COMMENT: "{comment}"

PRODUCT FACTS (use only these):
{chr(10).join('- ' + f for f in facts)}

RULES:
- Answer the actual question first, then one useful detail.
- Never invent a personal purchase or usage history. If asked "did you buy it" and you did not, say so plainly.
- Never guarantee authenticity, delivery or commission.
- Do not argue. Do not bash another seller or platform.
- Keep it under 300 characters. No emoji needed.
- No [LINK] placeholder in a reply unless the comment explicitly asks where to buy.
- Output only the reply text."""
        raw = self._complete(brief, max_tokens=200, temperature=0.6)
        text = self._clean(raw)
        score, flags = validate(text)
        # replies do not need disclosure or a link
        relaxed = [f for f in flags if f not in ("no_disclosure", "link_placeholder_count", "too_short")]
        score = max(score, 100 - 20 * len(relaxed))
        return Draft(text=text, archetype="reply", score=score, flags=relaxed,
                     ok=(not relaxed), raw=raw)

    def keywords_for_topic(self, topic_title: str) -> list[str]:
        """Ask the model which Shopee search keywords fit a topic."""
        try:
            out = self._complete(
                "List 3 Shopee Malaysia search keywords for this topic, comma separated, "
                "physical products only, lowercase, no explanation.\n\nTOPIC: " + topic_title,
                max_tokens=60, temperature=0.3,
            )
            kws = [re.sub(r"[^a-z0-9 \-]", "", k.strip().lower()) for k in out.split(",")]
            return [k for k in kws if 2 < len(k) < 30][:3]
        except Exception:  # noqa: BLE001
            return []

    # ------------------------------------------------------------------ clean
    @staticmethod
    def _clean(raw: str) -> str:
        t = raw.strip()
        # strip markdown fences and quote wrappers
        t = re.sub(r"^```(?:text)?\s*|\s*```$", "", t, flags=re.S).strip()
        t = re.sub(r'^["“\']|["”\']$', "", t).strip()
        # remove leading labels the model sometimes adds
        t = re.sub(r"^(post|thread|caption)\s*[:\-]\s*", "", t, flags=re.I)
        # collapse >2 blank lines
        t = re.sub(r"\n{3,}", "\n\n", t)
        return t
