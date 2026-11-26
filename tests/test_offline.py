"""離線測試：以各資料源真實格式的假資料取代網路請求，驗證整條更新流程。

用法（在暫存複本執行，避免把假資料寫進 docs/data）：
    python tests/test_offline.py
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent.parent

PRICE_930 = {"SPCX": 150.83, "INTC": 120.25, "CRWV": 132.0, "COHR": 287.2, "SNPS": 434.5, "NOK": 10.16,
             "NBIS": 118.0, "IREN": 64.0, "GLW": 196.0, "ANT": 83.0}


def series(tk):
    d, p, out = date(2026, 9, 15), PRICE_930[tk], []
    i = 0
    while d <= date(2026, 11, 25):
        if d.weekday() < 5:
            i += 1
            out.append((d.isoformat(), round(p * (1 + 0.004 * ((i % 7) - 3)) * (1 + 0.002 * max(0, i - 12)), 2)))
        d += timedelta(days=1)
    return out


SUBMISSIONS = {"filings": {"recent": {
    "form": ["8-K", "13F-HR", "4", "8-K", "10-Q"],
    "filingDate": ["2026-11-24", "2026-11-14", "2026-11-10", "2026-11-12", "2026-11-19"],
    "reportDate": ["2026-11-23", "2026-09-30", "", "2026-11-12", "2026-10-26"],
    "accessionNumber": ["0001045810-26-000090", "0001045810-26-000085", "0001045810-26-000084", "0001045810-26-000082", "0001045810-26-000088"],
    "primaryDocument": ["nov23pressrelease.htm", "primary_doc.xml", "x.xml", "nvidiaannouncesceotransiti.htm", "nvda-20261026.htm"],
    "primaryDocDescription": ["8-K", "13F-HR", "4", "8-K", "10-Q"],
    "items": ["5.02,7.01", "", "", "5.02", ""]}}}
INDEX = {"directory": {"item": [{"name": "primary_doc.xml"}, {"name": "infotable_q3.xml"}]}}
INFOTABLE = """<?xml version="1.0"?><informationTable xmlns="http://www.sec.gov/edgar/document/thirteenf/informationtable">
""" + "".join(f"""<infoTable><nameOfIssuer>{n}</nameOfIssuer><titleOfClass>COM</titleOfClass><cusip>{c}</cusip><value>{v}</value>
<shrsOrPrnAmt><sshPrnamt>{s}</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt></infoTable>""" for n, c, v, s in [
    ("SPACE EXPLORATION TECHNOLOGIES CORP", "84612A101", 19680000000, 130472925),
    ("INTEL CORP", "458140100", 19370000000, 161082488),
    ("COREWEAVE INC", "21873S108", 4110000000, 31136364),
    ("COHERENT CORP", "19247G107", 2240000000, 7799443),
    ("SYNOPSYS INC", "871607107", 1890000000, 4349827),
    ("NOKIA CORP", "654902204", 740000000, 72860000),
    ("NEBIUS GROUP N V", "N97284108", 280000000, 2372881),
    ("GENERATE BIOMEDICINES INC", "37148K100", 13000000, 1000000),
    ("ARM HOLDINGS PLC", "042068205", 50000000, 300000)]) + "</informationTable>"
RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Nvidia nears deal to acquire Reflection AI - Reuters</title><link>https://example.com/a</link><pubDate>Tue, 24 Nov 2026 10:00:00 GMT</pubDate><source url="https://reuters.com">Reuters</source></item>
<item><title>Intel shares rise as Nvidia trims stake - CNBC</title><link>https://example.com/b</link><pubDate>Mon, 23 Nov 2026 09:00:00 GMT</pubDate><source url="https://cnbc.com">CNBC</source></item>
<item><title>Artificial intelligence spending outlook - FT</title><link>https://example.com/c</link><pubDate>Sun, 22 Nov 2026 09:00:00 GMT</pubDate><source url="https://ft.com">FT</source></item>
<item><title>輝達加碼投資 CoreWeave 與 Nebius 新雲 - 經濟日報</title><link>https://example.com/d</link><pubDate>Sun, 22 Nov 2026 08:00:00 GMT</pubDate><source url="https://money.udn.com">經濟日報</source></item>
</channel></rss>"""


