<script setup>
</script>

<template>
  <div>
    <h1 class="text-xl font-bold tracking-tight mb-1">說明</h1>
    <p class="text-xs text-slate-500 mb-5">估值方法與資料來源</p>

    <section class="mb-4 bg-white border border-[#e7e7e1] p-5">
      <div class="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">主要</div>
      <h2 class="text-base font-semibold mb-3 tracking-tight">殖利率法</h2>
      <ul class="text-sm text-slate-700 space-y-1.5 leading-relaxed">
        <li><strong>便宜價</strong> = 最近一年現金股利 ÷ 近 3 年第 95 百分位殖利率</li>
        <li><strong>合理價</strong> = 最近一年現金股利 ÷ 近 3 年平均殖利率</li>
        <li><strong>昂貴價</strong> = 最近一年現金股利 ÷ 近 3 年第 5 百分位殖利率</li>
      </ul>
      <p class="text-xs text-slate-500 mt-3 leading-relaxed border-l-2 border-amber-400 pl-3">
        殖利率法<strong>對成長股嚴重低估</strong>（成長股殖利率本身低，例如台積電）。
        若該股殖利率長期低於 2%，請以下方 PE 法為主要參考。
      </p>
    </section>

    <section class="mb-4 bg-white border border-[#e7e7e1] p-5">
      <div class="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">附加</div>
      <h2 class="text-base font-semibold mb-3 tracking-tight">本益比（PE）法</h2>
      <ul class="text-sm text-slate-700 space-y-1.5 leading-relaxed">
        <li><strong>便宜價</strong> = 近 4 季 EPS × 近 3 年第 5 百分位 PE</li>
        <li><strong>合理價</strong> = 近 4 季 EPS × 近 3 年平均 PE</li>
        <li><strong>昂貴價</strong> = 近 4 季 EPS × 近 3 年第 95 百分位 PE</li>
      </ul>
    </section>

    <section class="mb-4 bg-white border border-[#e7e7e1] p-5">
      <div class="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-1">領先訊號</div>
      <h2 class="text-base font-semibold mb-3 tracking-tight">ADR 溢價</h2>
      <ul class="text-sm text-slate-700 space-y-1.5 leading-relaxed">
        <li><strong>ADR 隱含台股價</strong> = ADR 收盤 × USD/TWD ÷ 每 ADR 對應股數</li>
        <li><strong>溢價率</strong> = (ADR 隱含台股價 − 台股收盤) ÷ 台股收盤</li>
      </ul>
      <p class="text-xs text-slate-500 mt-3 leading-relaxed border-l-2 border-[#b4530b] pl-3">
        ADR「當日」收盤其實是在台股收盤後 14~15 小時（美東 16:00 = 台北隔日 04:00），
        所以這個溢價率會 leading 台股<strong>隔日</strong>開盤方向。
      </p>
    </section>

    <section class="bg-amber-50 border border-amber-200 p-4 text-xs text-slate-700 leading-relaxed">
      <strong class="block mb-1">免責聲明</strong>
      本工具資料僅供研究與學習參考，<strong>非投資建議</strong>。
      投資有風險，請自行評估後決策。
    </section>
  </div>
</template>
