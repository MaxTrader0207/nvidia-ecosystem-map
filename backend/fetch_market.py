"""上市持股與認股權證的每週估值。

價格來源：yfinance（優先）→ Stooq CSV（備援）→ 上週快取（標記 stale）。
股數來源優先序：最新 13F 解析 → holdings.json 精確股數 → 13F 市值 ÷ 申報日收盤推算 → 約略股數。
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta

from common import TPE, http_get


def _hist_yf(ticker: str, start: date) -> list[tuple[str, float]]:
    import yfinance as yf  # 選用套件
    df = yf.Ticker(ticker).history(start=start.isoformat(), auto_adjust=False)
    if df is None or df.empty:
        raise RuntimeError("yfinance 無資料")
    return [(idx.strftime("%Y-%m-%d"), float(v)) for idx, v in df["Close"].dropna().items()]


def _hist_stooq(sym: str, start: date) -> list[tuple[str, float]]:
    url = f"https://stooq.com/q/d/l/?s={sym}&d1={start:%Y%m%d}&d2={datetime.now(TPE):%Y%m%d}&i=d"
    txt = http_get(url).text
    rows = [(r["Date"], float(r["Close"])) for r in csv.DictReader(io.StringIO(txt)) if r.get("Close") not in (None, "", "N/D")]
    if not rows:
        raise RuntimeError("Stooq 無資料")
    return rows


def _history(ticker: str, stooq: str | None, start: date, errors: list) -> tuple[list, str]:
    for name, fn, arg in (("yfinance", _hist_yf, ticker), ("stooq", _hist_stooq, stooq)):
        if not arg:
            continue
        try:
            return fn(arg, start), name
        except Exception as e:  # noqa: BLE001
            errors.append(f"{ticker}/{name}: {e}")
    return [], ""


def _close_on_or_before(hist, d: str):
    c = [p for (dt, p) in hist if dt <= d]
    return c[-1] if c else None


def run(holdings_cfg: dict, sec: dict | None, prev: dict | None) -> tuple[dict, str]:
    as_of = holdings_cfg["as_of_13f"]
    start = min(date.fromisoformat(as_of) - timedelta(days=10), datetime.now(TPE).date() - timedelta(days=21))
    prev_h = {h["ticker"]: h for h in (prev or {}).get("holdings", [])}
    f13 = (sec or {}).get("f13") or {}
    f13_use = f13.get("report_date", "") >= as_of
    f13_by_node = {m["node"]: m for m in f13.get("matched", [])} if f13_use else {}

    cache, errors = {}, []

    def prices(ticker, stooq):
        if ticker not in cache:
            cache[ticker] = _history(ticker, stooq, start, errors)
        return cache[ticker]

    out_h = []
    for h in holdings_cfg["holdings"]:
        hist, srcname = prices(h["ticker"], h.get("stooq"))
        row = {"node": h["node"], "ticker": h["ticker"], "note": h.get("note", "")}
        pv = prev_h.get(h["ticker"], {})
        if hist:
            row.update(price=hist[-1][1], price_date=hist[-1][0], price_src=srcname, stale=False)
            wk = _close_on_or_before(hist, (date.fromisoformat(hist[-1][0]) - timedelta(days=7)).isoformat())
            row["chg_w_pct"] = (row["price"] / wk - 1) * 100 if wk else None
        elif pv.get("price"):
            row.update(price=pv["price"], price_date=pv.get("price_date"), price_src="上週快取", stale=True, chg_w_pct=None)
        else:
            row.update(price=None, price_date=None, price_src="", stale=True, chg_w_pct=None)

        # 股數
        f13_value_b = h.get("f13_value_b")
        if h["node"] in f13_by_node:
            m = f13_by_node[h["node"]]
            row["shares"], row["shares_src"] = m["shares"], f"13F（{f13['report_date']}）"
            f13_value_b = m["value_usd"] / 1e9
        elif h.get("shares"):
            row["shares"], row["shares_src"] = h["shares"], "設定檔"
        elif pv.get("shares") and pv.get("shares_src", "").startswith("推算"):
            row["shares"], row["shares_src"] = pv["shares"], pv["shares_src"]
        else:
            base = _close_on_or_before(hist, as_of) if hist else None
            if base and f13_value_b:
                row["shares"], row["shares_src"] = round(f13_value_b * 1e9 / base), f"推算（13F 市值 ÷ {as_of} 收盤 ${base:,.2f}）"
            elif h.get("approx_shares"):
                row["shares"], row["shares_src"] = h["approx_shares"], "約略股數（新聞報導）"
            else:
                row["shares"], row["shares_src"] = None, "未知"
        row["f13_value_b"] = f13_value_b
        row["value_b"] = row["shares"] * row["price"] / 1e9 if row.get("shares") and row.get("price") else None
        row["chg_vs_13f_pct"] = (row["value_b"] / f13_value_b - 1) * 100 if row["value_b"] and f13_value_b else None
        out_h.append(row)

    out_w = []
    for w in holdings_cfg.get("warrants", []):
        hist, srcname = prices(w["ticker"], w.get("stooq"))
        p = hist[-1][1] if hist else next((x["price"] for x in (prev or {}).get("warrants", []) if x["ticker"] == w["ticker"] and x.get("price")), None)
        out_w.append({**w, "price": p, "price_date": hist[-1][0] if hist else None, "stale": not hist,
                      "intrinsic_b": max(0.0, p - w["strike"]) * w["shares"] / 1e9 if p else None,
                      "exercise_cost_b": w["strike"] * w["shares"] / 1e9,
                      "in_the_money": (p or 0) > w["strike"]})

    tot = {
        "value_b": sum(r["value_b"] or 0 for r in out_h),
        "value_13f_names_b": sum(r["value_b"] or 0 for r in out_h if r["f13_value_b"]),
        "f13_value_b": sum(r["f13_value_b"] or 0 for r in out_h),
        "warrant_intrinsic_b": sum(w["intrinsic_b"] or 0 for w in out_w),
    }
    dates = [r["price_date"] for r in out_h + out_w if r.get("price_date")]
    out = {"as_of_13f": as_of, "price_date": max(dates) if dates else None, "holdings": out_h,
           "warrants": out_w, "totals": tot, "errors": errors[:30]}
    ok = sum(1 for r in out_h if not r["stale"])
    msg = f"{ok}/{len(out_h)} 檔取得最新價格；持股估值 ${tot['value_b']*10:,.0f} 億"
    if ok == 0:
        raise RuntimeError("所有價格來源皆失敗：" + "; ".join(errors[:5]))
    return out, msg
