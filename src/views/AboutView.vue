<script setup>
import { ref } from 'vue'

const showRidgeDetails = ref(false)
</script>

<template>
  <div class="space-y-6">
    <header>
      <h1 class="text-2xl font-bold tracking-tight mb-1">說明</h1>
      <p class="text-sm text-slate-500">完整估值方法 / 圖表怎麼讀 / 訊號邏輯 / 資料來源</p>
    </header>

    <!-- 1. 三價估值總覽 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">概念</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">什麼是「三價」</h2>
      <p class="text-sm leading-relaxed mb-2">
        三價 = <strong>便宜價 / 合理價 / 昂貴價</strong>。把同一檔股票過去的<strong>實際交易結果</strong>當基準，
        推算出三條目標價：歷史上最常被認為「便宜」的價位、最常見的「合理」位置、以及最常被視為「昂貴」的高點。
      </p>
      <ul class="text-xs text-slate-600 leading-relaxed space-y-1 list-disc list-outside ml-5">
        <li>當前股價 ≤ 便宜價 → 歷史百分位偏低，價格相對便宜</li>
        <li>便宜價 &lt; 當前 ≤ 合理價 → 接近長期平均</li>
        <li>合理價 &lt; 當前 ≤ 昂貴價 → 估值偏高</li>
        <li>當前 &gt; 昂貴價 → 比歷史上 95% 的時間都還貴</li>
      </ul>
      <p class="text-[11px] text-slate-500 mt-3 leading-relaxed border-l-2 border-amber-400 pl-3">
        三價是<strong>歷史相對位置</strong>，不是「真正的內在價值」。基本面結構性改變（例如護城河變寬、產業地位改變）後，
        過去的便宜可能再也回不去；反之亦然。請把它當參考座標，不是真理。
      </p>
    </section>

    <!-- 2. 殖利率法 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">公式</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">殖利率法</h2>
      <p class="text-sm leading-relaxed mb-3">適合<strong>穩定配息</strong>的標的（金融股、傳產龍頭、配息型 ETF）。</p>
      <div class="bg-slate-50 border border-slate-200 p-3 mb-3 font-mono text-xs space-y-1">
        <div>便宜價 = 最近一年現金股利 ÷ 近 3 年第 95 百分位殖利率</div>
        <div>合理價 = 最近一年現金股利 ÷ 近 3 年平均殖利率</div>
        <div>昂貴價 = 最近一年現金股利 ÷ 近 3 年第 5 百分位殖利率</div>
      </div>
      <p class="text-xs leading-relaxed mb-2">
        殖利率區間取自過去 3 年「<strong>每個交易日</strong>」的殖利率（年股利 ÷ 當日收盤），
        取第 5/95 百分位（過濾極端尾部 5%），比直接拿三年最高/最低值更穩定。
      </p>
      <p class="text-[11px] text-slate-500 leading-relaxed border-l-2 border-amber-400 pl-3">
        ⚠ 殖利率法<strong>對成長股嚴重低估</strong>。成長股殖利率本身低（例如台積電長期 1~2%），
        把這個分母倒過來算便宜價會得到非常離譜的數字。若該股殖利率長期低於 2%，請以下方 PE 法為主要參考。
        個股頁會自動偵測並提示。
      </p>
    </section>

    <!-- 3. PE 法 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">公式</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">本益比 (PE) 法</h2>
      <p class="text-sm leading-relaxed mb-3">適合<strong>所有有獲利的個股</strong>，特別是成長股。ETF 沒有 EPS 概念，沒有 PE 法。</p>
      <div class="bg-slate-50 border border-slate-200 p-3 mb-3 font-mono text-xs space-y-1">
        <div>便宜價 = 近 4 季 EPS 合計 × 近 3 年第 5 百分位 PE</div>
        <div>合理價 = 近 4 季 EPS 合計 × 近 3 年平均 PE</div>
        <div>昂貴價 = 近 4 季 EPS 合計 × 近 3 年第 95 百分位 PE</div>
      </div>
      <p class="text-xs leading-relaxed">
        近 4 季 EPS 合計（TTM, Trailing Twelve Months）反映最新的獲利水準。
        PE 區間同樣取自每日歷史 PE 的 5/95 百分位。
      </p>
    </section>

    <!-- 4. 安全邊際 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">風險控管</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">安全邊際（Margin of Safety）</h2>
      <p class="text-sm leading-relaxed mb-3">
        安全邊際是 Benjamin Graham 與 Warren Buffett 都強調的觀念：
        <strong>用比估值低 X% 的價位才進場</strong>，當作「估值錯誤、未來變差」的緩衝。
      </p>
      <p class="text-sm leading-relaxed mb-3">
        在個股頁的「進階設定」可以拉一個 <strong>0~50%</strong> 的 slider：
      </p>
      <div class="bg-slate-50 border border-slate-200 p-3 mb-3 font-mono text-xs space-y-1">
        <div>套用後的便宜價 = 原便宜價 × (1 − 安全邊際%)</div>
        <div>套用後的合理價 = 原合理價 × (1 − 安全邊際%)</div>
        <div>昂貴價不變（賣出參考用）</div>
      </div>
      <p class="text-xs leading-relaxed mb-2">
        例：原合理價 113，套用 20% 安全邊際後，合理價變成 90.4 元才會被當作合理進場點。
        昂貴價刻意保持原值，因為「該不該賣」的標準應該嚴格、不該因安全邊際把賣出條件也放寬。
      </p>
      <p class="text-[11px] text-slate-500 leading-relaxed border-l-2 border-[#b4530b] pl-3">
        典型用法：估值有不確定性的個股（產業變動快、EPS 波動大）拉 15~25%；
        相對穩定的成熟產業 0~10% 即可；對自己看法很保守的人可以拉到 30%+。
        個股頁的「進階設定」也允許自訂股利金額、自訂 EPS（例：用預估明年 EPS）來逼真模擬。
      </p>
    </section>

    <!-- 5. 估值帶狀圖 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">視覺化</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">估值帶狀圖怎麼讀</h2>
      <ul class="text-sm leading-relaxed space-y-1.5 mb-3 list-disc list-outside ml-5">
        <li>黑色折線：過去 3 年的<strong>實際收盤價</strong>走勢</li>
        <li>三條虛線：用目前的 EPS / 股利推回去畫出來的 便宜價（綠）/ 合理價（藍）/ 昂貴價（紅）</li>
        <li>四個色帶（從上到下）：紅 = 昂貴以上、琥珀 = 合理~昂貴、淺綠 = 便宜~合理、深綠 = 便宜以下</li>
        <li>右邊圓點 + 數字：當前股價</li>
        <li>圖下方數字：「目前位置 X%」── 0% = 完全便宜、100% = 完全昂貴、可超出 0~100 的範圍</li>
      </ul>
      <p class="text-[11px] text-slate-500 leading-relaxed">
        因為三條參考線是用<strong>當前</strong>EPS/股利推回去的，所以參考線是水平的、不是隨歷史變動的真河流圖。
        但這就是優點：你看到的是「<strong>過去 3 年的價格落在現在的估值帶哪裡</strong>」，
        而不是「過去某個 EPS 對應的便宜價」。
      </p>
    </section>

    <!-- 6. ADR 訊號 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">領先訊號</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">夜盤訊號（ADR + SOX）</h2>
      <div class="bg-slate-50 border border-slate-200 p-3 mb-3 font-mono text-xs space-y-1">
        <div>ADR 隱含台股價 = ADR 收盤 × USD/TWD ÷ 每 ADR 對應股數</div>
        <div>溢價率 = (ADR 隱含台股價 − 台股收盤) ÷ 台股收盤</div>
      </div>
      <p class="text-sm leading-relaxed mb-3">
        關鍵是<strong>時差</strong>：ADR 與費半指數在美國時間 16:00 收盤 = 台北隔日凌晨 4 點，比台股收盤晚 14~15 小時。
        所以這些報價已經反映了「台股收盤 → 美股收盤」這段期間的全球新聞、美股波動，台股<strong>明天開盤</strong>會補上這段差距。
      </p>
      <p class="text-xs leading-relaxed mb-2">
        <strong>/adr 儀表板</strong>聚焦於 3 檔重點 ADR + 費城半導體指數：
      </p>
      <table class="w-full text-xs mb-3 border border-[#e7e7e1]">
        <thead>
          <tr class="bg-slate-50 text-slate-600">
            <th class="px-2 py-1.5 text-left">代號</th>
            <th class="px-2 py-1.5 text-left">對應台股 / 標的</th>
            <th class="px-2 py-1.5 text-right">換算比例</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">TSM</td><td class="px-2 py-1.5">2330 台積電</td><td class="px-2 py-1.5 text-right font-mono">1 ADR : 5 股</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">HNHPF</td><td class="px-2 py-1.5">2317 鴻海（OTC 非贊助 ADR）</td><td class="px-2 py-1.5 text-right font-mono">1 ADR : 2 股</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">ASX</td><td class="px-2 py-1.5">3711 日月光投控</td><td class="px-2 py-1.5 text-right font-mono">1 ADR : 2 股</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">^SOX</td><td class="px-2 py-1.5">費城半導體指數（全市場 sector）</td><td class="px-2 py-1.5 text-right font-mono">直接看漲跌幅</td></tr>
        </tbody>
      </table>
      <p class="text-xs leading-relaxed mb-2">
        <strong>ADR 平均訊號</strong>：3 檔 ADR 溢價等權平均，分成 5 檔：
      </p>
      <table class="w-full text-xs mb-3 border border-[#e7e7e1]">
        <thead>
          <tr class="bg-slate-50 text-slate-600">
            <th class="px-2 py-1.5 text-left">平均溢價</th>
            <th class="px-2 py-1.5 text-left">訊號</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">≥ +5%</td><td class="px-2 py-1.5 text-red-600 font-semibold">強烈偏多</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">+1% ~ +5%</td><td class="px-2 py-1.5 text-red-500">偏多</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">−1% ~ +1%</td><td class="px-2 py-1.5">中性</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">−5% ~ −1%</td><td class="px-2 py-1.5 text-emerald-500">偏空</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">≤ −5%</td><td class="px-2 py-1.5 text-emerald-700 font-semibold">強烈偏空</td></tr>
        </tbody>
      </table>
      <p class="text-xs leading-relaxed mb-2">
        <strong>SOX 訊號</strong>：直接看當日漲跌幅，分成 5 檔：
      </p>
      <table class="w-full text-xs border border-[#e7e7e1]">
        <thead>
          <tr class="bg-slate-50 text-slate-600">
            <th class="px-2 py-1.5 text-left">SOX 當日漲跌</th>
            <th class="px-2 py-1.5 text-left">訊號</th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">≥ +2%</td><td class="px-2 py-1.5 text-red-600 font-semibold">強勢</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">+0.5% ~ +2%</td><td class="px-2 py-1.5 text-red-500">偏多</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">−0.5% ~ +0.5%</td><td class="px-2 py-1.5">中性</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">−2% ~ −0.5%</td><td class="px-2 py-1.5 text-emerald-500">偏弱</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5 font-mono">≤ −2%</td><td class="px-2 py-1.5 text-emerald-700 font-semibold">弱勢</td></tr>
        </tbody>
      </table>
      <p class="text-[11px] text-slate-500 mt-3 leading-relaxed">
        UMC（2303 聯電）、CHT（2412 中華電）的 ADR 仍會抓取並顯示在個股頁，但不納入 /adr 儀表板的 headline 平均。
        歷史走勢以 sparkline 呈現（每日累積到 <code>adr_history.json</code>，最多保留 365 天）。
      </p>

      <hr class="my-4 border-[#e7e7e1]">
      <h3 class="text-base font-semibold tracking-tight mb-2">明日開盤 / 高 / 低 預測</h3>
      <p class="text-sm leading-relaxed mb-2">
        把 ADR 報酬扣掉匯率和大盤影響，再加上偏離常態的溢價，用回歸算明天 TW 開盤的<strong>合理區間</strong>。
        每天 cron 用 ~2 年歷史重新訓練，過去 30 天每日預測 vs 實際對照即時可見。
      </p>
      <button
        @click="showRidgeDetails = !showRidgeDetails"
        class="text-xs text-slate-500 hover:text-slate-900 underline mb-2"
      >
        {{ showRidgeDetails ? '收起技術細節 ▴' : '展開技術細節 ▾' }}
      </button>
      <div v-if="showRidgeDetails" class="text-sm leading-relaxed space-y-2 mt-2 pt-2 border-t border-[#e7e7e1]">
        <p>
          <code>scripts/predict_open_high_low.py</code> 用 Ridge 回歸 + 80% Conformal 區間，把每日訊號合成<strong>單一預測 + 校準區間</strong>，預測隔日 TW 開盤 / 盤中最高 / 盤中最低三條，寫入 <code>data/adr_prediction.json</code>。
        </p>
        <p><strong>訊號乾淨化</strong>：</p>
        <ul class="text-xs list-disc pl-5 space-y-1 text-slate-600">
          <li><strong>ADR alpha</strong> = ADR USD 漲跌 − USD/TWD 漲跌 − rolling 90d β · SOX 漲跌（剝掉 FX 與 sector beta，留下純個股 alpha）</li>
          <li><strong>SOX</strong> 整體漲跌 %（保留 sector 訊號）</li>
          <li><strong>溢價 z-score</strong> = (今日溢價 − 60d rolling median) / MAD（去掉結構性偏移，例如 TSMC 長期 8%+ 溢價）</li>
        </ul>
        <p><strong>事件日剔除</strong>（從訓練集中扣除）：</p>
        <ul class="text-xs list-disc pl-5 space-y-1 text-slate-600">
          <li>除息日 T 與 T+1（FinMind <code>TaiwanStockDividend</code>）</li>
          <li>TW 漲跌停（|change| &gt; 9.5%）</li>
          <li>長假後第一日（calendar gap &gt; 3）</li>
          <li>ADR 成交量 = 0（HNHPF 鴻海 OTC 常見）</li>
        </ul>
        <p><strong>建模 + 驗證</strong>：</p>
        <ul class="text-xs list-disc pl-5 space-y-1 text-slate-600">
          <li>RidgeCV 三訊號合成 → 單一點估，per-stock per-target 校準權重</li>
          <li>80% Conformal 區間（finite-sample valid coverage 保證）</li>
          <li>Walk-forward：過去 30 個交易日，每日重新訓練、預測、跟實際比對</li>
          <li>一致性 enforce：高 ≥ 開 ≥ 低（少數情況自動 clip）</li>
        </ul>
        <p class="text-[11px] text-slate-500">
          盤中最高 / 最低 RMSE 通常較大（極值有 long tail），當作「合理範圍上下限」而非精確 target。
        </p>
      </div>
    </section>

    <!-- 7. ETF 評分 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">ETF 全覽</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">綜合分計算</h2>
      <p class="text-sm leading-relaxed mb-3">
        <strong>4 維相對排名</strong>，每維 0~100 分（min-max normalize 到當前清單），等權平均得綜合分：
      </p>
      <ul class="text-xs space-y-1 mb-3 list-disc list-outside ml-5 leading-relaxed">
        <li><strong>殖利率分</strong>：TTM 現金股利 ÷ 現價，越高越好</li>
        <li><strong>1Y 報酬分</strong>：近 1 年含息報酬，越高越好（單日跌幅 &gt; 30% 視為分割/減資，會跳過）</li>
        <li><strong>規模分</strong>：近 60 日平均成交金額 log10，越大越好（流動性好）</li>
        <li><strong>穩定度分</strong>：年化波動度（日報酬 std × √250），越低越好</li>
      </ul>
      <p class="text-[11px] text-slate-500 leading-relaxed">
        分母是「當前清單裡的所有 ETF」，所以這是<strong>同儕中的相對排名</strong>，不是絕對標準。
        FinMind 免費版未提供費用率，因此費用率沒納入評分。
      </p>
    </section>

    <!-- 8. K 線 + 籌碼 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">技術面 + 籌碼</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">K 線與三大法人</h2>
      <ul class="text-sm leading-relaxed space-y-1.5 list-disc list-outside ml-5">
        <li><strong>K 線</strong>：紅漲綠跌（台股慣例，與美股相反）；可切換 1M / 3M / 6M / 1Y</li>
        <li><strong>MA5 / MA20 / MA60</strong>：5 / 20 / 60 日移動平均線（短/中/長）。三條同時上揚 = 多頭排列</li>
        <li><strong>成交量</strong>：副圖柱狀；顏色與當日 K 棒一致</li>
        <li><strong>三大法人籌碼</strong>：堆疊柱狀圖；外資 + 投信 + 自營，正向（買超）置中線上、負向（賣超）置中線下</li>
        <li>4 張 5 日累計卡：方便觀察短期方向（連續買超 vs 連續賣超）</li>
      </ul>
      <p class="text-[11px] text-slate-500 mt-3 leading-relaxed">
        單位：每股票籌碼採股數（FinMind 慣例），UI 顯示為「萬股 / 千萬股」；大盤頁的三大法人是新台幣金額（億元）。
      </p>
    </section>

    <!-- 9. 自選組合 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">自選頁</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">組合便宜度</h2>
      <p class="text-sm leading-relaxed mb-2">
        把所有自選股的「目前位置百分位」平均起來，得到「整體組合在便宜~昂貴帶的位置」。
      </p>
      <ul class="text-xs leading-relaxed space-y-1 list-disc list-outside ml-5">
        <li>每檔位置 = (現價 − 便宜價) ÷ (昂貴價 − 便宜價) × 100%</li>
        <li>優先用 PE 法（成長股不會被殖利率法低估）；無 EPS 退回殖利率法</li>
        <li>同時標出組合中<strong>最便宜的一檔</strong>（潛在加碼候選）跟<strong>最貴的一檔</strong>（潛在減碼候選）</li>
      </ul>
    </section>

    <!-- 10. AI 摘要 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">可選功能</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">AI 個股摘要</h2>
      <p class="text-sm leading-relaxed mb-2">
        在個股頁手動點「生成摘要」，會把該檔的估值狀態、EPS 趨勢、ADR 溢價等資料丟給 LLM，
        產出 2~3 句客觀摘要（不給投資建議）。
      </p>
      <p class="text-sm leading-relaxed mb-2">
        到「<RouterLink to="/settings" class="text-[#b4530b] underline">設定</RouterLink>」可選擇供應商並貼上自己的 API key：
      </p>
      <ul class="text-xs leading-relaxed space-y-1 list-disc list-outside ml-5 mb-3">
        <li><strong>Anthropic Claude</strong>（預設 claude-haiku-4-5）</li>
        <li><strong>OpenAI</strong>（預設 gpt-4o-mini）</li>
        <li><strong>Google Gemini</strong>（預設 gemini-2.0-flash）</li>
      </ul>
      <p class="text-[11px] text-slate-500 leading-relaxed border-l-2 border-amber-400 pl-3">
        <strong>本站沒有後端</strong>，瀏覽器直接呼叫對應供應商 API，金鑰只存在你這台裝置的 localStorage。
        本站無法替你保管金鑰、無法代為呼叫。請勿在公用電腦設定金鑰。
        摘要結果也快取在 localStorage（fingerprint 比對：股價或估值有變才會視為過期）。
      </p>
    </section>

    <!-- 11. 設定 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">個人化</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">設定</h2>
      <ul class="text-sm leading-relaxed space-y-1.5 list-disc list-outside ml-5">
        <li><strong>主題</strong>：日間 / 夜間 / 跟隨系統。系統模式會即時跟著作業系統的 light/dark 切換</li>
        <li><strong>字體大小</strong>：小 (14px) / 標準 (16px) / 大 (18px)。同時影響文字與間距（rem-based）</li>
        <li><strong>LLM 供應商與 API key</strong>：見上方說明</li>
      </ul>
      <p class="text-[11px] text-slate-500 mt-3 leading-relaxed">所有設定僅儲存在 localStorage，不會同步到任何伺服器。</p>
    </section>

    <!-- 12. 資料來源 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">出處</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">資料來源 與 更新頻率</h2>
      <table class="w-full text-xs border border-[#e7e7e1]">
        <thead>
          <tr class="bg-slate-50 text-slate-600">
            <th class="px-2 py-1.5 text-left">資料</th>
            <th class="px-2 py-1.5 text-left">來源</th>
            <th class="px-2 py-1.5 text-left">更新時間（台北時間）</th>
          </tr>
        </thead>
        <tbody class="text-slate-700">
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5">台股價格 / EPS / 股利 / 三大法人 / K 線</td><td class="px-2 py-1.5 font-mono">FinMind</td><td class="px-2 py-1.5">工作日 14:00</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5">ETF 全覽 / 大盤指數</td><td class="px-2 py-1.5 font-mono">FinMind</td><td class="px-2 py-1.5">工作日 14:00</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5">美股 ADR / USD-TWD 匯率</td><td class="px-2 py-1.5 font-mono">Yahoo Finance</td><td class="px-2 py-1.5">工作日 05:00</td></tr>
          <tr class="border-t border-[#e7e7e1]"><td class="px-2 py-1.5">頁面部署</td><td class="px-2 py-1.5 font-mono">GitHub Pages</td><td class="px-2 py-1.5">資料更新後 15 分鐘</td></tr>
        </tbody>
      </table>
      <p class="text-[11px] text-slate-500 mt-3 leading-relaxed">
        FinMind 免費版每小時 600 次請求；若 GitHub Actions 有設 <code>FINMIND_TOKEN</code> 可拉到每天 1000+。
        ADR 用 yfinance 抓不需要 token。資料抓完直接 commit 進 repo，前端 fetch 純靜態 JSON，沒有後端、沒有 CORS。
      </p>
    </section>

    <!-- 13. 已知限制 -->
    <section class="bg-white border border-[#e7e7e1] p-5">
      <div class="text-xs uppercase tracking-[0.16em] text-slate-500 mb-1">老實說</div>
      <h2 class="text-lg font-semibold tracking-tight mb-3">已知限制</h2>
      <ul class="text-xs space-y-2 list-disc list-outside ml-5 leading-relaxed">
        <li><strong>未還原權息</strong>：FinMind 免費版未提供調整還原價，因此分割（如 0050 在 2024-12 拆分 1:4）會讓 1Y 報酬被誤算。系統已加入單日 &gt; 30% 跌幅偵測，遇到會顯示 N/A 而非錯誤數字。</li>
        <li><strong>估值帶為水平線</strong>：用「當前 EPS/股利」推回去畫，不是真河流圖。基本面長期變化會讓帶狀偏離歷史。</li>
        <li><strong>ETF 評分為相對排名</strong>：分母是當前清單，換清單分數會變。費用率因 FinMind 不提供，未納入。</li>
        <li><strong>ADR 訊號是統計參考</strong>，不是必中規律。隔日台股仍可能因國內事件偏離 ADR 隱含方向。</li>
        <li><strong>非預載個股</strong>：只支援即時抓取（約 5 秒），抓回的資料不會被快取超過 6 小時。</li>
      </ul>
    </section>

    <!-- 14. 免責 -->
    <section class="bg-amber-50 border border-amber-200 p-4 text-xs leading-relaxed">
      <strong class="block mb-1">免責聲明</strong>
      本工具資料僅供研究與學習參考，<strong>非投資建議</strong>。
      估值方法為簡化模型，可能與專業分析存在差異。資料來源（FinMind / Yahoo Finance）可能有錯誤或延遲。
      投資有風險，請自行評估後決策。
    </section>
  </div>
</template>
