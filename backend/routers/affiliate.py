"""Affiliate bot router - Threads + Shopee affiliate pipeline.

Reads the bot's state files and drives the pipeline through the official APIs:
  - Shopee Affiliate Open API (GraphQL, signed) for product discovery
  - Threads Graph API for publishing
  - Google Trends / News RSS for topic signal

The router never publishes on its own. Publishing requires an explicit
POST /publish with a draft id, and a draft carrying validation flags is
refused unless override=true is passed.
"""
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

BOT_DIR = Path(os.getenv("AFFILIATE_BOT_DIR", "/root/.hermes/work/affiliate-bot"))
RESEARCH_DIR = BOT_DIR / "research"
STATE_FILE = BOT_DIR / "state" / "state.json"
DRAFTS_DIR = BOT_DIR / "drafts"
PYTHON = sys.executable


def _bot_env() -> dict[str, str]:
    """Environment with the bot's package importable."""
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BOT_DIR}:{env.get('PYTHONPATH', '')}"
    return env


def _run(args: list[str], timeout: int = 600) -> dict[str, Any]:
    """Run a bot CLI command and parse its JSON output.

    The CLI prints human text; this wrapper asks for machine output by
    invoking the pipeline modules directly instead.
    """
    cmd = [PYTHON, "-c", args[0]] + args[1:]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            cwd=str(BOT_DIR), env=_bot_env(),
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Bot operation timed out")
    if proc.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail=f"Bot command failed: {(proc.stderr or proc.stdout)[-400:]}",
        )
    return {"output": proc.stdout, "stderr": proc.stderr}


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"posts": [], "drafts": [], "counts": {}, "items_used": [],
                "replied_to": [], "hooks_used": []}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"posts": [], "drafts": [], "counts": {}, "items_used": [],
                "replied_to": [], "hooks_used": []}


def _save_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1, ensure_ascii=False))
    tmp.replace(STATE_FILE)


# --------------------------------------------------------------------- health
@router.get("/health")
async def health():
    """Credential and connection status for every component of the pipeline."""
    script = """
from bot.pipeline import Pipeline
print(Pipeline().health())
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script], capture_output=True, text=True,
            timeout=120, cwd=str(BOT_DIR), env=_bot_env(),
        )
        text = (proc.stdout or "") + (proc.stderr or "")
    except subprocess.TimeoutExpired:
        text = "health check timed out"

    lines = [ln for ln in text.splitlines() if ln.strip()]
    parsed: dict[str, Any] = {"raw": text}
    for ln in lines:
        if ":" not in ln:
            continue
        key, _, val = ln.partition(":")
        k = key.strip().lower().replace(" ", "_")
        parsed[k] = val.strip()

    state = _load_state()
    today = __import__("datetime").datetime.now(
        __import__("datetime").timezone(__import__("datetime").timedelta(hours=8))
    ).strftime("%Y-%m-%d")
    counts = state.get("counts", {})

    parsed["today"] = {
        "posts": counts.get(f"{today}:post", 0),
        "replies": counts.get(f"{today}:reply", 0),
    }
    parsed["totals"] = {
        "posts_published": len(state.get("posts", [])),
        "drafts_generated": len(state.get("drafts", [])),
        "pending_drafts": len([d for d in state.get("drafts", []) if not d.get("published")]),
        "items_promoted": len(state.get("items_used", [])),
        "comments_answered": len(state.get("replied_to", [])),
    }
    return parsed


@router.get("/governor")
async def governor():
    """Weekly ramp quota + reply risk queue. The numbers that protect the account."""
    script = """
import json
from bot.state import State
from bot.velocity import VelocityGovernor

st = State()
gov = VelocityGovernor(state=st)
status = gov.get_status()
mix = gov.get_content_mix()

def cap_num(key):
    return int(str(status.get(key, '0/0')).split('/')[1]) if '/' in str(status.get(key,'')) else 0

def used_num(key):
    return int(str(status.get(key, '0/0')).split('/')[0]) if '/' in str(status.get(key,'')) else 0

print(json.dumps({
    'week': status.get('week'),
    'date': status.get('date'),
    'buckets': [
        {'name': 'Original posts', 'key': 'original_posts',
         'used': used_num('original_posts'), 'cap': cap_num('original_posts')},
        {'name': 'Story chapters', 'key': 'story_chapters',
         'used': used_num('story_chapters'), 'cap': cap_num('story_chapters')},
        {'name': 'Engagement replies', 'key': 'engagement_replies',
         'used': used_num('engagement_replies'), 'cap': cap_num('engagement_replies')},
    ],
    'content_mix': mix,
    'review_queue': st.data.get('review_queue', [])[-25:],
    'escalations': st.data.get('escalations', [])[-25:],
    'replied_count': len(st.data.get('replied_to', [])),
}, default=str, ensure_ascii=False))
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script], capture_output=True, text=True,
            timeout=120, cwd=str(BOT_DIR), env=_bot_env(),
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=502, detail=proc.stderr[-300:])
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Governor status timed out")


