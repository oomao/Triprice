<script setup>
</script>

<template>
  <div class="prose max-w-none">
    <h1 class="text-2xl font-bold mb-4">說明</h1>

    <section class="mb-6 bg-white rounded-lg shadow-sm border border-slate-200 p-5">
      <h2 class="text-lg font-semibold mb-2">殖利率法（主）</h2>
      <ul class="text-sm text-slate-700 space-y-1 list-disc list-inside">
        <li><strong>便宜價</strong> = 最近一年現金股利 / 近 3 年最高殖利率</li>
        <li><strong>合理價</strong> = 最近一年現金股利 / 近 3 年平均殖利率</li>
        <li><strong>昂貴價</strong> = 最近一年現金股利 / 近 3 年最低殖利率</li>
      </ul>
      <p class="text-xs text-slate-500 mt-3 leading-relaxed">
        ⚠️ 殖利率法<strong>對成長股嚴重低估</strong>（成長股殖利率本身低，例如台積電）。
        若該股殖利率長期低於 2%，請以下方 PE 法為主要參考。
      </p>
    </section>

    <section class="mb-6 bg-white rounded-lg shadow-sm border border-slate-200 p-5">
      <h2 class="text-lg font-semibold mb-2">本益比 (PE) 法（附）</h2>
      <ul class="text-sm text-slate-700 space-y-1 list-disc list-inside">
        <li><strong>便宜價</strong> = 近 4 季 EPS × 近 3 年最低 PE</li>
        <li><strong>合理價</strong> = 近 4 季 EPS × 近 3 年平均 PE</li>
        <li><strong>昂貴價</strong> = 近 4 季 EPS × 近 3 年最高 PE</li>
      </ul>
    </section>

    <section class="mb-6 bg-white rounded-lg shadow-sm border border-slate-200 p-5">
      <h2 class="text-lg font-semibold mb-2">ADR 比較</h2>
      <div class="text-sm text-slate-700 space-y-2">
        <p><strong>ADR 隱含台股價</strong> = ADR 收盤 × USD/TWD ÷ 每 ADR 對應股數</p>
        <p><strong>溢價率</strong> = (ADR 隱含台股價 − 台股收盤) / 台股收盤</p>
        <p class="text-xs text-slate-500 leading-relaxed">
          ⏰ ADR「當日」收盤實際在台股收盤後 14~15 小時（美東 16:00 = 台北隔日 04:00），
          所以這個溢價率反而會 leading 台股<strong>隔日</strong>開盤方向。
        </p>
      </div>
    </section>

    <section class="bg-amber-50 border border-amber-200 rounded-lg p-4 text-xs text-slate-700 leading-relaxed">
      ⚠️ 本工具資料僅供研究與學習參考，<strong>非投資建議</strong>。
      投資有風險，請自行評估後決策。
    </section>
  </div>
</template>
