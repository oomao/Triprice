# Triprice

台股估值小工具：以**殖利率法**為主、**本益比 (PE) 法**為輔，計算便宜 / 合理 / 昂貴三檔目標價，並比較美股 ADR 與台股的隱含價差。

純前端 PWA，部署在 GitHub Pages，資料每日由 GitHub Actions 自動抓取並更新。

---

## 立即使用

### 網址
**https://oomao.github.io/Triprice/**

桌機 / 手機 / 平板都能用，沒裝任何東西也能開。

### 安裝到手機（PWA）

像 native app 一樣，可加到主畫面、離線可看：

- **iOS Safari**：分享按鈕 → 加入主畫面
- **Android Chrome**：右上選單 → 安裝應用程式

---

## 功能

| 功能 | 說明 |
|------|------|
| 三價估值 | 便宜 / 合理 / 昂貴三檔目標價，殖利率法 + PE 法雙計算（5/95 百分位） |
| **估值帶狀圖** | **個股頁顯示 3 年股價走勢 + 三檔估值參考線，一眼看出目前位置（0% = 便宜、100% = 昂貴）** |
| 標籤分級 | 目前股價自動標示「便宜 / 合理偏便宜 / 合理偏貴 / 昂貴」 |
| ADR 比較 | TSM、HNHPF、UMC、ASX、CHT 五檔 ADR 的隱含台股價 + 溢價率 |
| **明日 TW 開盤 / 高 / 低預測** | **`/adr` 頁：Ridge + 80% Conformal 區間預測明日 TW 開盤、盤中最高、盤中最低三條，附過去 30 日 walk-forward 驗證（每天重訓 + 比對實際）。訊號乾淨化（FX 分離、SOX β residual、溢價 z-score）+ 事件日剔除（除息、漲跌停、長假後、HNHPF stale）。頁首「預測快覽」一秒看到答案，頁面右上有新鮮度 badge。** |
| **個股頁預測整合** | **2330 / 2317 / 3711 個股頁顯示一張「明日開盤預測」strip（同 Ridge 模型）— 把短期訊號跟長期估值放在同一頁。** |
| **夜盤訊號速覽** | **`/adr` 頁：3 檔重點 ADR 平均溢價 + 費城半導體指數（^SOX）的 5 段標籤（強烈偏多 → 強烈偏空 / 強勢 → 弱勢）+ 30 日 sparkline（含 min/max 標記）。** |
| **ETF 全覽 + 評分** | **`/etf` 頁：列出全部主流台股 ETF（過濾掉債券/槓桿）。4 維相對評分（殖利率、1Y 報酬、規模、穩定度）。可依分類過濾、欄位排序** |
| **大盤儀表板** | **`/market` 頁：加權指數 + 櫃買指數現況（含 1Y 走勢）+ 三大法人近 30 日買賣超。** |
| **K 線 + 均線** | **個股頁：日 K 線（紅漲綠跌）+ MA5/MA20/MA60 + 成交量副圖。可切換 1M / 3M / 6M / 1Y 區間** |
| **三大法人籌碼** | **個股頁：近 30 日外資 / 投信 / 自營商買賣超堆疊柱狀圖 + 5 日累計卡片** |
| **自選組合估值** | **自選頁：彙總所有自選股的「位置百分位」，平均便宜度 + 最便宜/最貴標示 + 每檔位置條** |
| **個股摘要 (LLM)** | **個股頁：可選功能。設定 → 填 Claude / OpenAI API key 後，按「生成摘要」用瀏覽器端 LLM 為該檔生成 2~3 句客觀摘要（localStorage cache，fingerprint 比對避免重複付費）** |
| **介面** | 純黑底頂欄 + 焦糖色高亮 + 表格使用 tabular-nums，數字對齊像專業看盤工具，不是樣板儀表板。Skeleton shimmer 載入動畫 |
| 財報明細 | 近 4 季 EPS、YoY 成長率、近 5 年股利歷史 |
| 自選股 | 自訂任意股票代號，存於 localStorage |
| PWA | 可安裝到主畫面、離線可用、自動更新 |
| RWD | 手機 / 平板 / 桌機自適應（寬表自動橫滾、nav 在窄螢幕橫滑） |
| 自動更新 | 每天台股 + 美股收盤後抓取最新資料 |

---

## 估值方法

### 殖利率法（主）

適合穩定配息的股票（金融股、ETF、傳產龍頭）。

```
便宜價 = 最近一年現金股利 ÷ 近 3 年第 95 百分位殖利率
合理價 = 最近一年現金股利 ÷ 近 3 年中位數殖利率
昂貴價 = 最近一年現金股利 ÷ 近 3 年第 5 百分位殖利率
```