# --------------------------------------------------------------------- topics
@router.get("/topics")
async def topics(limit: int = 25):
    """Current topic signal from Google Trends + Google News RSS."""
    script = f"""
import json
from bot.topics import harvest
print(json.dumps([{{'title': t.title, 'source': t.source, 'kind': t.kind,
                   'published': t.published, 'url': t.url}}
                  for t in harvest({int(limit)})], ensure_ascii=False))
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script], capture_output=True, text=True,
            timeout=90, cwd=str(BOT_DIR), env=_bot_env(),
        )
        if proc.returncode != 0:
            raise HTTPException(status_code=502, detail=proc.stderr[-300:])
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Topic harvest timed out")


# ------------------------------------------------------------------ discovery
@router.get("/candidates")
async def candidates(limit: int = 10):
    """Discovered product candidates with fit scores."""
    script = f"""
import json
from bot.pipeline import Pipeline
p = Pipeline()
cands = p.gather_candidates(topic_limit=8)
sel = p.select(cands, n={int(limit)})
print(json.dumps([{{
    'topic': c.topic.title if c.topic else 'evergreen',
    'topic_kind': c.topic.kind if c.topic else 'evergreen',
    'fit': round(c.fit_score, 1),
    'reasons': c.reasons,
    'item_id': c.product.item_id,
    'name': c.product.name,
    'price_min': c.product.price_min,
    'price_max': c.product.price_max,
    'commission_rate': c.product.commission_rate,
    'commission_est': c.product.commission_est,
    'sales': c.product.sales,
    'rating': c.product.rating,
    'shop': c.product.shop_name,
    'offer_link': c.product.offer_link,
    'image': c.product.image_url,
}} for c in sel], ensure_ascii=False))
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script], capture_output=True, text=True,
            timeout=420, cwd=str(BOT_DIR), env=_bot_env(),
        )
        if proc.returncode != 0:
            detail = proc.stderr[-400:]
            if "SHOPEE_API_APP_ID" in detail or "credentials missing" in detail:
                raise HTTPException(status_code=409, detail="Shopee API credentials not configured")
            raise HTTPException(status_code=502, detail=detail)
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Discovery timed out")


# --------------------------------------------------------------------- drafts
@router.get("/drafts")
async def list_drafts():
    """All drafts, pending first."""
    state = _load_state()
    drafts = state.get("drafts", [])
    drafts.sort(key=lambda d: (bool(d.get("published")), -float(d.get("score", 0))))
    return drafts


@router.post("/drafts/generate")
async def generate_drafts(count: int = 3):
    """Run the full pipeline: topics -> products -> drafts. Staged, not published."""
    script = f"""
import json
from bot.pipeline import Pipeline
p = Pipeline()
cands = p.gather_candidates(topic_limit=8)
if not cands:
    print(json.dumps({{'error': 'no candidates', 'detail': 'Shopee API credentials missing or no products'}}))
else:
    sel = p.select(cands, n={int(count)})
    drafts = p.build_drafts(sel)
    staged = p.stage(drafts)
    print(json.dumps({{'staged': len(staged), 'drafts': [
        {{'text': d['text'], 'score': d['score'], 'flags': d['flags'],
          'ok': d['ok'], 'product_name': d['product_name'],
          'archetype': d['archetype'], 'topic': d['topic'],
          'link': d['link'], 'sub_ids': d['sub_ids']}}
        for d in staged]}}, ensure_ascii=False))
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script], capture_output=True, text=True,
            timeout=600, cwd=str(BOT_DIR), env=_bot_env(),
        )
        if proc.returncode != 0:
            detail = proc.stderr[-400:]
            if "credentials missing" in detail:
                raise HTTPException(status_code=409, detail="Shopee API credentials not configured")
            raise HTTPException(status_code=502, detail=detail)
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Draft generation timed out")


class PublishBody(BaseModel):
    draft_index: int
    override: bool = False


@router.post("/publish")
async def publish(body: PublishBody):
    """Publish one staged draft to Threads. Requires an explicit call."""
    state = _load_state()
    pending = [d for d in state.get("drafts", []) if not d.get("published")]
    if not pending:
        raise HTTPException(status_code=404, detail="No pending drafts")
    if body.draft_index < 0 or body.draft_index >= len(pending):
        raise HTTPException(
            status_code=400,
            detail=f"Draft index out of range (0-{len(pending) - 1})",
        )
    draft = pending[body.draft_index]
    if draft.get("flags") and not body.override:
        raise HTTPException(
            status_code=422,
            detail=f"Draft has validation flags: {draft.get('flags')}. "
                   f"Resubmit with override=true to publish anyway.",
        )

    script = """
import json, sys
from bot.state import State
from bot.threads_api import ThreadsAPI
from bot.writer import Draft
from bot.pipeline import Pipeline

