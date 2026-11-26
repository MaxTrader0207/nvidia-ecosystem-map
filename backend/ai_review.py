"""（選用）以 Claude API + 網路搜尋產生「待人工審核」的資料更新建議。

只在設定 ANTHROPIC_API_KEY 時執行。結果寫入 docs/data/ai_review.json，
**不會**自動改寫 data/ecosystem.json——請人工確認來源後再手動修改主資料。
"""
from __future__ import annotations

import json
import os
import re

import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")


def _prompt(eco: dict, news: dict | None) -> str:
    nodes = [{"id": n["id"], "name": n["name"], "amount": n.get("short"), "date": n.get("date"), "status": n.get("status")}
             for n in eco["nodes"] if n["cat"] != "cp"]
    heads = [f"- {i['published'][:10]} {i['title']}（{i['source']}）" for i in (news or {}).get("items", [])[:40]]
    return f"""你是協助維護「NVIDIA 生態資本投資族譜」資料庫的研究助理。主資料最後人工校訂日：{eco['meta']['curated_at']}。

現有節點（JSON）：
{json.dumps(nodes, ensure_ascii=False)}

本週新聞標題（供參考，需自行查證）：
{chr(10).join(heads) or '（無）'}

任務：用網路搜尋查證自校訂日以來，NVIDIA 的股權投資、認股權證、擔保、收購、技術授權有無「實質變化」：
1. 既有節點的金額、狀態（例如完成交割、行使權證、上市、出售）改變；
2. 新的投資對象（現有清單沒有的）；
3. 已報導但尚未定案的事項有了結果（如 Reflection AI、Firmus、Hugging Face 監管核准）。
只收錄有可靠來源（公司新聞稿、SEC、主要財經媒體）的變化；沒有就回傳空陣列。不要臆測。

最後只輸出一個 JSON 陣列（不要其他文字），每個元素格式：
{{"node_id": "既有節點 id 或 null（新對象）", "name": "公司名", "change_type": "金額變更|狀態變更|新投資|定案|其他",
  "summary": "繁體中文一句話說明", "proposed": {{"short": "...", "status": "...", "date": "YYYY-MM-DD"}},
  "sources": [{{"title": "...", "url": "https://..."}}], "confidence": "高|中|低"}}"""


def run(eco: dict, news: dict | None) -> tuple[dict, str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("未設定 ANTHROPIC_API_KEY，略過（選用功能）")
    r = requests.post(API_URL, timeout=300, headers={
        "x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": MODEL, "max_tokens": 6000,
              "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
              "messages": [{"role": "user", "content": _prompt(eco, news)}]})
    r.raise_for_status()
    text = "".join(b.get("text", "") for b in r.json().get("content", []) if b.get("type") == "text")
    m = re.search(r"\[[\s\S]*\]", text)
    items = json.loads(m.group(0)) if m else []
    known = {n["id"] for n in eco["nodes"]}
    for it in items:
        if it.get("node_id") not in known:
            it["node_id"] = None
    return {"model": MODEL, "items": items,
            "disclaimer": "AI 產生之建議，僅供人工審核參考；未經確認前不會寫入主資料。"}, f"{len(items)} 項建議待審核"
