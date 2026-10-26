<script setup>
import { ref, onMounted, watch, computed, inject } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useWatchlistStore } from '../stores/watchlist'
import { useAlertsStore } from '../stores/alerts'
import { useSettingsStore } from '../stores/settings'
import { generateSummary, loadCachedSummary, clearCachedSummary } from '../lib/summarize.js'
import BandChart from '../components/BandChart.vue'
import CandleChart from '../components/CandleChart.vue'
import ChipsChart from '../components/ChipsChart.vue'
import DiffBars from '../components/DiffBars.vue'
import ValuationScale from '../components/ValuationScale.vue'
import { computeFreshness, TW_SCHEDULE } from '../lib/freshness.js'
import { fetchData } from '../lib/data.js'
import { valuationView, distancePct, METHOD_LABEL } from '../lib/position.js'

const settingsStore = useSettingsStore()
const summaryState = ref(null)      // {text, generated_at, provider, model, fingerprint} | null
const summaryLoading = ref(false)
const summaryError = ref('')

const route = useRoute()
const watchlist = useWatchlistStore()
const alerts = useAlertsStore()
const alertInput = ref('')
const rawData = ref(null)
const stocksMeta = ref(null)
const adrPrediction = ref(null)   // headline-stock prediction from data/adr_prediction.json
const liveName = ref(null)        // name from data/names.json for non-preloaded codes
const loading = ref(true)
const loadingMessage = ref('載入中…')
const error = ref(null)

const lastUpdated = inject('lastUpdated', ref({}))
// Day-scale thresholds (weekend-safe). The cron silently died for ~30 days once;
// the per-stock page must show staleness, not present month-old data as current.
const freshness = computed(() =>
  computeFreshness(lastUpdated.value.tw, { schedule: TW_SCHEDULE, staleNote: '資料可能過期' })
)

const code = computed(() => route.params.code)
const meta = computed(() => stocksMeta.value?.tw_stocks?.[code.value])
const isDynamic = computed(() => rawData.value?._dynamic === true)

// Price alert (fires when latest close ≤ target — the "等便宜了買" case).
const alertTarget = computed(() => alerts.get(code.value))
const alertOpen = ref(false)
function setAlert(price = alertInput.value) {
  alerts.set(code.value, price)
  alertInput.value = ''
  alertOpen.value = false
}

// === User customization settings (per-stock localStorage) ===
const defaultSettings = {
  dividend_mode: 'latest', // 'latest' | 'avg2y' | 'avg3y' | 'avg5y' | 'custom'
  custom_dividend: null,
  eps_mode: 'ttm', // 'ttm' | 'custom'
  custom_eps: null,
  margin_of_safety: 0, // 0..50 percent
}

const settings = ref({ ...defaultSettings })

function loadSettings(c) {
  if (!c) return
  try {
    const raw = localStorage.getItem(`triprice.settings.${c}`)
    if (raw) {
      Object.assign(settings.value, defaultSettings, JSON.parse(raw))
    } else {
      Object.assign(settings.value, defaultSettings)
    }
  } catch {
    Object.assign(settings.value, defaultSettings)
  }
}

watch(
  settings,
  (val) => {
    if (!code.value) return
    try {
      localStorage.setItem(`triprice.settings.${code.value}`, JSON.stringify(val))
    } catch {}
  },
  { deep: true },
)

function resetSettings() {
  Object.assign(settings.value, defaultSettings)
}

// === Computed values applying user settings ===
const dividendAvgs = computed(() => {
  const hist = rawData.value?.dividend_history || []
  const result = {}
  for (const n of [2, 3, 5]) {
    if (hist.length >= n) {
      const sum = hist.slice(0, n).reduce((s, d) => s + (d.cash_dividend || 0), 0)
      result[n] = Number((sum / n).toFixed(2))
    }
  }
  return result
})

const effectiveDividend = computed(() => {
  if (!rawData.value) return null
  if (settings.value.dividend_mode === 'custom' && settings.value.custom_dividend != null) {
    const v = Number(settings.value.custom_dividend)
    return isNaN(v) ? rawData.value.dividend_used : v
  }
  if (settings.value.dividend_mode.startsWith('avg')) {
    const n = parseInt(settings.value.dividend_mode.slice(3), 10)
    if (dividendAvgs.value[n] != null) return dividendAvgs.value[n]
  }
  return rawData.value.dividend_used || 0
})

const effectiveEps = computed(() => {
  if (settings.value.eps_mode === 'custom' && settings.value.custom_eps != null) {
    const v = Number(settings.value.custom_eps)
    return isNaN(v) ? rawData.value?.eps_ttm : v
  }
  return rawData.value?.eps_ttm
})

function round2(n) {
  return Number(Number(n).toFixed(2))
}