idx = int(sys.argv[1])
st = State()
pending = [d for d in st.data.get('drafts', []) if not d.get('published')]
d = pending[idx]
draft = Draft(
    text=d['text'], archetype=d.get('archetype',''), topic=d.get('topic',''),
    product_name=d.get('product_name',''), link=d.get('link',''),
    sub_ids=d.get('sub_ids',[]), score=d.get('score',0),
    flags=d.get('flags',[]), ok=True,
)
rec = Pipeline().publish(draft)
print(json.dumps({'post_id': rec.get('post_id'), 'published_at': rec.get('published_at')}))
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script, str(body.draft_index)],
            capture_output=True, text=True, timeout=120,
            cwd=str(BOT_DIR), env=_bot_env(),
        )
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout)[-400:]
            if "THREADS_USER_ID" in detail or "credentials not configured" in detail:
                raise HTTPException(status_code=409, detail="Threads credentials not configured")
            raise HTTPException(status_code=502, detail=detail)
        result = json.loads(proc.stdout.strip().splitlines()[-1])
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Publish timed out")

    # mark published in the local ledger
    draft["published"] = True
    draft["post_id"] = result.get("post_id")
    draft["published_at"] = result.get("published_at")
    state.setdefault("posts", []).append(draft)
    _save_state(state)
    return result


@router.post("/drafts/reject")
async def reject_drafts(indices: list[int]):
    """Mark drafts as published (so they drop out of the queue) without posting."""
    state = _load_state()
    pending = [d for d in state.get("drafts", []) if not d.get("published")]
    for i in indices:
        if 0 <= i < len(pending):
            pending[i]["published"] = True
            pending[i]["rejected"] = True
    _save_state(state)
    return {"rejected": len(indices)}


# --------------------------------------------------------------------- report
@router.get("/report")
async def report():
    """Revenue and performance snapshot from local ledger + Shopee conversions."""
    state = _load_state()
    posts = state.get("posts", [])
    published = [p for p in posts if p.get("post_id") and not p.get("rejected")]

    by_archetype: dict[str, dict[str, Any]] = {}
    for p in published:
        a = p.get("archetype", "unknown")
        e = by_archetype.setdefault(a, {"count": 0, "score_sum": 0.0})
        e["count"] += 1
        e["score_sum"] += float(p.get("score", 0))
    for a, e in by_archetype.items():
        e["avg_score"] = round(e["score_sum"] / max(1, e["count"]), 1)
        del e["score_sum"]

    conversions: list[dict[str, Any]] = []
    conv_error = None
    script = """
import json
from bot.shopee_api import ShopeeOpenAPI
try:
    rows = ShopeeOpenAPI().conversion_report(limit=50)
    print(json.dumps(rows, default=str))
except Exception as e:
    print(json.dumps({'error': str(e)}))
"""
    try:
        proc = subprocess.run(
            [PYTHON, "-c", script], capture_output=True, text=True,
            timeout=120, cwd=str(BOT_DIR), env=_bot_env(),
        )
        if proc.returncode == 0:
            payload = json.loads(proc.stdout.strip().splitlines()[-1])
            if isinstance(payload, dict) and payload.get("error"):
                conv_error = payload["error"]
            elif isinstance(payload, list):
                conversions = payload
            else:
                conv_error = "unexpected conversion report shape"
        else:
            conv_error = (proc.stderr or "")[-200:]
    except subprocess.TimeoutExpired:
        conv_error = "conversion report timed out"

    total_commission = 0.0
    for c in conversions:
        try:
            total_commission += float(c.get("totalCommission") or 0)
        except (TypeError, ValueError):
            pass

    return {
        "posts_published": len(published),
        "posts_total": len(posts),
        "by_archetype": by_archetype,
        "conversions": conversions,
        "conversion_count": len(conversions),
        "total_commission": round(total_commission, 2),
        "conversion_error": conv_error,
        "items_promoted": len(state.get("items_used", [])),
        "comments_answered": len(state.get("replied_to", [])),
    }


# -------------------------------------------------------------------- research
@router.get("/research")
async def research():
    """Corpus + style guide metadata so the page can show what the bot learned from."""
    files = []
    for name in ("manglish_threads_corpus.md", "manglish_style_guide.md",
                 "lexicon_counts.txt", "corpus_clean.txt"):
        p = RESEARCH_DIR / name
        if p.exists():
            text = p.read_text(errors="ignore")
            files.append({
                "name": name,
                "bytes": p.stat().st_size,
                "lines": text.count("\n") + 1,
            })
    counts = {}
    lex = RESEARCH_DIR / "lexicon_counts.txt"
    if lex.exists():
        for line in lex.read_text().splitlines()[:25]:
            if "\t" in line:
                w, _, c = line.partition("\t")
                counts[w] = int(c)
    return {"files": files, "top_lexicon": counts}