殖利率取**近 3 年每日**「年股利 / 收盤價」的第 5 / 50 / 95 百分位（過濾極端尾部 5%，比直接拿最高/最低值更穩定）。

### 本益比 (PE) 法（附）

適合所有股票，**特別是成長股（殖利率法會嚴重低估）**。

```
便宜價 = 近 4 季 EPS 合計 × 近 3 年第 5 百分位 PE
合理價 = 近 4 季 EPS 合計 × 近 3 年中位數 PE
昂貴價 = 近 4 季 EPS 合計 × 近 3 年第 95 百分位 PE
```

PE 區間同樣取自每日歷史 PE 的 5 / 50 / 95 百分位。

⚠️ 殖利率法對成長股（殖利率長期低於 2%）會嚴重低估其合理價。個股頁會自動偵測並提示「請以 PE 法為主」。

### ADR 隱含價 + 夜盤訊號

```
ADR 隱含台股價 = ADR 收盤 × USD/TWD ÷ 每 ADR 對應股數
ADR 溢價率   = (ADR 隱含台股價 − 台股收盤) / 台股收盤
```

由於 ADR 收盤晚於台股約 14~15 小時（美東 16:00 = 台北隔日 04:00），這個溢價率反映「ADR 比較新的收盤」vs「台股比較舊的收盤」的差距，**可作為台股隔日開盤方向的參考訊號**。

| ADR | 台股 | 1 ADR : 台股股數 | 進入 /adr 預測 |
|-----|------|------|---|
| TSM | 2330 台積電 | 1 : 5 | ✓ |
| HNHPF | 2317 鴻海（OTC 非贊助 ADR） | 1 : 2 | ✓ |
| ASX | 3711 日月光投控 | 1 : 2 | ✓ |
| UMC | 2303 聯電 | 1 : 5 | （僅顯示在個股頁） |
| CHT | 2412 中華電 | 1 : 10 | （僅顯示在個股頁） |

### 明日 TW 開盤 / 高 / 低預測（Ridge + Conformal）

`/adr` 儀表板的核心：把 ADR 報酬扣掉匯率與大盤影響，再加上偏離常態的溢價，用回歸算明天 TW 開盤 / 盤中最高 / 盤中最低三條 + 80% 信心區間。

**訊號乾淨化**：
- **個股 α**（JSON: `adr_alpha_pct`）= ADR USD 漲跌 − USD/TWD 漲跌 − rolling 90d β · SOX 漲跌（剝 FX 與 sector beta，留下純個股動能）
- **SOX** 整體漲跌 %（保留 sector 訊號）
- **溢價 z-score** = (今日溢價 − 60d rolling median) / MAD（去掉結構性偏移）

**事件日剔除**（從訓練集中扣除）：
- 除息日 T 與 T+1（FinMind `TaiwanStockDividend`）
- TW 漲跌停（|change| > 9.5%）
- 長假後第一日（calendar gap > 3）
- ADR 成交量 = 0（HNHPF 鴻海 OTC 常見）

**建模 + 驗證**：
- RidgeCV 三訊號合成 → 每股票每目標獨立校準權重
- 80% Conformal 區間（finite-sample valid coverage 保證）
- Walk-forward：過去 30 個交易日，每日重訓、預測、跟實際比對
- 一致性 enforce：高 ≥ 開 ≥ 低（少數情況自動 clip）

**頁面元素**：頁首「預測快覽」三檔開盤 +80% 區間 → 點擊跳到下方完整卡 → 內含訊號分解、預測表、過去 30 天 walk-forward 統計（可展開逐日對照）。
H1 旁有新鮮度 badge（綠 ≤ 6h / 黃 6–30h / 紅 > 30h cron 失敗警示）。
2330 / 2317 / 3711 個股頁也會顯示同模型的開盤預測 strip。

---

## 預載 26 檔台股

| 類別 | 代號 |
|------|------|
| ETF | 0050 0056 00878 00929 |
| 半導體 | 2330 2454 2303 2308 3711 |
| 金融 | 2880 2881 2882 2884 2885 2886 2887 2890 2891 2892 |
| 電子其他 | 2317 2382 2412 2409 |
| 民生消費 | 1216 2912 |
| 傳產 | 2002 |

要看其他股票？開網站「自選」頁手動輸入代號（4-6 碼）即可，或直接在程式碼中加入（見下方「自訂」段）。

---

## 開發

### 環境需求