const computedValuations = computed(() => {
  if (!rawData.value) return { yieldVal: null, peVal: null }
  const div = effectiveDividend.value
  const eps = effectiveEps.value
  const ys = rawData.value.yield_stats
  const ps = rawData.value.pe_stats
  const factor = 1 - (settings.value.margin_of_safety || 0) / 100

  let yieldVal = null
  if (ys && div && div > 0) {
    yieldVal = {
      cheap: round2((div / ys.high) * factor),
      fair: round2((div / ys.avg) * factor),
      expensive: round2(div / ys.low),
    }
  }
  let peVal = null
  if (ps && eps && eps > 0) {
    peVal = {
      cheap: round2(eps * ps.low * factor),
      fair: round2(eps * ps.avg * factor),
      expensive: round2(eps * ps.high),
    }
  }
  return { yieldVal, peVal }
})

const hasCustomization = computed(() => {
  const s = settings.value
  return (
    s.dividend_mode !== 'latest' ||
    s.eps_mode !== 'ttm' ||
    s.margin_of_safety > 0
  )
})

// data is the rawData with user-setting overrides — template reads this
const data = computed(() => {
  if (!rawData.value) return null
  return {
    ...rawData.value,
    dividend_used: effectiveDividend.value,
    eps_ttm: effectiveEps.value,
    valuation_yield: computedValuations.value.yieldVal || rawData.value.valuation_yield,
    valuation_pe: computedValuations.value.peVal || rawData.value.valuation_pe,
  }
})

async function load() {
  loading.value = true
  loadingMessage.value = '載入中…'
  error.value = null
  method.value = null
  alertOpen.value = false
  liveName.value = null
  rawData.value = null
  adrPrediction.value = null
  summaryState.value = null
  summaryError.value = ''
  loadSettings(code.value)
  try {
    const [meta, stock, pred] = await Promise.all([
      fetchData('stocks.json'),
      fetchData(`tw/${code.value}.json`, { optional: true }),
      fetchData('adr_prediction.json', { optional: true }),
    ])
    stocksMeta.value = meta
    adrPrediction.value = pred?.stocks?.[code.value] || null
    if (!meta?.tw_stocks?.[code.value]) {
      fetchData('names.json', { optional: true }).then((n) => { liveName.value = n?.names?.[code.value] || null })
    }
    if (stock) {
      rawData.value = stock
    } else {
      loadingMessage.value = '此股票未預載，從 FinMind 即時抓取（約 5 秒）…'
      try {
        const { fetchStockDynamic } = await import('../lib/finmind.js')
        rawData.value = await fetchStockDynamic(code.value)
      } catch (e) {
        error.value = `動態抓取失敗：${e.message}`
      }
    }
    // Pull cached summary, if any (server-side `data.summary` takes precedence
    // when present, but for new architecture we rely on the local cache).
    const cached = loadCachedSummary(code.value)
    if (cached) summaryState.value = cached
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

async function handleGenerateSummary(force = false) {
  if (!rawData.value) return
  if (!settingsStore.hasActiveApiKey) {
    summaryError.value = `請先到「設定」填入 ${settingsStore.llmProvider} 的 API key`
    return
  }
  summaryLoading.value = true
  summaryError.value = ''
  try {
    const result = await generateSummary({
      data: rawData.value,
      provider: settingsStore.llmProvider,
      apiKey: settingsStore.activeApiKey(),
      model: settingsStore.effectiveModel,
      force,
    })
    summaryState.value = result
  } catch (e) {
    summaryError.value = e.message || String(e)
  } finally {
    summaryLoading.value = false
  }
}

function handleClearSummary() {
  clearCachedSummary(code.value)
  summaryState.value = null
  summaryError.value = ''
}

onMounted(load)
watch(code, load)

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  })
}

// === Verdict: one method drives the headline (same rule as the overview table:
// PE when there is EPS, else yield); the user can flip to the other method.
const method = ref(null) // null = default (primary) | 'pe' | 'yield'
const view = computed(() => (data.value ? valuationView(data.value) : null))
const selected = computed(() => {
  const v = view.value
  if (!v) return null
  if (method.value === 'pe' && v.pe) return v.pe
  if (method.value === 'yield' && v.yld) return v.yld
  return v.primary
})
const other = computed(() => {
  const v = view.value
  if (!v || !selected.value) return null
  return selected.value.method === 'pe' ? v.yld : v.pe
})

const BAND_ROWS = [
  { k: 'cheap', l: '便宜價', c: 'text-emerald-600' },
  { k: 'fair', l: '合理價', c: 'text-[#0a0e16]' },
  { k: 'expensive', l: '昂貴價', c: 'text-red-500' },
]

function pctAbs(n) {
  return Math.abs(n).toFixed(1) + '%'
}
const verdictSentence = computed(() => {
  const sel = selected.value
  const price = data.value?.current_price
  if (!sel || !price) return ''
  const { cheap, fair, expensive } = sel.bands
  const parts = []
  parts.push(price > fair
    ? `比合理價 ${fmt(fair)} 高 ${pctAbs(((price - fair) / fair) * 100)}`
    : `要漲 ${pctAbs(distancePct(price, fair))} 才回到合理價 ${fmt(fair)}`)
  if (price > expensive) parts.push(`已高於昂貴價 ${fmt(expensive)}`)
  else if (price > cheap) parts.push(`再跌 ${pctAbs(distancePct(price, cheap))} 才到便宜價 ${fmt(cheap)}`)
  else parts.push(`已低於便宜價 ${fmt(cheap)}`)
  return `現價 ${fmt(price)}，${parts.join('；')}。`
})

