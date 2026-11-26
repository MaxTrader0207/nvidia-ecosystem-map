#!/usr/bin/env python3
"""開啟 docs/ 下每一份 Dashboard 與總網路圖，切換所有分頁並點第一張卡片，回報瀏覽器錯誤。
用法：python3 test_all.py [資料夾，預設 docs]   需要：pip install playwright && playwright install chromium"""
import asyncio, glob, os, sys
from playwright.async_api import async_playwright
async def main(folder):
    files = sorted(f for f in glob.glob(os.path.join(folder, "*.html")) if "template" not in os.path.basename(f) and os.path.basename(f) != "index.html"); bad = 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for f in files:
            pg = await b.new_page(viewport={"width": 1500, "height": 950}); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto("file://" + os.path.abspath(f)); await pg.wait_for_timeout(300)
            for t in await pg.query_selector_all("nav.tabs button"):
                if await t.is_visible(): await t.click(); await pg.wait_for_timeout(80)
            first = await pg.query_selector("nav.tabs button")
            if first: await first.click()
            card = await pg.query_selector(".lcard") or await pg.query_selector("#g .node")
            if card: await card.click(); await pg.wait_for_timeout(80)
            cards = len(await pg.query_selector_all(".lcard, #g .node"))
            print(("✅" if not errs and cards else "❌"), os.path.basename(f), f"節點 {cards}", errs[:2] or "")
            bad += bool(errs) or not cards; await pg.close()
        await b.close()
    print(f"共 {len(files)} 份，{bad} 份有問題"); sys.exit(1 if bad else 0)
asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "docs"))
