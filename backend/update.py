"""每週更新主程式（GitHub Actions 執行）。

流程：
  1. 讀取人工主資料 data/ecosystem.json、data/holdings.json → 複製到 docs/data/
  2. SEC 申報＋最新 13F 解析   → docs/data/sec.json
  3. 持股／權證估值           → docs/data/market.json
  4. 新聞追蹤                 → docs/data/news.json
  5. （選用）AI 審核建議       → docs/data/ai_review.json
  6. 寫入 docs/data/meta.json（更新時間、下次排程、各步驟狀態）

任一步驟失敗只會保留上週資料並在 meta 標示，不會中斷整體更新。
用法：python backend/update.py [--only market,news] ；本機測試可設 OFFLINE=1
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(__file__))

import ai_review  # noqa: E402
import fetch_market  # noqa: E402
import fetch_news  # noqa: E402
import fetch_sec  # noqa: E402
from common import (DATA_DIR, OFFLINE, OUT_DIR, SCHEDULE_TEXT, iso, load_json,  # noqa: E402
                    next_run, now_tpe, save_json)

STEPS = ["sec", "market", "news", "ai"]
LABELS = {"sec": "SEC 申報／13F", "market": "持股與權證估值", "news": "新聞追蹤", "ai": "AI 審核建議（選用）"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="只執行指定步驟，逗號分隔：" + ",".join(STEPS))
    args = ap.parse_args()
    only = {s for s in args.only.split(",") if s} or set(STEPS)

    start = now_tpe()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    eco = load_json(DATA_DIR / "ecosystem.json")
    hold = load_json(DATA_DIR / "holdings.json")
    if not eco or not hold:
        print("找不到 data/ecosystem.json 或 data/holdings.json", file=sys.stderr)
        return 1
    shutil.copyfile(DATA_DIR / "ecosystem.json", OUT_DIR / "ecosystem.json")
    shutil.copyfile(DATA_DIR / "holdings.json", OUT_DIR / "holdings.json")

    prev_meta = load_json(OUT_DIR / "meta.json", {}) or {}
    steps = dict(prev_meta.get("steps", {}))
    results = {k: load_json(OUT_DIR / f"{k if k != 'ai' else 'ai_review'}.json") for k in STEPS}

    runners = {
        "sec": lambda: fetch_sec.run(hold, results["sec"]),
        "market": lambda: fetch_market.run(hold, results["sec"], results["market"]),
        "news": lambda: fetch_news.run(eco, hold, results["news"]),
        "ai": lambda: ai_review.run(eco, results["news"]),
    }
    for k in STEPS:
        if k not in only:
            continue
        t0 = time.time()
        if OFFLINE:
            steps[k] = {"label": LABELS[k], "status": "skipped", "message": "OFFLINE 模式未連網", "at": iso(now_tpe())}
            continue
        try:
            data, msg = runners[k]()
            data["updated_at"] = iso(now_tpe())
            results[k] = data
            save_json(OUT_DIR / f"{k if k != 'ai' else 'ai_review'}.json", data)
            steps[k] = {"label": LABELS[k], "status": "ok", "message": msg, "at": iso(now_tpe()),
                        "secs": round(time.time() - t0, 1)}
        except Exception as e:  # noqa: BLE001
            skipped = isinstance(e, RuntimeError) and "略過" in str(e)
            steps[k] = {"label": LABELS[k], "status": "skipped" if skipped else "error", "message": str(e)[:300],
                        "at": iso(now_tpe()), "kept_previous": results[k] is not None,
                        "last_ok_at": (prev_meta.get("steps", {}).get(k) or {}).get("at") if results[k] else None}
            if not skipped:
                traceback.print_exc()
        print(f"[{k}] {steps[k]['status']}: {steps[k]['message']}")

    end = now_tpe()
    run_url = ""
    if os.environ.get("GITHUB_RUN_ID"):
        run_url = f"{os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ['GITHUB_RUN_ID']}"
    meta = {
        "updated_at": iso(end),
        "started_at": iso(start),
        "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
        "schedule": SCHEDULE_TEXT,
        "next_run_at": iso(next_run(end)),
        "curated_at": eco["meta"].get("curated_at"),
        "steps": steps,
        "run_url": run_url,
    }
    save_json(OUT_DIR / "meta.json", meta)
    print(f"完成：{meta['updated_at']}；下次排程 {meta['next_run_at']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
