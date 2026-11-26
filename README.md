# NVIDIA 生態資本投資循環架構｜投資族譜 Dashboard

前後端分離版：**前端** GitHub Pages（`docs/`）＋**後端** GitHub Actions 每週排程（`backend/`）。
畫面頂部顯示「最後更新時間／下次排程／各步驟狀態」，超過 8 天未更新會轉紅提醒。

```
nvidia-ecosystem-map/
├── data/                         ← 人工維護主資料（唯一真實來源）
│   ├── ecosystem.json            節點、來源、循環、時間軸、KPI、治理動態、校驗紀錄
│   └── holdings.json             追蹤的上市持股、權證、新聞關鍵字對照
├── backend/                      ← Python 更新程式（GitHub Actions 執行）
│   ├── update.py                 主程式：依序執行各步驟並寫 meta.json
│   ├── fetch_sec.py              SEC EDGAR 申報清單＋最新 13F 資訊表解析
│   ├── fetch_market.py           持股估值（yfinance → Stooq → 上週快取）、權證內含價值
│   ├── fetch_news.py             Google News RSS（英／繁中）＋節點標記
│   ├── ai_review.py              （選用）Claude API＋網路搜尋產生「待審核」建議
│   └── common.py                 路徑、台北時間、排程設定
├── docs/                         ← GitHub Pages 前端
│   ├── index.html
│   ├── assets/{style.css, app.js, export.js}
│   └── data/                     後端產出（前端讀取），勿手動編輯
├── tests/test_offline.py         離線測試（假資料，不連網）
└── .github/workflows/weekly-update.yml
```

## 每週自動更新的內容

| 步驟 | 內容 | 失敗時 |
|---|---|---|
| SEC 申報／13F | 近 120 天 8-K、10-Q、13F、13D/G…，本週新申報標 NEW；新 13F 出爐時自動解析股數，並列出**設定檔未追蹤的新持股** | 沿用上週資料 |
| 持股與權證估值 | 8 檔上市持股最新市值、週漲跌、相較 13F 變化；IREN／Corning／Nebius 權證內含價值 | 沿用上週價格並標「未更新」 |
| 新聞追蹤 | 近 7 天 NVIDIA×投資／入股／收購／權證／擔保新聞，自動標記涉及節點（族譜卡片顯示 📰 次數） | 沿用上週資料 |
| AI 審核建議（選用） | 設定 `ANTHROPIC_API_KEY` 才執行；產生建議清單，**不會自動改寫主資料** | 略過 |

人工主資料（金額、狀態、循環結構）**不會**被排程改寫——新聞與 AI 只提供線索，確認後請手動修改 `data/ecosystem.json`。

## 部署步驟

1. 建立 GitHub repo（例：`MaxTrader0207/nvidia-ecosystem-map`），推上整個資料夾。
2. **Settings → Pages**：Source 選 *Deploy from a branch*，Branch 選 `main`、資料夾 `/docs`。
3. **Settings → Actions → General → Workflow permissions**：選 *Read and write permissions*（排程要把資料 commit 回 repo）。
4. **Settings → Secrets and variables → Actions**：
   - Variables → `SEC_USER_AGENT`（**必填**，SEC 要求含聯絡資訊，例：`Your Name your@email.com`）
   - Secrets → `ANTHROPIC_API_KEY`（選填，啟用 AI 審核建議）
   - Variables → `CLAUDE_MODEL`（選填，預設 `claude-sonnet-5-5`）
5. **Actions → Weekly Update → Run workflow** 手動跑第一次，完成後網頁就會顯示更新時間。

## 排程

- `cron: "7 0 * * 1"` ＝ **每週一 08:07（台北）**，抓美股週五收盤後的週快照。
- 修改 `data/` 或 `backend/` 並 push 到 main 時也會自動重跑。
- 要改時間：同時修改 workflow 的 cron 與 `backend/common.py` 的 `SCHEDULE_*`（畫面上的「下次排程」據此計算）。
- 注意：GitHub 對 60 天無 commit 的 repo 會停用排程；本流程每週都會 commit 資料，通常不會觸發。

## 日常維護

- **新增／修改投資節點**：編輯 `data/ecosystem.json` 的 `nodes`，來源加到 `sources` 再以鍵名引用。
- **新增追蹤持股**：在 `data/holdings.json` 的 `holdings` 加入 ticker、`issuer_match`（13F 發行人名稱關鍵字）；股數未知可填 `null`，後端會從 13F 推算。
- **新聞關鍵字**：`holdings.json` 的 `news_aliases`。

## 本機執行

```bash
pip install -r backend/requirements.txt
SEC_USER_AGENT="Your Name your@email.com" python backend/update.py        # 全部步驟
python backend/update.py --only market,news                             # 只跑部分
python tests/test_offline.py                                            # 離線測試（在暫存複本執行）
python -m http.server -d docs 8000                                      # 開 http://localhost:8000
```
（直接雙擊 `docs/index.html` 會因瀏覽器 file:// 限制讀不到 JSON，需用上面的本機伺服器或 GitHub Pages。）

本 Dashboard 為資訊整理，非投資建議。


---

## 投資生態圈（20 家＋跨實體總網路圖）

與上面的 NVIDIA 即時版互相獨立，放在子資料夾，不會動到原本的 `data/`、`backend/`、`docs/index.html`。

- 網址：`https://maxtrader0207.github.io/nvidia-ecosystem-map/ecosystem/`（自動轉到總網路圖，各家 Dashboard 從圖上點進去）
- `ecomap/data/<slug>/data.json`：各家主資料（人工維護，唯一真實來源）
- `ecomap/`：建置程式（`build.py`、`build_network.py`、兩個 template）、`update_prices.py`、`check_updates.py`、`test_all.py`
- `docs/ecosystem/`：產出的頁面（`ecomap/docs` 是指向這裡的連結）
- `.github/workflows/ecomap-weekly.yml`：每週一 08:37（台北）更新上市持股現值 → 檢查新動態（寫入 `pending.json`，不改主資料）→ 重建 → 測試全部頁面 → 通過才提交

詳細說明見 `ecomap/README.md`。本頁為資訊整理，非投資建議。
