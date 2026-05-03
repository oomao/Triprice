<script setup>
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'

const signal = ref(null)
const history = ref([])
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  const base = import.meta.env.BASE_URL
  try {
    const [sigRes, histRes] = await Promise.all([
      fetch(`${base}data/adr_signal.json`),
      fetch(`${base}data/adr_history.json`),
    ])
    if (sigRes.ok) signal.value = await sigRes.json()
    if (histRes.ok) {
      const j = await histRes.json()
      history.value = (j.records || []).slice(-30)
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  })
}

function premiumClass(v) {
  if (v == null) return 'text-slate-400'
  if (v >= 5) return 'text-red-600 font-bold'
  if (v >= 1) return 'text-red-500'
  if (v > -1) return 'text-slate-600'
  if (v > -5) return 'text-emerald-500'
  return 'text-emerald-700 font-bold'
}

const signalColor = computed(() => {
  if (!signal.value) return 'bg-slate-100 text-slate-500'
  switch (signal.value.signal_code) {
    case 'strong_bull': return 'bg-red-50 border-red-300 text-red-700'
    case 'bull':        return 'bg-red-50 border-red-200 text-red-600'
    case 'neutral':     return 'bg-slate-50 border-slate-300 text-slate-700'
    case 'bear':        return 'bg-emerald-50 border-emerald-200 text-emerald-600'
    case 'strong_bear': return 'bg-emerald-50 border-emerald-300 text-emerald-700'
    default:            return 'bg-slate-100 text-slate-500'
  }
})

const headline = computed(() => {
  if (!signal.value) return null
  const v = signal.value.avg_premium_pct
  if (v == null) return null
  const direction =
    v >= 1 ? '台股隔日開盤偏多'
    : v <= -1 ? '台股隔日開盤偏空'
    : '台股隔日開盤偏中性'
  return { direction, value: v }
})

// Tiny sparkline for premium history.
const SPARK_W = 320
const SPARK_H = 60
const SPARK_PAD = 4

