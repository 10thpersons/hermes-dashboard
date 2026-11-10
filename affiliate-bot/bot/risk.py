"""Risk gate for auto-generated replies: SAFE / HOLD / ESCALATE.

  SAFE      -> may auto-draft the reply
  HOLD      -> stage the draft for human approval
  ESCALATE  -> do NOT reply at all; log for the operator

Ported from the legacy risk_classifier. The legacy version asked an LLM for a
one-word verdict (and embedded an API key; that key is NOT carried over).
Its rubric was: ESCALATE = hostile/accusatory ("scam", "fake", "bot")/legal/bait;
HOLD = ambiguous/sarcastic or unsourced result/money/health claims; else SAFE.
This port is deterministic (stdlib only) so it is testable and fail-closed;
an optional ``llm`` callable can only RAISE severity, never lower it.

Precedence: ESCALATE > HOLD > SAFE.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable

from .state import State, now_myt

SAFE, HOLD, ESCALATE = "SAFE", "HOLD", "ESCALATE"
_RANK = {SAFE: 0, HOLD: 1, ESCALATE: 2}

# ---------------------------------------------------------------- ESCALATE
# category -> terms (word-boundary matched; phrases allowed)
ESCALATE_TERMS: dict[str, list[str]] = {
    "scam_fraud": [
        "scam", "scams", "scammed", "scammer", "scammers", "scamming", "fraud",
        "fraudulent", "fake", "fakes", "bot", "bots", "tipu", "ditipu", "penipu",
        "menipu", "penipuan", "kena tipu", "rip off", "ripped off", "ripoff",
        "con artist", "misleading", "false advertising", "shady",
    ],
    "refund": [
        "refund", "refunds", "refunded", "money back", "chargeback", "return my money",
        "duit balik", "nak refund", "pulangkan duit", "tuntut balik",
    ],
    "authenticity": [
        "authentic", "authenticity", "original ke", "ori ke", "legit ke", "is it legit",
        "is this legit", "is it original", "is it genuine", "is this genuine",
        "genuine ke", "real or fake", "original or fake", "tiruan", "copy ke",
        "counterfeit", "knockoff", "knock off", "kw", "tak original",
    ],
    "legal_threat": [
        "lawyer", "legal action", "sue", "sue you", "lawsuit", "court", "police",
        "polis", "authorities", "report you", "reported", "reporting you", "report this",
        "complaint", "complain", "kkm", "kpdnhep", "mcmc", "consumer tribunal",
        "tribunal", "i will report", "expose you", "expose this",
    ],
    "threat": [
        "kill you", "hurt you", "hunt you", "ruin you", "bunuh",
        "i will find", "watch your back", "you will pay", "tunggu je",
    ],
    "abuse": [
        "idiot", "stupid", "moron", "dumb", "shut up", "fuck", "fucking", "shit",
        "bastard", "bitch", "asshole", "scum", "trash", "garbage", "bodoh", "babi",
        "anjing", "sial", "bangang", "pukimak", "puki", "lancau", "celaka",
        "bangsat", "useless", "loser",
    ],
}

# Competitor names: a mention alone is HOLD, a dispute/comparison is ESCALATE.
COMPETITOR_NAMES = [
    "lazada", "tiktok shop", "tiktokshop", "temu", "aliexpress", "amazon",
    "shein", "taobao", "mr diy", "mydin", "watsons", "guardian",
]
COMPETITOR_DISPUTE_TERMS = [
    "cheaper", "murah", "better", "worse", "lagi bagus", "lagi murah", "rip off",
    "overpriced", "mahal", "scam", "fake", "boycott", "switch to", "why not",
    "better than shopee", "shopee is", "shopee tipu", "shopee scam",
]

# ----------------------------------------------------------------- HOLD
HOLD_TERMS: dict[str, list[str]] = {
    "skeptic_sarcasm": [
        "too good to be true", "sure,", "yeah right", "yea right", "riiight",
        "bold claim", "skeptical", "sceptical", "doubt it", "doubt la", "cap",
        "how much did they pay", "paid to say", "paid promo", "sponsored", "is this an ad",
        "ye ke", "betul ke", "really?", "seriously?", "so you're saying",
        "so you are saying", "fixes everything", "what's the catch", "whats the catch",
        "🙄", "🤡", "🙃", "/s",
    ],
    "health_claim": [
        "cure", "cures", "heal", "heals", "lose weight", "weight loss", "slimming",
        "diabetes", "cancer", "pregnant", "pregnancy", "baby safe", "safe for baby",
        "side effect", "side effects", "allergy", "allergic", "doctor", "medical",
        "treat", "treats", "pain relief", "kurus", "sakit",
    ],
    "money_claim": [
        "guaranteed", "guarantee", "make money", "get rich", "passive income",
        "income", "profit", "earn rm", "jackpot", "100%", "risk free", "risk-free",
    ],
    "unverifiable_product": [
        "halal", "warranty", "waranti", "sirim", "kkm approved", "expired",
        "damaged", "rosak", "not delivered", "never arrived", "belum sampai",
        "wrong item", "salah barang",
    ],
}

# Applied to our DRAFTED reply only (unsourced claims we'd be making).
REPLY_HOLD_TERMS = [
    "guaranteed", "guarantee", "100%", "cure", "cures", "heal", "heals",
    "lose weight", "make money", "get rich", "risk free", "risk-free",
    "doctor recommended", "clinically proven", "proven to", "no side effects",
    "authentic", "original", "genuine", "legit", "halal",
]


def _compile(terms: list[str]) -> re.Pattern[str]:
    parts = []
    for t in sorted(set(terms), key=len, reverse=True):
        esc = re.escape(t.lower())
        pre = r"(?<!\w)" if t[0].isalnum() else ""
        post = r"(?!\w)" if t[-1].isalnum() else ""
        parts.append(f"{pre}{esc}{post}")
    return re.compile("|".join(parts))


_ESC_RE = {k: _compile(v) for k, v in ESCALATE_TERMS.items()}
_HOLD_RE = {k: _compile(v) for k, v in HOLD_TERMS.items()}
_COMP_RE = _compile(COMPETITOR_NAMES)
_COMP_DISPUTE_RE = _compile(COMPETITOR_DISPUTE_TERMS)
_REPLY_HOLD_RE = _compile(REPLY_HOLD_TERMS)


@dataclass
class RiskResult:
    verdict: str                       # SAFE | HOLD | ESCALATE
    reasons: list[str] = field(default_factory=list)  # "category:term"

    @property
    def action(self) -> str:
        return {SAFE: "send", HOLD: "queue", ESCALATE: "skip"}[self.verdict]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def classify(
    comment: str,
    drafted_reply: str = "",
    llm: Callable[[str, str], str] | None = None,
) -> RiskResult:
    """Classify a comment (+ optional drafted reply). Deterministic.

    llm: optional callable(comment, reply) -> 'SAFE'|'HOLD'|'ESCALATE'. Its
    answer is used only if more severe than the rules; errors are treated as
    HOLD (fail closed), as in the legacy API-failure path.
    """
    c, r = _norm(comment), _norm(drafted_reply)
    esc: list[str] = []
    hold: list[str] = []

    for cat, rx in _ESC_RE.items():
        for m in rx.finditer(c):
            esc.append(f"{cat}:{m.group(0)}")

    if _COMP_RE.search(c):
        if _COMP_DISPUTE_RE.search(c):
            esc.append(f"competitor_dispute:{_COMP_RE.search(c).group(0)}")
        else:
            hold.append(f"competitor_mention:{_COMP_RE.search(c).group(0)}")

    if esc:
        return RiskResult(ESCALATE, esc)

    for cat, rx in _HOLD_RE.items():
        for m in rx.finditer(c):
            hold.append(f"{cat}:{m.group(0)}")
    for m in _REPLY_HOLD_RE.finditer(r):
        hold.append(f"reply_claim:{m.group(0)}")

    result = RiskResult(HOLD if hold else SAFE, hold)

    if llm is not None:
        try:
            v = str(llm(comment, drafted_reply)).strip().upper()
            v = next((k for k in (ESCALATE, HOLD, SAFE) if k in v), HOLD)
        except Exception:
            v = HOLD
        if _RANK[v] > _RANK[result.verdict]:
            result = RiskResult(v, result.reasons + [f"llm:{v}"])
    return result


def gate_reply(
    comment: str,
    drafted_reply: str,
    state: State | None = None,
    comment_id: str = "",
    llm: Callable[[str, str], str] | None = None,
) -> dict:
    """Gate a drafted reply. Returns
    {action: 'send'|'queue'|'skip', classification, message, reasons}.

    HOLD     -> appended to state.data['review_queue'] (reviewed=False)
    ESCALATE -> appended to state.data['escalations']; no reply is sent
    State is saved only when an entry is written.
    """
    res = classify(comment, drafted_reply, llm=llm)
    out = {
        "action": res.action,
        "classification": res.verdict,
        "reasons": res.reasons,
        "message": {
            SAFE: "Auto-approved, ok to reply",
            HOLD: "Queued for human review",
            ESCALATE: "Escalated: do not reply",
        }[res.verdict],
    }
    if res.verdict == SAFE:
        return out
    st = state or State()
    entry = {
        "comment_id": comment_id,
        "comment": comment,
        "classification": res.verdict,
        "reasons": res.reasons,
        "timestamp": now_myt().isoformat(),
        "reviewed": False,
    }
    if res.verdict == HOLD:
        entry["drafted_reply"] = drafted_reply
        st.data.setdefault("review_queue", []).append(entry)
        st.data["review_queue"] = st.data["review_queue"][-200:]
    else:
        st.data.setdefault("escalations", []).append(entry)
        st.data["escalations"] = st.data["escalations"][-200:]
    st.save()
    return out
