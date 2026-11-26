"""共用工具：路徑、時間（台北）、JSON 讀寫、HTTP。"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"              # 人工維護主資料
OUT_DIR = ROOT / "docs" / "data"      # 後端產出、前端讀取

TPE = timezone(timedelta(hours=8), name="Asia/Taipei")

# 排程設定：需與 .github/workflows/weekly-update.yml 的 cron 一致
# cron "7 0 * * 1"（UTC）＝ 每週一 08:07（台北）
SCHEDULE_WEEKDAY = 0      # 0 = 週一
SCHEDULE_HOUR = 8
SCHEDULE_MINUTE = 7
SCHEDULE_TEXT = "每週一 08:07（台北時間）"

# SEC 要求 User-Agent 含聯絡資訊；請在 GitHub repo Variables 設定 SEC_USER_AGENT（例："你的名稱 your@email"）
SEC_UA = os.environ.get("SEC_USER_AGENT", "").strip()
OFFLINE = os.environ.get("OFFLINE") == "1"   # 本機測試：不連網，只重建輸出


def now_tpe() -> datetime:
    return datetime.now(TPE)


def iso(dt: datetime) -> str:
    return dt.astimezone(TPE).isoformat(timespec="seconds")


def next_run(after: datetime) -> datetime:
    a = after.astimezone(TPE)
    days = (SCHEDULE_WEEKDAY - a.weekday()) % 7
    cand = (a + timedelta(days=days)).replace(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0)
    if cand <= a:
        cand += timedelta(days=7)
    return cand


def load_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def http_get(url: str, *, headers: dict | None = None, timeout: int = 30, **kw) -> requests.Response:
    h = {"User-Agent": "Mozilla/5.0 (compatible; NVIDIA-Ecosystem-Map/1.0)"}
    if headers:
        h.update(headers)
    r = requests.get(url, headers=h, timeout=timeout, **kw)
    r.raise_for_status()
    return r