const sparkPath = computed(() => {
  if (!history.value.length) return ''
  const vals = history.value.map((h) => h.avg_premium_pct)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1
  const n = vals.length
  return vals
    .map((v, i) => {
      const x = SPARK_PAD + ((SPARK_W - SPARK_PAD * 2) * i) / Math.max(1, n - 1)
      const y = SPARK_PAD + (SPARK_H - SPARK_PAD * 2) * (1 - (v - min) / range)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

const sparkZero = computed(() => {
  if (!history.value.length) return null
  const vals = history.value.map((h) => h.avg_premium_pct)
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1
  return SPARK_PAD + (SPARK_H - SPARK_PAD * 2) * (1 - (0 - min) / range)
})
</script>

<template>
  <div>
    <h1 class="text-xl font-bold tracking-tight mb-1">ADR 訊號儀表板</h1>
    <p class="text-xs text-slate-500 mb-5 leading-relaxed">
      美股 ADR 收盤晚於台股約 14~15 小時，溢價可作為台股<strong>隔日開盤</strong>方向的領先訊號。
    </p>

    <div v-if="loading" class="text-slate-500 py-8 text-center">載入中…</div>
    <div v-else-if="!signal" class="bg-amber-50 border border-amber-200 p-4 text-sm text-slate-700 leading-relaxed">
      尚無 ADR 訊號資料 — 等下次美股收盤後（台北時間隔日清晨）由 GitHub Actions 自動產生。
    </div>
    <div v-else>
      <!-- Aggregate signal banner -->
      <section
        class="border-2 px-5 py-4 mb-5 flex items-center justify-between gap-4"
        :class="signalColor"
      >
        <div>
          <div class="text-xs uppercase tracking-wider opacity-70">整體訊號</div>
          <div class="text-2xl font-bold mt-0.5">{{ signal.signal_label }}</div>
          <div v-if="headline" class="text-sm mt-1 opacity-80">
            {{ headline.direction }}（4 檔 ADR 平均溢價
            <strong>{{ signal.avg_premium_pct >= 0 ? '+' : '' }}{{ fmt(signal.avg_premium_pct) }}%</strong>）
          </div>
        </div>
        <div class="text-right shrink-0">
          <div class="text-xs opacity-70">ADR 平均漲跌</div>
          <div class="text-lg font-bold">
            {{ signal.avg_adr_change_pct >= 0 ? '+' : '' }}{{ fmt(signal.avg_adr_change_pct) }}%
          </div>
        </div>
      </section>

      <!-- Per-ADR cards -->
      <section class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
        <RouterLink
          v-for="e in signal.adrs"
          :key="e.adr"
          :to="`/stock/${e.tw_code}`"
          class="block bg-white border border-[#e7e7e1] p-4 hover:border-[#0a0e16] transition"
        >
          <div class="flex items-baseline justify-between">
            <div>
              <div class="font-bold text-base">{{ e.tw_name }}</div>
              <div class="text-xs text-slate-500 mt-0.5 font-mono">{{ e.tw_code }} · ADR {{ e.adr }}</div>
            </div>
            <div class="text-right">
              <div class="text-xs text-slate-500">溢價</div>
              <div :class="premiumClass(e.premium_pct)" class="text-lg">
                {{ e.premium_pct >= 0 ? '+' : '' }}{{ fmt(e.premium_pct) }}%
              </div>
            </div>
          </div>
          <div class="mt-3 grid grid-cols-3 gap-2 text-xs">
            <div>
              <div class="text-slate-400">台股</div>
              <div class="font-mono">{{ fmt(e.tw_price) }}</div>
            </div>
            <div>
              <div class="text-slate-400">ADR 隱含</div>
              <div class="font-mono">{{ fmt(e.implied_tw_price) }}</div>
            </div>
            <div>
              <div class="text-slate-400">ADR 漲跌</div>
              <div :class="e.adr_change_pct >= 0 ? 'text-red-500' : 'text-emerald-600'" class="font-mono">
                {{ e.adr_change_pct >= 0 ? '+' : '' }}{{ fmt(e.adr_change_pct) }}%
              </div>
            </div>
          </div>
        </RouterLink>
      </section>

      <!-- History sparkline -->
      <section v-if="history.length >= 2" class="bg-white border border-[#e7e7e1] p-4 mb-6">
        <div class="flex items-baseline justify-between mb-2">
          <h2 class="text-base font-semibold">近 {{ history.length }} 個交易日平均溢價</h2>
          <span class="text-xs text-slate-500">
            最新 {{ history[history.length - 1]?.avg_premium_pct >= 0 ? '+' : '' }}{{ fmt(history[history.length - 1]?.avg_premium_pct) }}%
          </span>
        </div>
        <svg :viewBox="`0 0 ${SPARK_W} ${SPARK_H}`" preserveAspectRatio="none" class="w-full h-16">
          <line
            v-if="sparkZero != null"
            :x1="SPARK_PAD" :x2="SPARK_W - SPARK_PAD"
            :y1="sparkZero" :y2="sparkZero"
            stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="3 3"
          />
          <path :d="sparkPath" stroke="#b4530b" stroke-width="1.6" fill="none" stroke-linejoin="round" stroke-linecap="round" />
        </svg>
        <div class="flex justify-between text-[10px] text-slate-400 font-mono mt-1">
          <span>{{ history[0]?.date }}</span>
          <span>0%</span>
          <span>{{ history[history.length - 1]?.date }}</span>
        </div>
      </section>
      <section v-else class="bg-slate-50 border border-slate-200 p-3 mb-6 text-xs text-slate-500">
        歷史溢價趨勢需累積至少 2 個交易日（每日由 cron 自動寫入 <code>adr_history.json</code>）。
      </section>

      <!-- Methodology footer -->
      <div class="text-xs text-slate-500 leading-relaxed bg-slate-50 p-3 border border-slate-200">
        <p class="mb-1"><strong>計算邏輯</strong></p>
        <p>每檔 ADR 的隱含台股價 = ADR 收盤 × USD/TWD ÷ ratio；溢價 = (隱含價 − 台股收盤) ÷ 台股收盤。</p>
        <p class="mt-1">整體訊號 = 4 檔 ADR 溢價的等權平均，分成 5 檔（強烈偏空 / 偏空 / 中性 / 偏多 / 強烈偏多）。</p>
        <p class="mt-1 text-slate-400">
          USD/TWD = {{ fmt(signal.fx_rate, 3) }}（{{ signal.fx_date }}）· 訊號更新 {{ signal.updated?.replace(/:\d{2}\+\d{2}:\d{2}$/, '') }}
        </p>
      </div>
    </div>
  </div>
</template>
