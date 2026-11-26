"""SEC EDGAR：NVIDIA 最新申報清單＋最新 13F 資訊表解析。

輸出 docs/data/sec.json：
  filings : 近 120 天重要申報（8-K、10-Q、10-K、13F-HR、SC 13D/G…），標記本週新出現者
  f13     : 最新一份 13F-HR 的持股明細（發行人、CUSIP、股數、市值），並比對 holdings.json
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from common import SEC_UA, TPE, http_get

FORMS = {"8-K", "8-K/A", "10-Q", "10-K", "13F-HR", "13F-HR/A", "SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A",
         "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A", "DEF 14A", "S-3ASR"}
LOOKBACK_DAYS = 120


def _hdr():
    if not SEC_UA:
        raise RuntimeError("未設定 SEC_USER_AGENT（SEC 要求含聯絡資訊的 User-Agent），已略過")
    return {"User-Agent": SEC_UA, "Accept-Encoding": "gzip, deflate"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_infotable(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    rows = []
    for it in root.iter():
        if _local(it.tag) != "infoTable":
            continue
        d = {}
        for ch in it.iter():
            name = _local(ch.tag)
            if name in ("nameOfIssuer", "titleOfClass", "cusip", "value", "sshPrnamt", "sshPrnamtType", "putCall"):
                d[name] = (ch.text or "").strip()
        rows.append({
            "issuer": d.get("nameOfIssuer", ""), "class": d.get("titleOfClass", ""), "cusip": d.get("cusip", ""),
            "value_usd": float(d.get("value") or 0), "shares": int(float(d.get("sshPrnamt") or 0)),
            "type": d.get("sshPrnamtType", ""), "putCall": d.get("putCall", ""),
        })
    return rows


def _fetch_13f(cik_int: int, acc: str, report_date: str, filing_date: str, holdings: list[dict]) -> dict:
    base = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc.replace('-', '')}"
    idx = http_get(base + "/index.json", headers=_hdr()).json()
    names = [i["name"] for i in idx.get("directory", {}).get("item", [])]
    xmls = [n for n in names if n.lower().endswith(".xml") and "primary_doc" not in n.lower()]
    if not xmls:
        raise RuntimeError("13F 找不到資訊表 XML")
    rows = _parse_infotable(http_get(f"{base}/{xmls[0]}", headers=_hdr()).text)

    # 同一發行人可能多列（不同類別），依名稱彙總
    matched, unmatched = {}, []
    for r in rows:
        up = r["issuer"].upper()
        h = next((h for h in holdings if any(k in up for k in h.get("issuer_match", []))), None)
        if h:
            m = matched.setdefault(h["node"], {"node": h["node"], "ticker": h["ticker"], "issuer": r["issuer"],
                                               "shares": 0, "value_usd": 0.0, "cusips": []})
            m["shares"] += r["shares"]
            m["value_usd"] += r["value_usd"]
            m["cusips"].append(r["cusip"])
        else:
            unmatched.append(r)
    return {
        "accession": acc, "report_date": report_date, "filing_date": filing_date, "url": base + "/",
        "total_value_usd": sum(r["value_usd"] for r in rows), "positions": len(rows),
        "matched": list(matched.values()), "unmatched_new_positions": unmatched,
    }


def run(holdings_cfg: dict, prev: dict | None) -> dict:
    cik = holdings_cfg.get("nvidia_cik", "0001045810")
    cik_int = int(cik)
    sub = http_get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=_hdr()).json()
    rec = sub["filings"]["recent"]
    prev_acc = {f["accession"] for f in (prev or {}).get("filings", [])}
    first_run = not prev_acc
    cutoff = (datetime.now(TPE) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    filings, latest_13f = [], None
    for i, form in enumerate(rec["form"]):
        fd = rec["filingDate"][i]
        acc = rec["accessionNumber"][i]
        if form in ("13F-HR", "13F-HR/A") and latest_13f is None:
            latest_13f = (acc, rec.get("reportDate", [""] * len(rec["form"]))[i], fd)
        if form not in FORMS or fd < cutoff:
            continue
        doc = rec["primaryDocument"][i]
        filings.append({
            "form": form, "filing_date": fd, "report_date": rec.get("reportDate", [""] * len(rec["form"]))[i],
            "accession": acc, "desc": rec.get("primaryDocDescription", [""] * len(rec["form"]))[i] or form,
            "items": rec.get("items", [""] * len(rec["form"]))[i],
            "url": f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc.replace('-', '')}/{doc}",
            "is_new": (not first_run) and acc not in prev_acc,
        })

    out = {"cik": cik, "filings": filings, "f13": (prev or {}).get("f13")}
    msg = f"{len(filings)} 筆申報（新增 {sum(f['is_new'] for f in filings)}）"
    if latest_13f:
        acc, rdate, fdate = latest_13f
        if not out["f13"] or out["f13"].get("accession") != acc:
            out["f13"] = _fetch_13f(cik_int, acc, rdate, fdate, holdings_cfg["holdings"] + holdings_cfg.get("track_only", []))
            out["f13"]["is_new"] = not first_run
            msg += f"；已解析新 13F（{rdate}）"
        else:
            out["f13"]["is_new"] = False
    return out, msg
