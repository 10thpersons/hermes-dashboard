"""Topic discovery from public RSS feeds. No scraping, no account access.

Sources:
  - Google Trends RSS (geo=MY)      -> what is trending right now in Malaysia
  - Google News RSS (hl=ms-MY)      -> what Malaysians are reading today

Both are public feeds designed for consumption.
"""
from __future__ import annotations

import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import requests

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
}
MYT = timezone(timedelta(hours=8))

TRENDS_URL = "https://trends.google.com/trending/rss?geo=MY"
NEWS_URL = "https://news.google.com/rss?hl=ms-MY&gl=MY&ceid=MY:ms"

# Topics that cannot carry a product. Skip them outright rather than forcing a link.
BLOCK_PATTERNS = re.compile(
    r"\b(football|soccer|pilihan raya|pengenalan|perisu|kecelakaan|bola|liga|"
    r"koncert|korban|merdek[a]?\b.*?\bday\b|per，我就不|meninggal dunia|"
    r"ber.*?\b\b)\b",
    re.I,
)

PRODUCT_HINT = re.compile(
    r"(organiser|organizer|penykap|rack|storage|store|rajin|kemas|rumah|"
    r"dapur|meja|chair|kursi|kaunter|kitchen|tidy|bersih|basuh|penyapu|"
    r"vacuum|vacuum|pendingin|heater|phone|laptop|charger|cable|timing|skincare|"
    r"makeup|serum|kaos|tudung|hijab|kurung|tas|backpack|sepatu|shoes|"
    r"jam|watch|jus|food|lunchbox|thermos|puzzle|toy|mainan|book|stationery)",
    re.I,
)


@dataclass
class Topic:
    title: str
    source: str
    url: str
    published: str = ""
    kind: str = "trend"

    def __str__(self) -> str:
        return f"[{self.kind}/{self.source}] {self.title}"


def _fetch(url: str, timeout: int = 25) -> str:
    r = requests.get(url, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.text


def _clean(title: str) -> str:
    title = re.sub(r"<[^>]+>", "", title)
    title = title.replace("&amp;", "&").replace("&#39;", "'").replace("&quot;", '"')
    title = re.sub(r"\s+", " ", title).strip()
    # Google News appends " - Publisher"; keep it, it carries the source signal.
    return title


def trends(limit: int = 25) -> list[Topic]:
    out: list[Topic] = []
    try:
        root = ET.fromstring(_fetch(TRENDS_URL))
    except Exception:  # noqa: BLE001
        return out
    for item in root.findall(".//item")[:limit]:
        title = _clean(item.findtext("title", ""))
        if not title:
            continue
        traffic = item.findtext("{http://search.yahoo.com/mrss/}approx_traffic", "")
        out.append(Topic(
            title=title,
            source="google-trends",
            url=item.findtext("link", ""),
            published=item.findtext("pubDate", ""),
            kind="trend",
        ))
        if traffic:
            out[-1].published = f"{out[-1].published} | traffic {traffic}"
    return out


def news(limit: int = 30) -> list[Topic]:
    out: list[Topic] = []
    try:
        root = ET.fromstring(_fetch(NEWS_URL))
    except Exception:  # noqa: BLE001
        return out
    for item in root.findall(".//item")[:limit]:
        title = _clean(item.findtext("title", ""))
        if not title:
            continue
        out.append(Topic(
            title=title,
            source="google-news-my",
            url=item.findtext("link", ""),
            published=item.findtext("pubDate", ""),
            kind="news",
        ))
    return out


def _dedupe(topics: list[Topic]) -> list[Topic]:
    seen: set[str] = set()
    out: list[Topic] = []
    for t in topics:
        key = re.sub(r"[^a-z0-9]+", " ", t.title.lower()).strip()[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def product_shaped(topics: list[Topic]) -> list[Topic]:
    """Keep topics that plausibly connect to a physical product."""
    return [t for t in topics if PRODUCT_HINT.search(t.title) or not BLOCK_PATTERNS.search(t.title)]


def harvest(limit: int = 20) -> list[Topic]:
    """Full topic sweep. Returns topics ordered trend-first."""
    topics = _dedupe(trends(30) + news(40))
    return product_shaped(topics)[:limit]


def to_search_keywords(topic: Topic, model_client=None) -> list[str]:
    """Map a topic to Shopee search keywords. Model-assisted when available."""
    if model_client:
        try:
            kws = model_client.keywords_for_topic(topic.title)
            if kws:
                return kws
        except Exception:  # noqa: BLE001
            pass
    words = re.findall(r"[A-Za-z][A-Za-z\-']{2,}", topic.title)
    return [w.lower() for w in words[:3]] or ["organiser"]
