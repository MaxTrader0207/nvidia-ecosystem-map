# 投資生態圈 Dashboard 自動更新（第 14 項）

每週一自動搜尋各實體在資料截止日之後的新交易與公告，寫進 `data/<slug>/pending.json`，重建 Dashboard。新動態會出現在「投資委員會摘要」的「🔔 待人工確認」，**不會自動改正式資料**。

## 設定步驟
1. 建一個 repo，放入：`template.html`、`build.py`、`network_template.html`、`build_network.py`（從 skill 取出）、`check_updates.py`、`.github/workflows/ecomap-weekly.yml`。
2. 每家實體一個資料夾：`data/intel/data.json`、`data/meta/data.json`……；輸出放 `docs/`，GitHub Pages 指向 `docs/`。
3. 到 repo 的 Settings → Secrets → Actions 新增 `ANTHROPIC_API_KEY`。
4. 到 Actions 分頁手動執行一次「投資生態圈每週檢查」確認可用。

## 確認流程
- 看到待確認項目後，請 Claude 用 skill 查證並更新該實體的 data.json（同時把 `meta.asOf` 改成新日期），再刪除或清空 `pending.json`。
- 重建時 build.py 會自動和舊版 HTML 比對，頁面上的「🔄 與上一版相比」就是這次變更。

## 注意
- 每家每週約 1 次 API 呼叫（含最多 6 次網路搜尋），費用依模型與搜尋次數計算。
- 搜尋結果仍可能有誤或漏抓，pending 只是線索，不是已查證資料。

## 總網路圖與一致性檢查
- 每週流程最後會重建 `docs/Ecosystem_Network_Map.html`，並列出「同一筆關係在不同實體檔金額對不上」的項目。
- 結果分三種：一致、已說明（節點有 `xnote` 說明差異原因）、待確認（需要查證後修正或補 `xnote`）。

## 上市持股現值自動更新
- 節點填了 `shares`（股數）與 `pxTk`（Yahoo 報價代號）後，`update_prices.py` 每週會抓最新收盤價重算 `val`，報酬倍數跟著更新；非美元報價會自動換匯，ADR 可用 `pxMult` 設換股比例。
- 只改現值相關欄位，不會動 `verified`（人工查證日）。取不到報價時維持原值並在執行摘要列出。
- 也可以離線執行：`python update_prices.py . --prices prices.json`。
- `costUnknown: true` 的節點（金額欄是申報市值、成本未揭露）只顯示現值，不算倍數。
- 一致性檢查新增「單邊」：一方有記金額關係、另一方完全沒有對應節點。

## 放上 GitHub Pages（不用再下載 zip）
1. 把整個資料夾推到一個 repo（`docs/`、`data/`、四個建置檔、`.github/workflows/`）。
2. repo 的 Settings → Pages → Source 選「Deploy from a branch」，Branch 選 `main`、資料夾選 `/docs`。
3. 網址是 `https://<帳號>.github.io/<repo>/`；`docs/index.html` 會自動轉到總網路圖，各家 Dashboard 從總網路圖點進去。
4. 之後每週一的流程會自動更新現值、檢查新動態、重建並提交 `docs/`，頁面跟著更新。
- repo 若設為公開，任何人都能看到頁面；要私有需 GitHub 付費方案的私有 Pages。

## 每次建置後的自動測試
- `test_all.py docs` 會開啟每一份 Dashboard 與總網路圖、切換所有分頁並點第一張卡片；有瀏覽器錯誤就讓流程失敗、不提交。

## 部分減持與已回收
- `soldPct`：已減持的百分比（例如 25）。報酬倍數改用剩餘部位的成本計算。
- `realized`：已回收金額（US$ 十億）。有填時倍數＝（現值＋已回收）÷ 成本。

## 跨實體資金閉環
- 總網路圖會把所有有金額的關係接成有向圖，自動找出 2–4 個環節的閉環，並標出金額最小的一段；每條閉環最多允許一段金額未揭露。