const dividendLabel = computed(() => {
  const m = settings.value.dividend_mode
  if (m === 'latest') return '使用最近一年股利'
  if (m === 'custom') return '使用自訂股利'
  if (m.startsWith('avg')) return `使用近 ${m.slice(3)} 年平均股利`
  return '使用最近一年股利'
})

const epsLabel = computed(() =>
  settings.value.eps_mode === 'custom' ? '使用自訂 EPS' : '使用近 4 季 EPS 合計',
)
</script>

<template>
  <div>
    <RouterLink to="/" class="text-[11px] text-slate-500 hover:text-[#0a0e16] uppercase tracking-widest font-mono">← 總覽</RouterLink>

    <div v-if="loading" class="py-8">
      <div class="skel h-7 w-48 mb-3"></div>
      <div class="skel h-12 w-32 mb-2"></div>
      <div class="skel h-4 w-64 mb-6"></div>
      <div class="skel h-40 w-full"></div>
      <p v-if="loadingMessage !== '載入中…'" class="mt-4 text-sm text-slate-500">{{ loadingMessage }}</p>
    </div>
    <div v-else-if="error && !data" class="py-8">
      <p class="text-slate-700">{{ error }}</p>
      <p class="text-sm text-slate-500 mt-2">請確認代號正確（4-6 碼數字 / 字母），或稍後重試。</p>
    </div>
    <div v-else-if="data">
      <!-- Header: identity + price on the left, actions on the right -->
      <div class="flex items-start justify-between mt-3 mb-4 gap-3 flex-wrap">
        <div class="min-w-0">
          <div class="flex items-baseline gap-2 mb-1">
            <span class="font-mono text-[11px] text-slate-500 uppercase tracking-widest">{{ code }}</span>
            <span v-if="meta?.adr" class="font-mono text-[10px] text-slate-400">ADR {{ meta.adr }}</span>
            <span v-if="isDynamic" class="text-[10px] px-1.5 py-0.5 bg-amber-100 text-amber-700 font-mono uppercase tracking-wider">live</span>
          </div>
          <h1 class="text-2xl font-bold tracking-tight leading-tight">{{ meta?.name || liveName || (rawData?.name !== code ? rawData?.name : null) || code }}</h1>
          <div class="mt-2 flex items-baseline gap-3 flex-wrap">
            <span class="text-4xl font-bold tabular-nums tracking-tight">{{ fmt(rawData.current_price) }}</span>
            <span
              v-if="rawData.change != null"
              :class="rawData.change >= 0 ? 'text-red-600' : 'text-emerald-700'"
              class="text-base font-semibold tabular-nums"
            >
              {{ rawData.change >= 0 ? '+' : '' }}{{ fmt(rawData.change) }}
              <span class="text-sm font-medium opacity-90">
                ({{ rawData.change >= 0 ? '+' : '' }}{{ fmt(rawData.change_pct, 2) }}%)
              </span>
            </span>
          </div>
          <div class="mt-1 flex items-center gap-2 flex-wrap text-[11px] text-slate-500 font-mono">
            <span>收盤 {{ rawData.close_date }}</span>
            <span v-if="freshness" class="px-1.5 py-px rounded border font-sans font-medium" :class="freshness.cls">資料 {{ freshness.label }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <button
            @click="watchlist.toggle(code)"
            class="h-9 px-3 border text-xs tracking-wider transition font-semibold"
            :class="
              watchlist.has(code)
                ? 'bg-amber-100 border-amber-500 text-amber-800'
                : 'bg-white border-[#0a0e16] text-[#0a0e16] hover:bg-[#0a0e16] hover:text-white'
            "
          >{{ watchlist.has(code) ? '★ 自選中' : '☆ 加入自選' }}</button>
          <button
            v-if="alertTarget == null"
            @click="alertOpen = !alertOpen"
            class="h-9 px-3 border text-xs tracking-wider transition font-semibold bg-white text-slate-700 hover:border-[#0a0e16]"
            :class="alertOpen ? 'border-[#0a0e16]' : 'border-[#d8d8d2]'"
          >🔔 到價提醒</button>
          <span v-else class="h-9 pl-3 pr-1 border border-amber-300 bg-amber-50 text-amber-800 text-xs font-semibold inline-flex items-center gap-1.5">
            🔔 跌破 {{ fmt(alertTarget) }}
            <span v-if="rawData.current_price != null && rawData.current_price <= alertTarget" class="text-emerald-600">✓ 已到價</span>
            <button @click="alerts.remove(code)" class="w-6 h-6 text-amber-700/60 hover:text-red-500" aria-label="清除提醒">✕</button>
          </span>
        </div>
      </div>

      <!-- Alert editor: one-tap presets at the valuation prices -->
      <div v-if="alertOpen && alertTarget == null" class="mb-4 px-3 py-2.5 bg-white border border-[#e7e7e1] flex items-center flex-wrap gap-2 text-sm">
        <span class="text-xs text-slate-500">收盤跌破</span>
        <input
          v-model="alertInput"
          type="number" inputmode="decimal" step="0.01"
          placeholder="目標價"
          class="w-24 px-2 py-1 rounded border border-[#d8d8d2] text-sm focus:outline-none focus:border-[#0a0e16]"
          @keyup.enter="setAlert()"
        />
        <button
          @click="setAlert()"
          :disabled="!alertInput"
          class="text-xs px-2.5 py-1 rounded border border-[#0a0e16] text-[#0a0e16] hover:bg-[#0a0e16] hover:text-white transition disabled:opacity-40"
        >設定</button>
        <template v-if="selected">
          <span class="text-xs text-slate-400 ml-1">或直接用</span>
          <button @click="setAlert(selected.bands.cheap)" class="text-xs px-2 py-1 rounded border border-emerald-200 bg-emerald-50 text-emerald-700 hover:border-emerald-500">便宜價 {{ fmt(selected.bands.cheap) }}</button>
          <button @click="setAlert(selected.bands.fair)" class="text-xs px-2 py-1 rounded border border-[#d8d8d2] text-slate-700 hover:border-[#0a0e16]">合理價 {{ fmt(selected.bands.fair) }}</button>
        </template>
        <span class="basis-full text-[11px] text-slate-400">純前端提醒：下次打開 Triprice 時在總覽頁頂端顯示（不會推播）。</span>
      </div>

      <!-- Verdict: the answer first -->
      <section class="mb-5 bg-white border border-[#e7e7e1]">
        <div class="flex items-center justify-between gap-3 px-4 pt-3">
          <h2 class="text-[11px] uppercase tracking-[0.16em] text-slate-500 font-semibold">估值判讀</h2>
          <div v-if="view?.pe && view?.yld" class="inline-flex border border-[#d8d8d2] rounded overflow-hidden text-xs" role="tablist">
            <button
              v-for="m in ['pe', 'yield']"
              :key="m"
              role="tab"
              :aria-selected="selected?.method === m"
              class="px-2.5 py-1 transition"
              :class="selected?.method === m ? 'bg-[#0a0e16] text-white' : 'bg-white text-slate-600 hover:text-[#0a0e16]'"
              @click="method = m"
            >{{ METHOD_LABEL[m] }}</button>
          </div>
          <span v-else-if="selected" class="text-xs text-slate-500">{{ METHOD_LABEL[selected.method] }}</span>
        </div>

        <div v-if="selected && selected.pct != null" class="px-4 pb-4">
          <div class="flex items-baseline gap-3 mt-1 flex-wrap">
            <span class="text-3xl font-bold tracking-tight" :class="selected.tier.text">{{ selected.tier.label }}</span>
            <span class="font-mono text-sm text-slate-500">位置 {{ selected.pct }}%</span>
          </div>
          <p class="text-sm text-slate-600 mt-1 leading-relaxed">{{ verdictSentence }}</p>

          <div class="mt-2 px-1 sm:px-6">
            <ValuationScale :bands="selected.bands" :price="data.current_price" />
          </div>

          <div class="mt-1 space-y-1.5 text-xs leading-relaxed">
            <p v-if="other && other.pct != null" class="text-slate-600">
              另一種方法 · {{ METHOD_LABEL[other.method] }}：
              <strong :class="other.tier.text">{{ other.tier.label }} {{ other.pct }}%</strong>
              <button class="ml-1 text-[#b4530b] hover:text-[#0a0e16] underline" @click="method = other.method">切換查看</button>
            </p>
            <p v-if="view.divergent" class="px-2.5 py-1.5 bg-amber-50 border border-amber-200 text-slate-700">
              ⚠ 兩種方法的位置相差半個估值帶以上 — 通常代表近年獲利或配息變化很大（獲利暴增／衰退、配息政策改變、景氣循環），單看一種容易誤判，建議兩者一起參考。
            </p>
            <p v-if="selected.method === 'yield' && data.yield_stats && data.yield_stats.avg < 0.02" class="px-2.5 py-1.5 bg-amber-50 border border-amber-200 text-slate-700">
              ⚠ 殖利率中位數僅 {{ fmt(data.yield_stats.avg * 100, 2) }}%，屬成長股型態 — 殖利率法會嚴重低估合理價<template v-if="view.pe">，建議以 PE 法為主</template>。
            </p>
            <p v-if="data.split_detected" class="text-slate-500">
              ℹ 近 3 年曾分割／減資，歷史價格與股利已依分割比例還原後再計算。
            </p>
            <p v-if="settings.margin_of_safety > 0" class="text-amber-700">
              已套用安全邊際 {{ settings.margin_of_safety }}%（便宜價、合理價打折；昂貴價不變）。
            </p>
          </div>
        </div>
        <div v-else class="px-4 pb-4 pt-1 text-sm text-slate-500">
          這檔目前算不出估值帶：殖利率法需要配息紀錄，PE 法需要正的近 4 季 EPS。
        </div>
      </section>

      <!-- Valuation band chart for the selected method -->
      <section v-if="selected && data.price_history?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">估值帶走勢 <span class="text-sm font-normal text-slate-500">· {{ METHOD_LABEL[selected.method] }} · 近 3 年</span></h2>
        <div class="bg-white border border-[#e7e7e1] p-3">
          <BandChart
            :key="selected.method"
            :history="data.price_history"
            :bands="selected.bands"
            :current-price="data.current_price"
          />
        </div>
      </section>

      <!-- Both methods side by side + how they're computed -->
      <section class="mb-6">
        <h2 class="text-lg font-semibold mb-2">估值明細</h2>
        <div class="bg-white border border-[#e7e7e1] overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600 text-xs">
                <th class="px-4 py-2 text-left font-medium w-1/4"></th>
                <th class="px-4 py-2 text-right font-medium" :class="selected?.method === 'yield' ? 'text-[#0a0e16]' : ''">殖利率法</th>
                <th class="px-4 py-2 text-right font-medium" :class="selected?.method === 'pe' ? 'text-[#0a0e16]' : ''">PE 法</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in BAND_ROWS" :key="row.k" class="border-t border-slate-100">
                <td class="px-4 py-2.5 text-slate-600">{{ row.l }}</td>
                <td class="px-4 py-2.5 text-right font-bold tnum" :class="data.valuation_yield ? row.c : 'text-slate-300'">{{ fmt(data.valuation_yield?.[row.k]) }}</td>
                <td class="px-4 py-2.5 text-right font-bold tnum" :class="data.valuation_pe ? row.c : 'text-slate-300'">{{ fmt(data.valuation_pe?.[row.k]) }}</td>
              </tr>
              <tr class="border-t border-slate-100">
                <td class="px-4 py-2.5 text-slate-600">目前位置</td>
                <td class="px-4 py-2.5 text-right text-xs font-semibold" :class="view?.yld?.tier.text">{{ view?.yld?.pct != null ? view.yld.tier.label + ' ' + view.yld.pct + '%' : '—' }}</td>
                <td class="px-4 py-2.5 text-right text-xs font-semibold" :class="view?.pe?.tier.text">{{ view?.pe?.pct != null ? view.pe.tier.label + ' ' + view.pe.pct + '%' : '—' }}</td>
              </tr>
              <tr class="border-t border-slate-100 text-xs text-slate-500 align-top">
                <td class="px-4 py-2.5">計算依據</td>
                <td class="px-4 py-2.5 text-right leading-relaxed">
                  <template v-if="data.valuation_yield && data.yield_stats">
                    股利 {{ fmt(data.dividend_used) }} ÷ 殖利率<br />
                    {{ fmt(data.yield_stats.high * 100, 2) }}% / {{ fmt(data.yield_stats.avg * 100, 2) }}% / {{ fmt(data.yield_stats.low * 100, 2) }}%
                  </template>
                  <template v-else>無配息資料</template>
                </td>
                <td class="px-4 py-2.5 text-right leading-relaxed">
                  <template v-if="data.valuation_pe && data.pe_stats">
                    EPS {{ fmt(data.eps_ttm) }} × PE<br />
                    {{ fmt(data.pe_stats.low, 1) }} / {{ fmt(data.pe_stats.avg, 1) }} / {{ fmt(data.pe_stats.high, 1) }}
                  </template>
                  <template v-else>{{ rawData.eps_ttm == null ? '無 EPS（ETF 等）' : 'EPS ≤ 0，不適用' }}</template>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          {{ dividendLabel }} · {{ epsLabel }} · 殖利率 / PE 區間取自近 3 年每日資料的 5 / 50 / 95 百分位
          <span v-if="settings.margin_of_safety > 0" class="text-amber-600">· 安全邊際 {{ settings.margin_of_safety }}%</span>
        </p>
      </section>

      <!-- 進階設定 -->
      <details class="mb-6 -mt-3 group" :open="hasCustomization">
        <summary
          class="cursor-pointer text-sm font-medium text-[#b4530b] hover:text-[#0a0e16] inline-flex items-center gap-1.5 select-none list-none"
        >
          <span class="inline-block transition-transform group-open:rotate-90 text-xs">▶</span>
          進階設定
          <span
            v-if="hasCustomization"
            class="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-normal"
          >已自訂</span>
        </summary>

        <div class="mt-3 bg-white border border-[#e7e7e1] p-4 space-y-4">
          <!-- 股利取值 -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">股利取值</label>
            <select
              v-model="settings.dividend_mode"
              class="w-full px-3 py-1.5 border border-[#d8d8d2] bg-white text-sm focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] transition"
            >
              <option value="latest">最近一年（{{ fmt(rawData.dividend_used || 0) }}）</option>
              <option v-if="dividendAvgs[2]" value="avg2y">近 2 年平均（{{ fmt(dividendAvgs[2]) }}）</option>
              <option v-if="dividendAvgs[3]" value="avg3y">近 3 年平均（{{ fmt(dividendAvgs[3]) }}）</option>
              <option v-if="dividendAvgs[5]" value="avg5y">近 5 年平均（{{ fmt(dividendAvgs[5]) }}）</option>
              <option value="custom">自訂金額…</option>
            </select>
            <input
              v-if="settings.dividend_mode === 'custom'"
              v-model.number="settings.custom_dividend"
              type="number"
              step="0.01"
              min="0"
              placeholder="例：18.5"
              class="mt-2 w-full px-3 py-1.5 border border-[#d8d8d2] bg-white text-sm focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] transition"
            />
          </div>

          <!-- EPS -->
          <div v-if="rawData.eps_ttm">
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">EPS（用於 PE 法）</label>
            <select
              v-model="settings.eps_mode"
              class="w-full px-3 py-1.5 border border-[#d8d8d2] bg-white text-sm focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] transition"
            >
              <option value="ttm">TTM 近 4 季合計（{{ fmt(rawData.eps_ttm) }}）</option>
              <option value="custom">自訂 EPS…</option>
            </select>
            <input
              v-if="settings.eps_mode === 'custom'"
              v-model.number="settings.custom_eps"
              type="number"
              step="0.01"
              placeholder="例：80（預估明年）"
              class="mt-2 w-full px-3 py-1.5 border border-[#d8d8d2] bg-white text-sm focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] transition"
            />
          </div>

          <!-- 安全邊際 -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">
              安全邊際 <strong class="text-[#0a0e16] ml-1">{{ settings.margin_of_safety }}%</strong>
            </label>
            <input
              v-model.number="settings.margin_of_safety"
              type="range"
              min="0"
              max="50"
              step="5"
              class="w-full accent-[#0a0e16]"
            />
            <p class="text-[11px] text-slate-500 mt-1.5 leading-snug">
              <span class="text-emerald-600 font-medium">便宜價 / 合理價</span>會打 {{ settings.margin_of_safety }}% 折扣
              （要再便宜這麼多才視為合理進場），
              <span class="text-red-500 font-medium">昂貴價刻意保持不動</span> ——
              安全邊際是放寬「進場」的條件，不是放寬「賣出」的條件。
            </p>
          </div>

          <button
            v-if="hasCustomization"
            @click="resetSettings"
            class="text-xs text-slate-500 hover:text-red-500 underline"
          >重設為預設值</button>
        </div>
      </details>

      <!-- K 線 -->
      <section v-if="data.kline?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">K 線走勢</h2>
        <div class="bg-white border border-[#e7e7e1] p-3">
          <CandleChart :kline="data.kline" />
        </div>
      </section>

      <!-- 三大法人籌碼 -->
      <section v-if="data.chips?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">三大法人籌碼</h2>
        <div class="bg-white border border-[#e7e7e1] p-3">
          <ChipsChart :chips="data.chips" />
        </div>
      </section>

      <!-- ADR 比較 -->
      <section v-if="data.adr" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">美股 ADR 比較</h2>

        <div class="bg-white border border-[#e7e7e1] p-4">
          <!-- 主視覺：當日漲跌對比 -->
          <div class="text-xs text-slate-500 uppercase tracking-[0.16em] mb-3">當日漲跌對比 — 領先訊號</div>
          <DiffBars
            :tw-change-pct="data.change_pct"
            :adr-change-pct="data.adr.change_pct"
            :tw-label="`台股 ${code}`"
            :adr-label="`ADR ${data.adr.symbol}`"
            :tw-date="data.close_date"
            :adr-date="data.adr.close_date"
          />

          <!-- 收盤價 + 隱含/溢價 grid -->
          <div class="mt-4 pt-4 border-t border-[#e7e7e1] grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
            <div>
              <div class="text-slate-500 text-xs">台股收盤</div>
              <div class="font-bold font-mono">{{ fmt(data.current_price) }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">ADR 收盤</div>
              <div class="font-bold font-mono">${{ fmt(data.adr.close) }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">ADR 隱含台股價</div>
              <div class="font-bold font-mono">{{ fmt(data.adr.implied_tw_price) }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">溢價率</div>
              <div class="font-bold font-mono" :class="data.adr.premium_pct >= 0 ? 'text-red-500' : 'text-emerald-600'">
                {{ data.adr.premium_pct >= 0 ? '+' : '' }}{{ fmt(data.adr.premium_pct, 2) }}%
              </div>
            </div>
          </div>
        </div>

        <div class="text-xs text-slate-600 mt-3 leading-relaxed bg-slate-50 border border-[#e7e7e1] p-3">
          <p class="font-semibold mb-1.5">⏰ 為什麼這個對比是領先訊號？</p>
          <p class="mb-1.5">
            台股 13:30 收盤後，美股當天還沒開盤；美股 16:00 收盤（= 台北時間隔日 04:00）時，
            ADR 已經把這 14~15 小時內全球新聞 + 美股表現都消化進價格。
          </p>
          <p>
            因此「<strong>ADR 當日漲跌 − 台股當日漲跌</strong>」這個差距，
            就是「<strong>台股收盤之後</strong>」這段時間市場對該檔的態度變化 ──
            台股<strong>明天開盤</strong>會補上這段時差。
          </p>
          <p class="text-slate-500 text-[11px] mt-2 pt-2 border-t border-slate-200">
            1 ADR = {{ data.adr.ratio }} 股 · 匯率 USD/TWD = {{ fmt(data.adr.fx_rate, 3) }}
          </p>
        </div>
      </section>

      <!-- 明日開盤預測（only for headline 3 stocks，from /adr Ridge model） -->
      <section v-if="adrPrediction?.predictions?.open_gap" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">明日開盤預測</h2>
        <div v-if="freshness?.stale"
             class="mb-2 px-3 py-2 bg-rose-50 border border-rose-200 rounded text-xs text-rose-700 leading-relaxed">
          ⚠️ 資料已過期（{{ freshness.label }}），此「明日預測」是以 {{ adrPrediction.tw_close_date }} 收盤推論，<strong>非今日有效訊號</strong>，請勿據此交易。
        </div>
        <RouterLink to="/adr" class="block bg-white border-2 border-slate-900/80 hover:border-slate-900 transition">
          <div class="px-4 py-2 bg-slate-900 text-slate-100 text-xs uppercase tracking-wider flex items-baseline justify-between flex-wrap gap-2">
            <span>Ridge + Conformal 80% 區間</span>
            <span class="opacity-70 font-mono normal-case tracking-normal text-[10px]">
              用 {{ adrPrediction.tw_close_date }} 收盤推論 · 點開查詳細
            </span>
          </div>
          <div class="px-4 py-3 grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
            <div>
              <div class="text-slate-500 text-xs uppercase tracking-wider">開盤點估</div>
              <div class="font-mono font-bold text-xl mt-0.5"
                   :class="adrPrediction.predictions.open_gap.point_pct >= 0 ? 'text-red-600' : 'text-emerald-600'">
                {{ adrPrediction.predictions.open_gap.point_pct >= 0 ? '+' : '' }}{{ fmt(adrPrediction.predictions.open_gap.point_pct, 2) }}%
              </div>
              <div class="text-xs text-slate-500 font-mono mt-0.5">
                ~ {{ fmt(adrPrediction.predictions.open_gap.point_price, 0) }}
              </div>
            </div>
            <div>
              <div class="text-slate-500 text-xs uppercase tracking-wider">80% 區間</div>
              <div class="font-mono text-base mt-0.5">
                <span class="text-emerald-600">{{ adrPrediction.predictions.open_gap.lo80_pct >= 0 ? '+' : '' }}{{ fmt(adrPrediction.predictions.open_gap.lo80_pct, 2) }}%</span>
                <span class="text-slate-400 mx-1">~</span>
                <span class="text-red-500">{{ adrPrediction.predictions.open_gap.hi80_pct >= 0 ? '+' : '' }}{{ fmt(adrPrediction.predictions.open_gap.hi80_pct, 2) }}%</span>
              </div>
              <div class="text-xs text-slate-500 font-mono mt-0.5">
                {{ fmt(adrPrediction.predictions.open_gap.lo80_price, 0) }} ~ {{ fmt(adrPrediction.predictions.open_gap.hi80_price, 0) }}
                <span v-if="adrPrediction.predictions.open_gap.crosses_zero" class="text-amber-600 ml-1">⚠ 跨零</span>
              </div>
            </div>
            <div v-if="adrPrediction.walk_forward_30d?.open_gap?.summary">
              <div class="text-slate-500 text-xs uppercase tracking-wider">過去 30 日</div>
              <div class="font-mono text-base mt-0.5">
                MAE <strong>{{ adrPrediction.walk_forward_30d.open_gap.summary.mae_pct }}%</strong>
              </div>
              <div class="text-xs text-slate-500 font-mono mt-0.5">
                命中 <span class="font-semibold" :class="adrPrediction.walk_forward_30d.open_gap.summary.hit_rate_pct >= 70 ? 'text-emerald-600' : 'text-slate-600'">{{ adrPrediction.walk_forward_30d.open_gap.summary.hit_rate_pct }}%</span>
                · cov {{ adrPrediction.walk_forward_30d.open_gap.summary.coverage_pct }}%
              </div>
            </div>
          </div>
          <div v-if="adrPrediction.signals_cleaned.is_event_day || adrPrediction.signals_cleaned.hnhpf_stale"
               class="px-4 py-2 bg-amber-50 border-t border-amber-200 text-xs text-amber-800">
            <span v-if="adrPrediction.signals_cleaned.is_event_day">⚠ 事件日 — 預測可信度低</span>
            <span v-if="adrPrediction.signals_cleaned.hnhpf_stale" class="ml-2">⚠ HNHPF 報價停滯，預測僅供參考</span>
          </div>
        </RouterLink>
      </section>

      <!-- 歷年股利 -->
      <section v-if="data.dividend_history?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">歷年股利</h2>
        <div class="bg-white border border-[#e7e7e1] overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600">
                <th class="px-4 py-2 text-left">年度</th>
                <th class="px-4 py-2 text-right">現金股利</th>
                <th class="px-4 py-2 text-right" title="當年現金股利 ÷ 當年平均收盤價（超出 3 年價格資料者不計）">當年殖利率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in data.dividend_history" :key="d.year" class="border-t border-slate-100">
                <td class="px-4 py-2">{{ d.year }}</td>
                <td class="px-4 py-2 text-right">{{ fmt(d.cash_dividend) }}</td>
                <td class="px-4 py-2 text-right">{{ d.yield != null ? fmt(d.yield * 100, 2) + '%' : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- EPS 季度 -->
      <section v-if="data.eps_quarterly?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">EPS 季度明細</h2>
        <div class="bg-white border border-[#e7e7e1] overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600">
                <th class="px-4 py-2 text-left">季度</th>
                <th class="px-4 py-2 text-right">EPS</th>
                <th class="px-4 py-2 text-right">YoY 成長</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="q in data.eps_quarterly" :key="q.period" class="border-t border-slate-100">
                <td class="px-4 py-2">{{ q.period }}</td>
                <td class="px-4 py-2 text-right">{{ fmt(q.eps) }}</td>
                <td class="px-4 py-2 text-right" :class="q.yoy >= 0 ? 'text-red-500' : 'text-emerald-600'">
                  {{ q.yoy != null ? (q.yoy >= 0 ? '+' : '') + fmt(q.yoy * 100, 1) + '%' : '—' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- 摘要（瀏覽器端用使用者本地的 LLM key 產生；快取在 localStorage） -->
      <section class="mb-6 bg-white border border-[#e7e7e1] border-l-2 border-l-[#b4530b] px-4 py-3">
        <div v-if="summaryState?.text">
          <p class="text-sm leading-relaxed whitespace-pre-line">{{ summaryState.text }}</p>
          <div class="flex items-center justify-between flex-wrap gap-x-3 gap-y-1 mt-2">
            <span class="text-[10px] text-slate-400 font-mono">
              {{ summaryState.provider }} · {{ summaryState.model }} · {{ summaryState.generated_at?.replace(/:\d{2}\+\d{2}:\d{2}$/, '').replace('T', ' ') }}
            </span>
            <div class="flex gap-2">
              <button
                @click="handleGenerateSummary(true)"
                :disabled="summaryLoading"
                class="text-[11px] text-[#b4530b] hover:text-[#0a0e16] disabled:opacity-50"
              >{{ summaryLoading ? '生成中…' : '重新生成' }}</button>
              <button @click="handleClearSummary" class="text-[11px] text-slate-400 hover:text-red-500">清除</button>
            </div>
          </div>
        </div>
        <div v-else>
          <div class="flex items-baseline justify-between gap-3 flex-wrap">
            <div>
              <div class="text-[10px] uppercase tracking-[0.18em] text-slate-500 mb-0.5">AI 摘要</div>
              <p v-if="!settingsStore.hasActiveApiKey" class="text-xs text-slate-500 leading-relaxed">
                需在
                <RouterLink to="/settings" class="text-[#b4530b] hover:text-[#0a0e16] underline">設定</RouterLink>
                填入 {{ settingsStore.llmProvider }} 的 API key 後即可生成。所有金鑰只存在你的瀏覽器。
              </p>
              <p v-else class="text-xs text-slate-500 leading-relaxed">
                依目前估值與基本面資料生成 2~3 句客觀摘要。
                供應商：<span class="font-mono">{{ settingsStore.llmProvider }}</span> ·
                模型：<span class="font-mono">{{ settingsStore.effectiveModel }}</span>
              </p>
            </div>
            <button
              v-if="settingsStore.hasActiveApiKey"
              @click="handleGenerateSummary(false)"
              :disabled="summaryLoading"
              class="px-3 py-1.5 border text-xs uppercase tracking-wider transition shrink-0 font-semibold"
              :class="summaryLoading
                ? 'bg-slate-200 text-slate-500 border-slate-300 cursor-wait'
                : 'bg-[#0a0e16] text-white border-[#0a0e16] hover:bg-black'"
            >{{ summaryLoading ? '生成中…' : '生成摘要' }}</button>
          </div>
          <p v-if="summaryError" class="mt-2 text-xs text-red-600 break-words">⚠ {{ summaryError }}</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
summary::-webkit-details-marker { display: none; }
summary::marker { display: none; }
</style>
