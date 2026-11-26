"""Google News RSS：抓近 7 天 NVIDIA 投資相關新聞，並標記涉及的族譜節點。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from common import TPE, http_get

QUERIES = [
    ("en", '(Nvidia OR NVDA) (invest OR investment OR stake OR warrant OR acquire OR acquisition OR "funding round" OR guarantee) when:7d',
     "hl=en-US&gl=US&ceid=US:en"),
    ("zh", '(輝達 OR NVIDIA) (投資 OR 入股 OR 收購 OR 認股權證 OR 持股 OR 擔保) when:7d', "hl=zh-TW&gl=TW&ceid=TW:zh-Hant"),
]
MAX_ITEMS = 80


def _norm(t: str) -> str:
    return re.sub(r"\W+", "", t.lower())


def _matchers(eco: dict, aliases: dict) -> list[tuple[str, re.Pattern]]:
    out = []
    for n in eco["nodes"]:
        words = aliases.get(n["id"]) or [re.sub(r"[（(].*$", "", n["name"]).strip()]
        pats = []
        for w in words:
            w = re.escape(w)
            # 英數字詞加字界，避免 "Intel" 命中 "intelligence"
            pats.append(rf"(?<![A-Za-z]){w}(?![A-Za-z])" if re.match(r"^[\w\\ .-]+$", w, re.A) else w)
        out.append((n["id"], re.compile("|".join(pats), re.I)))
    return out


def run(eco: dict, holdings_cfg: dict, prev: dict | None) -> tuple[dict, str]:
    matchers = _matchers(eco, holdings_cfg.get("news_aliases", {}))
    prev_links = {i["link"] for i in (prev or {}).get("items", [])}
    first_run = not prev_links
    seen, items, errors = set(), [], []
    for lang, q, params in QUERIES:
        try:
            xml = http_get(f"https://news.google.com/rss/search?q={quote_plus(q)}&{params}").text
            root = ET.fromstring(xml)
        except Exception as e:  # noqa: BLE001
            errors.append(f"{lang}: {e}")
            continue
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            src_el = it.find("source")
            source = (src_el.text or "").strip() if src_el is not None else ""
            if source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
            key = _norm(title)
            if not title or key in seen:
                continue
            seen.add(key)
            try:
                pub = parsedate_to_datetime(it.findtext("pubDate")).astimezone(TPE).isoformat(timespec="minutes")
            except Exception:  # noqa: BLE001
                pub = ""
            link = it.findtext("link") or ""
            items.append({"title": title, "link": link, "source": source, "published": pub, "lang": lang,
                          "nodes": [nid for nid, p in matchers if p.search(title)],
                          "is_new": (not first_run) and link not in prev_links})
    if not items and errors:
        raise RuntimeError("; ".join(errors))
    items.sort(key=lambda x: x["published"], reverse=True)
    items = items[:MAX_ITEMS]
    out = {"window": "近 7 天", "queries": [q for _, q, _ in QUERIES], "items": items, "errors": errors}
    tagged = sum(1 for i in items if i["nodes"])
    return out, f"{len(items)} 則新聞，其中 {tagged} 則涉及族譜節點"
