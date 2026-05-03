# Triprice — 三價儀

台股估值小工具：殖利率法為主、PE 法為輔，含美股 ADR 比較。

純前端 PWA，部署在 GitHub Pages。資料每日由 GitHub Actions 自動抓取並 commit 為靜態 JSON。

## 功能

- 便宜 / 合理 / 昂貴價計算（殖利率法 + PE 法）
- EPS / 成長率財報明細
- ADR vs 台股收盤價比較（含溢價率，可作為台股隔日開盤訊號）
- 自選股管理（localStorage，可手動輸入任意代號）
- PWA：可安裝到主畫面、離線可用
- RWD：手機 / 平板 / 桌機自動適配

## 估值公式

**殖利率法（主）**

| | 公式 |
|--|------|
| 便宜價 | 最近一年現金股利 / 近 3 年最高殖利率 |
| 合理價 | 最近一年現金股利 / 近 3 年平均殖利率 |
| 昂貴價 | 最近一年現金股利 / 近 3 年最低殖利率 |

**本益比 (PE) 法（附）**

| | 公式 |
|--|------|
| 便宜價 | 近 4 季 EPS × 近 3 年最低 PE |
| 合理價 | 近 4 季 EPS × 近 3 年平均 PE |
| 昂貴價 | 近 4 季 EPS × 近 3 年最高 PE |

⚠️ 殖利率法對成長股嚴重低估，成長股請以 PE 法為主。

**ADR 比較**

```
ADR 隱含台股價 = ADR 收盤 × USD/TWD ÷ 每 ADR 對應股數
ADR 溢價率   = (ADR 隱含台股價 - 台股收盤) / 台股收盤
```

## 開發

```bash
npm install
npm run dev          # 開發伺服器 (http://localhost:5173)
npm run build        # 建置生產版本
npm run preview      # 預覽建置結果
```

## 資料抓取

```bash
# 安裝 Python 依賴
pip install -r scripts/requirements.txt

# 抓取台股資料
python scripts/fetch_tw.py

# 抓取美股 ADR + 匯率
python scripts/fetch_us.py
```

資料來源：
- 台股報價 / 股利 / 財報：FinMind
- 美股 ADR / 匯率：Yahoo Finance (yfinance)

## 部署

推送到 `main` 後，GitHub Actions 自動建置並部署到 GitHub Pages。

兩個 cron 排程自動更新資料：
- 台股：台北 14:00（收盤後 30 分）
- 美股：台北隔日 05:00（美股收盤後）

## 免責聲明

本工具資料僅供研究與學習參考，**非投資建議**。投資有風險，請自行評估。
