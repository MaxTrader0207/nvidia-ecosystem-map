#!/usr/bin/env python3
"""每週檢查各實體自上次資料截止日（meta.asOf）後的新交易與公告，寫成 pending.json（待人工確認），
再重建 Dashboard。不會自動改 data.json：新資訊一律要人工查證後才併入。

目錄結構（repo 根目錄）：
  template.html、build.py           ← 從 skill 取出
  data/<slug>/data.json             ← 各實體資料
  docs/<Slug>_Ecosystem_Capital_Map.html  ← 輸出（GitHub Pages）
環境變數：ANTHROPIC_API_KEY（必填）、ANTHROPIC_MODEL（預設 claude-sonnet-5-5）、MAX_ITEMS（預設 8）
"""
import json, os, re, subprocess, sys, urllib.request

API = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
MAX_ITEMS = int(os.environ.get("MAX_ITEMS", "8"))

def ask(entity, ticker, since, known):
    prompt = f"""請用網路搜尋，找出「{entity}（{ticker}）」在 {since} 之後新公布的：投資、入股、收購、處分、合資、大型採購或算力合約、融資發債，以及財報、監管裁定等重大公告。
已收錄的交易對象（若只是既有交易的進展，也要列出並在 t 開頭標「更新：」）：{', '.join(known[:60])}
只回傳 JSON 陣列，不要其他文字。每筆格式：{{"d":"YYYY-MM-DD","t":"一句標題","x":"一句說明（含金額）","url":"原始來源網址","counterparty":"對象名稱或空字串"}}。
沒有就回傳 []。最多 {MAX_ITEMS} 筆，日期必須晚於 {since}，網址必須是你實際搜尋到的頁面。"""
    body = {"model": MODEL, "max_tokens": 4000, "messages": [{"role": "user", "content": prompt}],
            "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers={
        "x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r: res = json.load(r)
    text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
    m = re.search(r"\[.*\]", text, re.S)
    try: items = json.loads(m.group(0)) if m else []
    except json.JSONDecodeError: items = []
    return [i for i in items if isinstance(i, dict) and str(i.get("d", "")) > since and str(i.get("url", "")).startswith("http")]

def main(root="."):
    summary = []
    for slug in sorted(os.listdir(os.path.join(root, "data"))):
        p = os.path.join(root, "data", slug, "data.json")
        if not os.path.exists(p): continue
        d = json.load(open(p, encoding="utf-8")); M = d["meta"]
        known = [n["name"] for n in d["nodes"]]
        seen = {e.get("t") for e in d.get("events", [])}
        try: items = [i for i in ask(M["entity"], M.get("ticker", ""), M["asOf"], known) if i.get("t") not in seen]
        except Exception as e:
            print(f"⚠️ {slug}：查詢失敗 {e}"); continue
        pend_p = os.path.join(root, "data", slug, "pending.json")
        old = json.load(open(pend_p, encoding="utf-8")) if os.path.exists(pend_p) else []
        urls = {o.get("url") for o in old}
        merged = old + [i for i in items if i.get("url") not in urls]
        json.dump(merged, open(pend_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out = os.path.join(root, "docs", f"{M.get('fileSlug', slug)}_Ecosystem_Capital_Map.html")
        subprocess.run([sys.executable, os.path.join(root, "build.py"), p, os.path.join(root, "template.html"), out], check=True)
        new = len(merged) - len(old)
        summary.append(f"| {M['entity']} | {new} | {len(merged)} |")
        print(f"✅ {M['entity']}：新增待確認 {new} 筆（累計 {len(merged)}）")
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        with open(s, "a", encoding="utf-8") as f:
            f.write("## 投資生態圈每週檢查\n\n| 實體 | 本週新增待確認 | 累計待確認 |\n|---|---|---|\n" + "\n".join(summary) + "\n")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