def fake_get(url, **kw):
    import json
    if "submissions" in url:
        body = json.dumps(SUBMISSIONS)
    elif url.endswith("index.json"):
        body = json.dumps(INDEX)
    elif url.endswith(".xml"):
        body = INFOTABLE
    elif "news.google.com" in url:
        body = RSS
    elif "stooq" in url:
        raise RuntimeError("stooq blocked in test")
    else:
        raise RuntimeError("unexpected url " + url)
    return SimpleNamespace(text=body, json=lambda: json.loads(body), status_code=200)


class FakeTicker:
    def __init__(self, tk):
        self.tk = tk

    def history(self, start, auto_adjust=False):
        import pandas as pd
        if self.tk == "ANT":  # 模擬某檔抓不到 → 走備援/快取
            return pd.DataFrame()
        s = series(self.tk)
        return pd.DataFrame({"Close": [p for _, p in s]}, index=pd.to_datetime([d for d, _ in s]))


def main():
    tmp = Path(tempfile.mkdtemp()) / "repo"
    shutil.copytree(REPO, tmp, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    shutil.rmtree(tmp / "docs" / "data", ignore_errors=True)
    sys.path.insert(0, str(tmp / "backend"))
    os.environ["SEC_USER_AGENT"] = "Test Runner test@example.com"
    import common
    common.SEC_UA = os.environ["SEC_USER_AGENT"]
    import fetch_market, fetch_news, fetch_sec, update
    for m in (fetch_market, fetch_news, fetch_sec):
        m.http_get = fake_get
    fetch_sec.SEC_UA = common.SEC_UA
    sys.modules["yfinance"] = SimpleNamespace(Ticker=FakeTicker)

    sys.argv = ["update.py"]
    assert update.main() == 0
    # 第二次執行：驗證「新增」標記與快取沿用
    assert update.main() == 0

    import json
    out = tmp / "docs" / "data"
    meta = json.loads((out / "meta.json").read_text())
    mk = json.loads((out / "market.json").read_text())
    sec = json.loads((out / "sec.json").read_text())
    news = json.loads((out / "news.json").read_text())
    print("meta.steps:", {k: v["status"] for k, v in meta["steps"].items()}, "next:", meta["next_run_at"])
    for h in mk["holdings"]:
        print(f"  {h['ticker']:5} shares={h['shares']} src={h['shares_src']} px={h['price']} val={h['value_b']}")
    print("  warrants:", [(w["ticker"], w["label"], round(w["intrinsic_b"] or 0, 3)) for w in mk["warrants"]])
    print("  sec filings:", len(sec["filings"]), "unmatched:", [u["issuer"] for u in sec["f13"]["unmatched_new_positions"]])
    print("  news:", [(i["title"][:30], i["nodes"]) for i in news["items"]])

    by = {h["ticker"]: h for h in mk["holdings"]}
    assert by["CRWV"]["shares"] == 31136364 and by["CRWV"]["shares_src"].startswith("13F")
    assert by["ANT"]["stale"] and by["ANT"]["value_b"] is None
    assert meta["steps"]["ai"]["status"] == "skipped"
    assert all(n["nodes"] == [] for n in news["items"] if "Artificial" in n["title"])   # Intel 不可誤中 intelligence
    assert "intel" in next(n for n in news["items"] if n["title"].startswith("Intel"))["nodes"]
    assert set(next(n for n in news["items"] if "輝達" in n["title"])["nodes"]) >= {"coreweave", "nebius"}
    assert [u["issuer"] for u in sec["f13"]["unmatched_new_positions"]] == ["ARM HOLDINGS PLC"]
    print("ALL TESTS PASSED →", out)


if __name__ == "__main__":
    main()