- Node.js 20+
- Python 3.12+
- npm

### 第一次設定

```bash
# 前端依賴
npm install

# 抓資料的 Python 依賴
pip install -r scripts/requirements.txt
```

### 本地開發

```bash
npm run dev          # 開發伺服器 → http://localhost:5173
npm run build        # 建置生產版本到 dist/
npm run preview      # 預覽建置結果
```

### 手動抓資料

```bash
# 抓全部 26 檔台股
python scripts/fetch_tw.py

# 只抓特定股票
python scripts/fetch_tw.py 2330 0050

# 抓美股 ADR + 匯率 + SOX（需先跑過 fetch_tw.py；事件日剔除需 FINMIND_TOKEN）
python scripts/fetch_us.py

# 重算明日預測 + 30 日 walk-forward 驗證（Ridge + Conformal；需先跑過 fetch_us.py）
python scripts/predict_open_high_low.py

# 抓 ETF 全覽（含評分）
python scripts/fetch_etf.py            # 全部主流 ETF（過濾債券/槓桿）
python scripts/fetch_etf.py --limit 40 # 只抓前 40 檔（本地測試用）

# 抓大盤（TAIEX + OTC + 三大法人）
python scripts/fetch_market.py
```

抓完的 JSON 會寫到 `data/tw/{code}.json`、`data/fx.json`、`data/adr_signal.json`、`data/adr_prediction.json`、`data/last_updated.json`。

> 個股摘要功能改成瀏覽器端：在 `/設定` 填入 Claude / OpenAI API key，個股頁按「生成摘要」。不再有 Python script。

---

## 專案架構

### 技術棧

| 層 | 技術 |
|----|------|
| 框架 | Vue 3.5 + Vue Router 5 + Pinia 3 |
| 建置 | Vite 7 |
| 樣式 | Tailwind CSS 4 |
| PWA | vite-plugin-pwa（Workbox） |
| 資料抓取 | Python 3.12 + FinMind + yfinance |
| 排程 | GitHub Actions cron |
| 部署 | GitHub Pages |

### 檔案結構

```
.
├── src/
│   ├── main.js                  # Vue app 啟動
│   ├── App.vue                  # 主版型 + 導覽列 + 更新時間
│   ├── style.css                # Tailwind 入口
│   ├── router/index.js          # 路由（hash router）
│   ├── stores/watchlist.js      # 自選股 store（localStorage）
│   ├── components/
│   │   ├── BandChart.vue        # 估值帶狀圖（純 SVG，無依賴）
│   │   ├── CandleChart.vue      # 日 K + MA + 成交量
│   │   └── ChipsChart.vue       # 三大法人堆疊柱狀
│   └── views/
│       ├── HomeView.vue         # 清單頁
│       ├── StockDetailView.vue  # 個股估值頁（嵌入 BandChart）
│       ├── WatchlistView.vue    # 自選股頁
│       ├── ETFListView.vue      # ETF 全覽 + 評分
│       ├── MarketView.vue       # 大盤（TAIEX/OTC + 三大法人）
│       ├── ADRDashboardView.vue # ADR 訊號儀表板
│       └── AboutView.vue        # 估值方法說明
├── public/
│   └── icon.svg                 # App / PWA / favicon 圖示
├── data/                        # 由 Python script 寫入；前端 fetch 為靜態 JSON
│   ├── stocks.json              # 預載清單 + ADR 對應（含 dashboard:true headline 標記）
│   ├── fx.json                  # USD/TWD 匯率 + VIX
│   ├── last_updated.json        # 全站資料更新時間（顯示在 footer）
│   ├── adr_signal.json          # 夜盤訊號當日快照（3 檔 ADR 溢價 + SOX）
│   ├── adr_history.json         # 夜盤訊號滾動歷史（365 天，含 SOX）
│   ├── adr_prediction.json      # Ridge + Conformal 預測（明日 TW 開/高/低 + 30 日 walk-forward 驗證）
│   ├── etf_list.json            # 全 ETF 清單 + 4 維相對評分
│   ├── market.json              # TAIEX/OTC + 三大法人 30 日買賣超
│   └── tw/{code}.json           # 每檔股票估值資料 + price_history + kline + chips
├── scripts/
│   ├── fetch_tw.py              # 抓台股 + 計算估值
│   ├── fetch_us.py              # 抓 ADR + 匯率 + SOX
│   ├── fetch_etf.py             # 抓 ETF 全覽 + 4 維評分
│   ├── fetch_market.py          # 抓 TAIEX/OTC + 三大法人
│   ├── predict_open_high_low.py # Ridge + Conformal 隔日預測 + walk-forward
│   └── requirements.txt
├── .github/workflows/
│   ├── deploy.yml               # 部署 Pages（push + cron）
│   ├── fetch-tw.yml             # 台股抓取 cron
│   └── fetch-us.yml             # 美股抓取 + Ridge 預測 cron
├── vite.config.js               # Vite + PWA 設定
├── index.html
└── package.json
```

