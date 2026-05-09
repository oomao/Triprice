<script setup>
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'
import DiffBars from '../components/DiffBars.vue'

const signal = ref(null)
const history = ref([])
const prediction = ref(null)
const loading = ref(true)
const error = ref(null)
const expandedWalkForward = ref({}) // { tw_code: bool }

onMounted(async () => {
  const base = import.meta.env.BASE_URL
  try {
    const [sigRes, histRes, predRes] = await Promise.all([
      fetch(`${base}data/adr_signal.json`),
      fetch(`${base}data/adr_history.json`),
      fetch(`${base}data/adr_prediction.json`),
    ])
    if (sigRes.ok) signal.value = await sigRes.json()
    if (histRes.ok) {
      const j = await histRes.json()
      history.value = (j.records || []).slice(-30)
    }
    if (predRes.ok) prediction.value = await predRes.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function toggleWalkForward(code) {
  expandedWalkForward.value[code] = !expandedWalkForward.value[code]
}

// Hash router uses /#/adr; an <a href="#detail-X"> would clobber the entire
// hash and break the route. Use manual scroll instead.
function scrollToDetail(code) {
  const el = document.getElementById(`detail-${code}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function pctSign(v) {
  if (v == null || isNaN(v)) return '—'
  return (v >= 0 ? '+' : '') + Number(v).toFixed(2) + '%'
}

// Parse "2026-05-09 20:32:13+08:00" → ms-since-epoch (best effort).
function parseTpe(s) {
  if (!s) return null
  // Replace space with T to get a parseable ISO-ish format
  const iso = s.replace(' ', 'T')
  const t = Date.parse(iso)
  return isNaN(t) ? null : t
}

// Freshness badge for the prediction file: green ≤6h, amber 6–30h, red >30h.
const freshness = computed(() => {
  const ts = parseTpe(prediction.value?.updated)
  if (!ts) return null
  const ageHours = (Date.now() - ts) / 3.6e6
  let label, cls
  if (ageHours <= 1) {
    label = `${Math.max(0, Math.round(ageHours * 60))} 分鐘前更新`
    cls = 'bg-emerald-50 border-emerald-300 text-emerald-700'
  } else if (ageHours <= 6) {
    label = `${ageHours.toFixed(1)} 小時前更新`
    cls = 'bg-emerald-50 border-emerald-300 text-emerald-700'
  } else if (ageHours <= 30) {
    label = `${ageHours.toFixed(1)} 小時前更新`
    cls = 'bg-amber-50 border-amber-300 text-amber-700'
  } else {
    label = `${(ageHours / 24).toFixed(1)} 天前 · cron 可能失敗`
    cls = 'bg-rose-50 border-rose-300 text-rose-700'
  }
  return { label, cls, ageHours }
})

// Map of stock code → hnhpf_stale flag from prediction JSON (so we can propagate
// the warning onto the top per-ADR cards which only have signal data).
const staleByCode = computed(() => {
  const out = {}
  if (!prediction.value?.stocks) return out
  for (const code in prediction.value.stocks) {
    out[code] = !!prediction.value.stocks[code].signals_cleaned?.hnhpf_stale
  }
  return out
})

// Map tw_code → raw signal entry from adr_signal.json. Used to render the
// raw "today's TW vs ADR move" diff bars + premium chip inside each prediction
// card (so we don't show the same per-stock data in two separate sections).
const rawByCode = computed(() => {
  if (!signal.value?.adrs) return {}
  return Object.fromEntries(signal.value.adrs.map((a) => [a.tw_code, a]))
})

function pctClassPrediction(v) {
  if (v == null) return 'text-slate-400'
  if (v >= 1.5) return 'text-red-600 font-semibold'
  if (v >= 0.3) return 'text-red-500'
  if (v > -0.3) return 'text-slate-600'
  if (v > -1.5) return 'text-emerald-500'
  return 'text-emerald-700 font-semibold'
}

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

function changeClass(v) {
  if (v == null) return 'text-slate-400'
  if (v >= 2) return 'text-red-600 font-bold'
  if (v >= 0.5) return 'text-red-500'
  if (v > -0.5) return 'text-slate-600'
  if (v > -2) return 'text-emerald-500'
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

// SOX label derived purely from daily change %.
const soxLabel = computed(() => {
  const c = signal.value?.sox?.change_pct
  if (c == null) return null
  if (c >= 2)    return { text: '強勢',   cls: 'bg-red-50 border-red-300 text-red-700' }
  if (c >= 0.5)  return { text: '偏多',   cls: 'bg-red-50 border-red-200 text-red-600' }
  if (c > -0.5)  return { text: '中性',   cls: 'bg-slate-50 border-slate-300 text-slate-700' }
  if (c > -2)    return { text: '偏弱',   cls: 'bg-emerald-50 border-emerald-200 text-emerald-600' }
  return                  { text: '弱勢',   cls: 'bg-emerald-50 border-emerald-300 text-emerald-700' }
})

// Tiny sparkline for premium history.
const SPARK_W = 320
const SPARK_H = 60
const SPARK_PAD = 4

function sparkPathOf(vals) {
  if (!vals.length) return ''
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
}

function sparkZeroOf(vals) {
  if (!vals.length) return null
  const min = Math.min(...vals, 0)
  const max = Math.max(...vals, 0)
  const range = max - min || 1
  return SPARK_PAD + (SPARK_H - SPARK_PAD * 2) * (1 - (0 - min) / range)
}

const premiumVals = computed(() => history.value.map((h) => h.avg_premium_pct))
const sparkPath   = computed(() => sparkPathOf(premiumVals.value))
const sparkZero   = computed(() => sparkZeroOf(premiumVals.value))
const premiumRange = computed(() => {
  const v = premiumVals.value
  if (!v.length) return null
  return { min: Math.min(...v), max: Math.max(...v) }
})

const soxVals = computed(() =>
  history.value.map((h) => h.sox_change_pct).filter((v) => v != null && !isNaN(v))
)
const soxSparkPath = computed(() => sparkPathOf(soxVals.value))
const soxSparkZero = computed(() => sparkZeroOf(soxVals.value))
const soxRange = computed(() => {
  const v = soxVals.value
  if (!v.length) return null
  return { min: Math.min(...v), max: Math.max(...v) }
})
</script>

<template>
  <div>
    <div class="flex items-baseline justify-between gap-2 flex-wrap mb-1">
      <h1 class="text-2xl font-bold tracking-tight">夜盤領先訊號</h1>
      <span v-if="freshness"
            class="text-[11px] font-mono px-2 py-0.5 border"
            :class="freshness.cls">
        {{ freshness.label }}
      </span>
    </div>
    <p class="text-sm text-slate-500 mb-5 leading-relaxed">
      美股 ADR 與費城半導體指數收盤晚於台股約 14~15 小時，可作為台股<strong>隔日開盤</strong>方向的領先參考。
      聚焦：<strong>台積電 (TSM)</strong>、<strong>鴻海 (HNHPF)</strong>、<strong>日月光 (ASX)</strong> + <strong>SOX</strong>。
    </p>

    <div v-if="loading" class="text-slate-500 py-8 text-center">載入中…</div>
    <div v-else-if="!signal" class="bg-amber-50 border border-amber-200 p-4 text-sm text-slate-700 leading-relaxed">
      尚無 ADR 訊號資料 — 等下次美股收盤後（台北時間隔日清晨）由 GitHub Actions 自動產生。
    </div>
    <div v-else>
      <!-- 預測快覽 — answer first, before the raw signal banners -->
      <section v-if="prediction" class="mb-5 border-2 border-slate-900 bg-slate-50/60">
        <div class="px-4 py-2 bg-slate-900 text-slate-100 text-xs uppercase tracking-wider flex items-baseline justify-between flex-wrap gap-2">
          <span class="font-semibold">明日 TW 開盤預測 (Ridge + Conformal 80%)</span>
          <span class="opacity-70 font-mono normal-case tracking-normal">
            用 {{ Object.values(prediction.stocks)[0]?.tw_close_date }} 收盤推論隔日 TW 開盤
          </span>
        </div>
        <div class="divide-y divide-[#e7e7e1]">
          <button v-for="(stock, code) in prediction.stocks"
             :key="code"
             type="button"
             @click="scrollToDetail(code)"
             class="block w-full text-left px-4 py-2.5 hover:bg-amber-50 transition cursor-pointer">
            <div class="flex items-baseline justify-between gap-2 flex-wrap">
              <div class="min-w-0">
                <span class="font-semibold text-sm">{{ stock.name }}</span>
                <span class="text-xs text-slate-500 ml-1.5 font-mono">{{ code }}</span>
              </div>
              <div class="font-mono text-sm">
                <span class="font-bold text-base"
                      :class="pctClassPrediction(stock.predictions.open_gap?.point_pct)">
                  {{ pctSign(stock.predictions.open_gap?.point_pct) }}
                </span>
                <span class="text-xs text-slate-500 ml-1 whitespace-nowrap">
                  [{{ pctSign(stock.predictions.open_gap?.lo80_pct) }}, {{ pctSign(stock.predictions.open_gap?.hi80_pct) }}]
                </span>
              </div>
            </div>
            <div class="text-[11px] text-slate-500 font-mono mt-0.5 text-right">
              {{ fmt(stock.predictions.open_gap?.lo80_price, 0) }} ~ {{ fmt(stock.predictions.open_gap?.hi80_price, 0) }}
              <span v-if="stock.predictions.open_gap?.crosses_zero" class="text-amber-600 ml-1">⚠ 跨零</span>
            </div>
          </button>
        </div>
        <div class="px-4 py-1.5 text-[10px] text-slate-500 border-t border-[#e7e7e1]">
          詳細訊號分解、盤中高低預測、過去 30 天驗證 → 滑到下方各檔卡片
        </div>
      </section>

      <!-- Two-pane top: ADR aggregate + SOX (raw 速覽) -->
      <p v-if="prediction" class="text-[11px] text-slate-500 mb-1.5 leading-relaxed">
        ↓ 下方為 raw 速覽（未扣 SOX/FX 與結構性偏移）。預測請以上方
        <strong>Ridge + Conformal</strong> 為準。
      </p>
      <section class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-5">
        <!-- ADR aggregate -->
        <div
          class="border-2 px-4 sm:px-5 py-4 flex items-center justify-between gap-3 min-w-0"
          :class="signalColor"
        >
          <div>
            <div class="text-xs uppercase tracking-wider opacity-70">ADR 平均訊號</div>
            <div class="text-2xl font-bold mt-0.5">{{ signal.signal_label }}</div>
            <div v-if="headline" class="text-sm mt-1 opacity-80">
              {{ headline.direction }}
            </div>
          </div>
          <div class="text-right min-w-0">
            <div class="text-xs opacity-70">3 檔平均溢價</div>
            <div class="text-lg font-bold">
              {{ signal.avg_premium_pct >= 0 ? '+' : '' }}{{ fmt(signal.avg_premium_pct) }}%
            </div>
            <div class="text-[11px] opacity-70 mt-0.5">
              ADR 平均漲跌 {{ signal.avg_adr_change_pct >= 0 ? '+' : '' }}{{ fmt(signal.avg_adr_change_pct) }}%
            </div>
          </div>
        </div>

        <!-- SOX (Philadelphia Semi Index) -->
        <div
          v-if="signal.sox"
          class="border-2 px-4 sm:px-5 py-4 flex items-center justify-between gap-3 min-w-0"
          :class="soxLabel?.cls || 'bg-slate-100 text-slate-500'"
        >
          <div>
            <div class="text-xs uppercase tracking-wider opacity-70">費城半導體指數 (SOX)</div>
            <div class="text-2xl font-bold mt-0.5">{{ soxLabel?.text || '—' }}</div>
            <div class="text-sm mt-1 opacity-80 font-mono">
              {{ fmt(signal.sox.close, 2) }} <span class="text-xs opacity-70">({{ signal.sox.close_date }})</span>
            </div>
          </div>
          <div class="text-right min-w-0">
            <div class="text-xs opacity-70">當日漲跌</div>
            <div :class="changeClass(signal.sox.change_pct)" class="text-2xl font-bold">
              {{ signal.sox.change_pct >= 0 ? '+' : '' }}{{ fmt(signal.sox.change_pct) }}%
            </div>
            <div class="text-[11px] opacity-70 mt-0.5 font-mono">
              {{ signal.sox.change >= 0 ? '+' : '' }}{{ fmt(signal.sox.change) }}
            </div>
          </div>
        </div>
        <div v-else class="bg-slate-50 border border-slate-200 px-5 py-4 text-sm text-slate-500">
          SOX 資料尚未抓取，請等下次 fetch_us.py 執行。
        </div>
      </section>

      <!-- (3 個別 ADR 卡片已合併進下方預測卡，避免 raw 與 cleaned 兩套資訊) -->

      <!-- History sparklines -->
      <section v-if="history.length >= 2" class="grid grid-cols-1 md:grid-cols-2 gap-3 mb-6">
        <div class="bg-white border border-[#e7e7e1] p-4">
          <div class="flex items-baseline justify-between mb-2">
            <h2 class="text-sm font-semibold">近 {{ history.length }} 日 ADR 平均溢價</h2>
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
          <div v-if="premiumRange" class="text-[10px] text-slate-400 font-mono mt-0.5 text-right">
            min {{ premiumRange.min >= 0 ? '+' : '' }}{{ fmt(premiumRange.min) }}% ·
            max {{ premiumRange.max >= 0 ? '+' : '' }}{{ fmt(premiumRange.max) }}%
          </div>
        </div>

        <div v-if="soxVals.length >= 2" class="bg-white border border-[#e7e7e1] p-4">
          <div class="flex items-baseline justify-between mb-2">
            <h2 class="text-sm font-semibold">近 {{ soxVals.length }} 日 SOX 漲跌</h2>
            <span class="text-xs text-slate-500">
              最新 {{ history[history.length - 1]?.sox_change_pct >= 0 ? '+' : '' }}{{ fmt(history[history.length - 1]?.sox_change_pct) }}%
            </span>
          </div>
          <svg :viewBox="`0 0 ${SPARK_W} ${SPARK_H}`" preserveAspectRatio="none" class="w-full h-16">
            <line
              v-if="soxSparkZero != null"
              :x1="SPARK_PAD" :x2="SPARK_W - SPARK_PAD"
              :y1="soxSparkZero" :y2="soxSparkZero"
              stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="3 3"
            />
            <path :d="soxSparkPath" stroke="#1e6f9f" stroke-width="1.6" fill="none" stroke-linejoin="round" stroke-linecap="round" />
          </svg>
          <div class="flex justify-between text-[10px] text-slate-400 font-mono mt-1">
            <span>起點</span>
            <span>0%</span>
            <span>最新</span>
          </div>
          <div v-if="soxRange" class="text-[10px] text-slate-400 font-mono mt-0.5 text-right">
            min {{ soxRange.min >= 0 ? '+' : '' }}{{ fmt(soxRange.min) }}% ·
            max {{ soxRange.max >= 0 ? '+' : '' }}{{ fmt(soxRange.max) }}%
          </div>
        </div>
        <div v-else class="bg-slate-50 border border-slate-200 p-4 text-xs text-slate-500">
          SOX 歷史資料需累積至少 2 個交易日。
        </div>
      </section>
      <section v-else class="bg-slate-50 border border-slate-200 p-3 mb-6 text-xs text-slate-500">
        歷史走勢需累積至少 2 個交易日（每日由 cron 自動寫入 <code>adr_history.json</code>）。
      </section>

      <!-- Phase 1: Ridge + Conformal model — predict next-day open / high / low -->
      <section v-if="prediction" class="mb-6">
        <div class="flex items-baseline justify-between mb-3 flex-wrap gap-2">
          <h2 class="text-lg font-bold tracking-tight">明日開盤 / 高 / 低 預測</h2>
          <span class="text-xs text-slate-500">{{ prediction.method }} · 回看 {{ prediction.lookback_days }} 天 · {{ prediction.updated?.slice(0,10) }} 更新</span>
        </div>
        <p class="text-xs text-slate-500 mb-4 leading-relaxed">
          訊號乾淨化：<strong>個股 α</strong>（ADR USD 漲跌剝掉 FX 與 SOX β，留下純個股動能）+ <strong>SOX</strong> 漲跌 + <strong>溢價 z-score</strong>（去掉 60 日結構性偏移）→ Ridge 回歸 → 80% Conformal 區間。
          底部展開可看過去 30 個交易日 walk-forward 逐日驗證（每日重新訓練、預測、跟實際比對）。
        </p>

        <div
          v-for="(stock, code) in prediction.stocks"
          :key="code"
          :id="`detail-${code}`"
          class="bg-white border border-[#e7e7e1] mb-4 scroll-mt-16"
        >
          <!-- Header -->
          <div class="px-4 py-3 border-b border-[#e7e7e1] bg-slate-50 flex items-baseline justify-between flex-wrap gap-x-3 gap-y-1">
            <div class="min-w-0">
              <span class="font-bold text-base">{{ stock.name }}</span>
              <span class="text-xs text-slate-500 ml-2 font-mono">{{ code }} · ADR {{ stock.adr }}</span>
            </div>
            <div class="text-xs text-slate-500 font-mono w-full sm:w-auto sm:text-right">
              TW 收盤 <strong class="text-slate-800">{{ fmt(stock.tw_close) }}</strong>
              <span class="text-slate-300">·</span> ADR ${{ fmt(stock.adr_close) }}
              <span class="text-slate-300">→</span> 隱含 {{ fmt(stock.implied_tw_price) }}
            </div>
          </div>

          <!-- Warnings -->
          <div v-if="stock.signals_cleaned.is_event_day || stock.signals_cleaned.hnhpf_stale || stock.signals_cleaned.is_ex_div"
               class="px-4 py-2 bg-amber-50 border-b border-amber-200 text-xs text-amber-800 leading-relaxed">
            <span v-if="stock.signals_cleaned.is_event_day">⚠ 事件日 — 預測可信度低</span>
            <span v-if="stock.signals_cleaned.is_ex_div" class="ml-2">⚠ 今日除息</span>
            <span v-if="stock.signals_cleaned.hnhpf_stale" class="ml-2">⚠ HNHPF 報價停滯（成交量過低或與前日相同），鴻海預測僅供參考</span>
          </div>

          <!-- Today's raw signals (DiffBars + premium chip) — merged from the
               old standalone "3 個別 ADR 卡片" section to avoid duplicated info. -->
          <div v-if="rawByCode[code]" class="px-4 pt-3 pb-2 border-b border-[#e7e7e1]">
            <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">今日 raw 訊號</div>
            <div class="flex items-baseline justify-end gap-2 text-xs mb-1">
              <span class="text-slate-500">ADR 溢價</span>
              <span :class="premiumClass(rawByCode[code].premium_pct)" class="font-mono font-semibold">
                {{ rawByCode[code].premium_pct >= 0 ? '+' : '' }}{{ fmt(rawByCode[code].premium_pct) }}%
              </span>
            </div>
            <DiffBars
              :tw-change-pct="rawByCode[code].tw_change_pct"
              :adr-change-pct="rawByCode[code].adr_change_pct"
              :tw-date="rawByCode[code].tw_close_date"
              :adr-date="rawByCode[code].adr_close_date"
              :show-diff-signal="false"
            />
          </div>

          <!-- Cleaned signals — ordered by typical Ridge weight: SOX > 溢價 z > 個股 α > FX -->
          <div class="px-4 pt-3 pb-2">
            <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">訊號分解 (cleaned)</div>
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
              <div>
                <div class="text-slate-400">SOX</div>
                <div class="font-mono" :class="changeClass(stock.signals_cleaned.sox_chg_pct)">
                  {{ pctSign(stock.signals_cleaned.sox_chg_pct) }}
                </div>
                <div class="text-[10px] text-slate-400">&nbsp;</div>
              </div>
              <div>
                <div class="text-slate-400">溢價 z-score</div>
                <div class="font-mono" :class="stock.signals_cleaned.premium_z >= 0 ? 'text-red-500' : 'text-emerald-600'">
                  {{ stock.signals_cleaned.premium_z >= 0 ? '+' : '' }}{{ fmt(stock.signals_cleaned.premium_z, 2) }}σ
                </div>
                <div class="text-[10px] text-slate-400">raw {{ pctSign(stock.signals_cleaned.premium_raw_pct) }}</div>
              </div>
              <div>
                <div class="text-slate-400">個股 α</div>
                <div class="font-mono" :class="changeClass(stock.signals_cleaned.adr_alpha_pct)">
                  {{ pctSign(stock.signals_cleaned.adr_alpha_pct) }}
                </div>
                <div class="text-[10px] text-slate-400">ADR 剝 FX + SOX β · β = {{ fmt(stock.signals_cleaned.sox_beta, 2) }}</div>
              </div>
              <div>
                <div class="text-slate-400">USD/TWD</div>
                <div class="font-mono" :class="changeClass(stock.signals_cleaned.fx_chg_pct)">
                  {{ pctSign(stock.signals_cleaned.fx_chg_pct) }}
                </div>
                <div class="text-[10px] text-slate-400">&nbsp;</div>
              </div>
            </div>
          </div>

          <!-- Predictions table -->
          <div class="px-4 pt-3 pb-4">
            <div class="text-xs uppercase tracking-wider text-slate-500 mb-1">明日預測 (Ridge + Conformal 80%)</div>
            <div class="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
            <table class="w-full min-w-[420px] text-sm border border-[#e7e7e1]">
              <thead>
                <tr class="bg-slate-50 text-slate-600 text-xs">
                  <th class="px-3 py-1.5 text-left">目標</th>
                  <th class="px-3 py-1.5 text-right">點估</th>
                  <th class="px-3 py-1.5 text-right">80% 區間 (%)</th>
                  <th class="px-3 py-1.5 text-right">區間價格</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="stock.predictions.open_gap" class="border-t border-[#e7e7e1] bg-amber-50/40">
                  <td class="px-3 py-2"><strong>開盤</strong></td>
                  <td class="px-3 py-2 text-right font-mono font-bold text-base"
                      :class="pctClassPrediction(stock.predictions.open_gap.point_pct)">
                    {{ pctSign(stock.predictions.open_gap.point_pct) }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-xs text-slate-500">
                    [{{ pctSign(stock.predictions.open_gap.lo80_pct) }},
                    {{ pctSign(stock.predictions.open_gap.hi80_pct) }}]
                    <span v-if="stock.predictions.open_gap.crosses_zero" class="ml-1 text-amber-600 whitespace-nowrap">⚠ 跨零</span>
                  </td>
                  <td class="px-3 py-2 text-right font-mono">
                    {{ fmt(stock.predictions.open_gap.lo80_price, 0) }} ~ <strong>{{ fmt(stock.predictions.open_gap.hi80_price, 0) }}</strong>
                  </td>
                </tr>
                <tr v-if="stock.predictions.max_gain" class="border-t border-[#e7e7e1]">
                  <td class="px-3 py-2">盤中最高</td>
                  <td class="px-3 py-2 text-right font-mono font-semibold"
                      :class="pctClassPrediction(stock.predictions.max_gain.point_pct)">
                    {{ pctSign(stock.predictions.max_gain.point_pct) }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-xs text-slate-500">
                    [{{ pctSign(stock.predictions.max_gain.lo80_pct) }},
                    {{ pctSign(stock.predictions.max_gain.hi80_pct) }}]
                  </td>
                  <td class="px-3 py-2 text-right font-mono">
                    {{ fmt(stock.predictions.max_gain.lo80_price, 0) }} ~ <strong>{{ fmt(stock.predictions.max_gain.hi80_price, 0) }}</strong>
                  </td>
                </tr>
                <tr v-if="stock.predictions.max_loss" class="border-t border-[#e7e7e1]">
                  <td class="px-3 py-2">盤中最低</td>
                  <td class="px-3 py-2 text-right font-mono font-semibold"
                      :class="pctClassPrediction(stock.predictions.max_loss.point_pct)">
                    {{ pctSign(stock.predictions.max_loss.point_pct) }}
                  </td>
                  <td class="px-3 py-2 text-right font-mono text-xs text-slate-500">
                    [{{ pctSign(stock.predictions.max_loss.lo80_pct) }},
                    {{ pctSign(stock.predictions.max_loss.hi80_pct) }}]
                  </td>
                  <td class="px-3 py-2 text-right font-mono">
                    <strong>{{ fmt(stock.predictions.max_loss.lo80_price, 0) }}</strong> ~ {{ fmt(stock.predictions.max_loss.hi80_price, 0) }}
                  </td>
                </tr>
              </tbody>
            </table>
            </div><!-- /overflow-x-auto -->
            <div v-if="stock.consistency_violated" class="mt-1 text-[11px] text-amber-700">
              預測高/低/開三條由獨立模型產出，曾有極小重疊已自動修正
            </div>
          </div>

          <!-- Walk-forward 30-day summary -->
          <div class="px-4 pt-2 pb-3 border-t border-[#e7e7e1]" v-if="stock.walk_forward_30d?.open_gap?.summary">
            <div class="flex items-baseline justify-between flex-wrap gap-2 mb-1">
              <div class="text-xs uppercase tracking-wider text-slate-500">過去 30 天每日預測 vs 實際</div>
              <button @click="toggleWalkForward(code)"
                      class="text-xs text-slate-500 hover:text-slate-900 underline">
                {{ expandedWalkForward[code] ? '收起逐日明細 ▴' : '展開逐日明細 ▾' }}
              </button>
            </div>
            <div class="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
            <table class="w-full min-w-[520px] text-xs border border-[#e7e7e1]">
              <thead>
                <tr class="bg-slate-50 text-slate-600">
                  <th class="px-2 py-1 text-left">目標</th>
                  <th class="px-2 py-1 text-right">N</th>
                  <th class="px-2 py-1 text-right">MAE</th>
                  <th class="px-2 py-1 text-right">RMSE</th>
                  <th class="px-2 py-1 text-right">偏差</th>
                  <th class="px-2 py-1 text-right">區間寬</th>
                  <th class="px-2 py-1 text-right">coverage</th>
                  <th class="px-2 py-1 text-right">命中率</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="tgt in ['open_gap', 'max_gain', 'max_loss']"
                    :key="tgt"
                    v-show="stock.walk_forward_30d[tgt]?.summary"
                    class="border-t border-[#e7e7e1]">
                  <td class="px-2 py-1">
                    {{ tgt === 'open_gap' ? '開盤' : (tgt === 'max_gain' ? '盤中最高' : '盤中最低') }}
                  </td>
                  <td class="px-2 py-1 text-right font-mono">{{ stock.walk_forward_30d[tgt].summary.n }}</td>
                  <td class="px-2 py-1 text-right font-mono">{{ stock.walk_forward_30d[tgt].summary.mae_pct }}%</td>
                  <td class="px-2 py-1 text-right font-mono">{{ stock.walk_forward_30d[tgt].summary.rmse_pct }}%</td>
                  <td class="px-2 py-1 text-right font-mono"
                      :class="stock.walk_forward_30d[tgt].summary.bias_pct > 0 ? 'text-red-500' : 'text-emerald-600'">
                    {{ pctSign(stock.walk_forward_30d[tgt].summary.bias_pct) }}
                  </td>
                  <td class="px-2 py-1 text-right font-mono">{{ stock.walk_forward_30d[tgt].summary.avg_interval_width_pct }}%</td>
                  <td class="px-2 py-1 text-right font-mono"
                      :class="stock.walk_forward_30d[tgt].summary.coverage_pct >= 75 ? 'text-emerald-600' : 'text-amber-600'">
                    {{ stock.walk_forward_30d[tgt].summary.coverage_pct }}%
                  </td>
                  <td class="px-2 py-1 text-right font-mono"
                      :class="stock.walk_forward_30d[tgt].summary.hit_rate_pct >= 70 ? 'text-emerald-600 font-semibold' : 'text-slate-600'">
                    {{ stock.walk_forward_30d[tgt].summary.hit_rate_pct }}%
                  </td>
                </tr>
              </tbody>
            </table>
            </div><!-- /overflow-x-auto -->
            <div class="text-[10px] text-slate-400 mt-1 leading-relaxed">
              命中率基準：擲銅板 50%。Coverage 目標 80%（finite-sample 保證）。
            </div>

            <!-- Per-day expansion (open_gap only) -->
            <div v-if="expandedWalkForward[code] && stock.walk_forward_30d.open_gap?.daily?.length"
                 class="mt-3">
              <div class="text-[11px] text-slate-500 mb-1">開盤預測 vs 實際（逐日）</div>
              <div class="overflow-x-auto -mx-4 px-4 sm:mx-0 sm:px-0">
                <table class="w-full min-w-[480px] text-xs border border-[#e7e7e1] font-mono">
                  <thead>
                    <tr class="bg-slate-50 text-slate-600">
                      <th class="px-2 py-1 text-left">日期</th>
                      <th class="px-2 py-1 text-right">預測</th>
                      <th class="px-2 py-1 text-right">實際</th>
                      <th class="px-2 py-1 text-right">誤差</th>
                      <th class="px-2 py-1 text-right">80% 區間</th>
                      <th class="px-2 py-1 text-center">方向</th>
                      <th class="px-2 py-1 text-center">in?</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="d in stock.walk_forward_30d.open_gap.daily"
                        :key="d.date"
                        class="border-t border-[#e7e7e1]">
                      <td class="px-2 py-0.5">{{ d.date }}</td>
                      <td class="px-2 py-0.5 text-right" :class="d.predicted_pct >= 0 ? 'text-red-500' : 'text-emerald-600'">
                        {{ pctSign(d.predicted_pct) }}
                      </td>
                      <td class="px-2 py-0.5 text-right" :class="d.actual_pct >= 0 ? 'text-red-500' : 'text-emerald-600'">
                        {{ pctSign(d.actual_pct) }}
                      </td>
                      <td class="px-2 py-0.5 text-right text-slate-500">
                        {{ pctSign(d.error_pct) }}
                      </td>
                      <td class="px-2 py-0.5 text-right text-slate-500">
                        [{{ pctSign(d.lo80_pct) }}, {{ pctSign(d.hi80_pct) }}]
                      </td>
                      <td class="px-2 py-0.5 text-center" :class="d.hit_direction ? 'text-emerald-600' : 'text-rose-500'">
                        {{ d.hit_direction ? '✓' : '✗' }}
                      </td>
                      <td class="px-2 py-0.5 text-center" :class="d.in_interval ? 'text-emerald-600' : 'text-rose-500'">
                        {{ d.in_interval ? '✓' : '✗' }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- Coefficients (collapsed under expansion only) -->
          <div v-if="expandedWalkForward[code] && stock.model_quality?.open_gap"
               class="px-4 pb-3 text-[11px] text-slate-500 leading-relaxed">
            <div class="mt-3"><strong>Ridge 標準化權重 (open_gap)</strong>:
              個股 α {{ stock.model_quality.open_gap.coef.adr_alpha }} ·
              SOX {{ stock.model_quality.open_gap.coef.sox_chg }} ·
              Premium z {{ stock.model_quality.open_gap.coef.premium_z }} ·
              intercept {{ stock.model_quality.open_gap.intercept }}
              · 訓練集 N = {{ stock.model_quality.open_gap.n_train }}
            </div>
          </div>
        </div>

        <p class="text-[11px] text-slate-500 leading-relaxed bg-slate-50 p-3 border border-slate-200">
          <strong>讀法</strong>：
          區間是 80% conformal — 過去 30 天實測，coverage 應接近 80%。
          <strong>命中率</strong>：預測方向（漲/跌）跟實際相符的比率（隨機是 50%）。
          盤中最高 / 最低 RMSE 通常較大（極值有 long tail），當作「<strong>合理範圍</strong>」而非精確 target。
          事件日（除息、漲跌停、長假後、HNHPF 停滯）會自動標警告，預測可信度降低。
        </p>
      </section>

      <!-- Methodology footer -->
      <div class="text-xs text-slate-500 leading-relaxed bg-slate-50 p-3 border border-slate-200">
        <p class="mb-1"><strong>計算邏輯</strong></p>
        <p>每檔 ADR 的隱含台股價 = ADR 收盤 × USD/TWD ÷ ratio；溢價 = (隱含價 − 台股收盤) ÷ 台股收盤。</p>
        <p class="mt-1">頂部 ADR 平均訊號 / SOX 標籤是 raw 速覽。下方「明日預測」用 Ridge + Conformal 把個股 α（剝 FX 與 SOX β 的 ADR 殘差）+ SOX + 溢價 z 合成單一預測，每天 06:00 cron 重新訓練、重新預測。</p>
        <p class="mt-1 text-slate-400">
          USD/TWD = {{ fmt(signal.fx_rate, 3) }}（{{ signal.fx_date }}）· 訊號更新 {{ signal.updated?.replace(/:\d{2}\+\d{2}:\d{2}$/, '') }}
        </p>
      </div>
    </div>
  </div>
</template>