### 資料流程

```
FinMind / yfinance
       │
       ▼
GitHub Actions cron  ──commit──►  data/*.json (在 main branch)
                                          │
                                          ▼
                                   GitHub Pages
                                   (純靜態 SPA)
                                          │
                                          ▼
                                  瀏覽器 fetch JSON
                                          │
                                          ▼
                                     Vue 渲染
```

純靜態：沒有後端、沒有資料庫、沒有 CORS 問題。

---

## 自動排程

GitHub Actions 自動跑（時間皆為台北時間 UTC+8）：

| Workflow | 觸發時機 | 動作 |
|----------|----------|------|
| `fetch-tw.yml` | 工作日 14:00 | 抓台股收盤 + 算估值 + ETF + 大盤 + commit |
| `fetch-us.yml` | 工作日 05:00 | 抓 ADR + 匯率 + SOX → 跑 Ridge 預測 → commit |
| `deploy.yml` | push 時 + 工作日 14:15 / 05:15 | 建置 + 部署到 Pages |

> Note：GITHUB_TOKEN 觸發的 push 不會啟動其他 workflow，所以 deploy 用獨立 cron 在 fetch 後 15 分鐘跑。

### 加 FinMind Token（推薦）

預設 FinMind 限制每小時 600 次。註冊取得 token 可拉到每天 1000+：

1. 註冊 [finmindtrade.com](https://finmindtrade.com/)
2. 從個人頁面取 token
3. 開 [Settings → Secrets → Actions](https://github.com/oomao/Triprice/settings/secrets/actions)
4. 新增 secret：name `FINMIND_TOKEN`、value 你的 token

---

## 自訂

### 新增 / 移除預載股票

編輯 `data/stocks.json`：

```json
{
  "categories": {
    "semiconductor": {
      "label": "半導體",
      "stocks": ["2330", "2454", "..."]
    }
  },
  "tw_stocks": {
    "2330": { "name": "台積電", "valuation_method": "yield", "adr": "TSM" }
  }
}
```

加完跑 `python scripts/fetch_tw.py` 抓資料、commit、push 即可。

### 修改估值公式

`scripts/fetch_tw.py` 裡的 `compute_yield_valuation` 與 `compute_pe_valuation` 函數。

### 換 App 名稱 / 圖示

- 名稱：`vite.config.js` 的 `manifest.name`、`short_name`、`index.html` 的 `<title>`
- 圖示：`public/icon.svg`

---

## 部署到自己的 GitHub

1. Fork / clone 這個 repo 到你的帳號
2. 改 `vite.config.js` 裡 `BASE` 變數為 `/<你的-repo-名稱>/`
3. push 到 main
4. 開 Settings → Pages → Source 選 **GitHub Actions**
5. 等 deploy workflow 跑完即可看到網站

---

## 疑難排解

**Deploy 顯示 `configure-pages` 失敗**  
GitHub Pages 還沒啟用。Settings → Pages → Source 選 "GitHub Actions"，再 push 一個 commit 重觸發即可。

**個股頁顯示「尚無此股票的估值資料」**  
代表 `data/tw/{code}.json` 不存在。手動跑 `python scripts/fetch_tw.py {code}` 補抓，或在 `stocks.json` 加進去等下次 cron。

**殖利率法的便宜價低得不合理**  
成長股本身殖利率就低，便宜價會被算得很低。請改看 PE 法（個股頁同時顯示）。系統會在平均殖利率 < 2% 時自動提醒。

**0050 / 0056 沒有 PE 法資料**  
ETF 沒有 EPS 概念，所以沒 PE。改看殖利率法即可。

**自選股加了不在預載清單的代號，顯示「尚無資料」**  
預設只有 26 檔有抓資料。要看其他股票，把代號加進 `data/stocks.json` 並執行 `python scripts/fetch_tw.py {code}`。

---

## 免責聲明

本工具資料僅供研究與學習參考，**不構成任何投資建議**。

- 估值方法為簡化模型，可能與專業分析存在差異
- 資料來源（FinMind、Yahoo Finance）可能有錯誤或延遲
- 投資有風險，請自行評估後決策

---

## 授權

MIT
