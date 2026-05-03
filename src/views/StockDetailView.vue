<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useWatchlistStore } from '../stores/watchlist'
import BandChart from '../components/BandChart.vue'

const route = useRoute()
const watchlist = useWatchlistStore()
const rawData = ref(null)
const stocksMeta = ref(null)
const loading = ref(true)
const loadingMessage = ref('載入中…')
const error = ref(null)

const code = computed(() => route.params.code)
const meta = computed(() => stocksMeta.value?.tw_stocks?.[code.value])
const isDynamic = computed(() => rawData.value?._dynamic === true)

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
  rawData.value = null
  loadSettings(code.value)
  try {
    const base = import.meta.env.BASE_URL
    const [stocksRes, dataRes] = await Promise.all([
      fetch(`${base}data/stocks.json`),
      fetch(`${base}data/tw/${code.value}.json`),
    ])
    stocksMeta.value = await stocksRes.json()
    if (dataRes.ok) {
      rawData.value = await dataRes.json()
    } else {
      loadingMessage.value = '此股票未預載，從 FinMind 即時抓取（約 5 秒）…'
      try {
        const { fetchStockDynamic } = await import('../lib/finmind.js')
        rawData.value = await fetchStockDynamic(code.value)
      } catch (e) {
        error.value = `動態抓取失敗：${e.message}`
      }
    }
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
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

function priceTier(current, valuation) {
  if (!current || !valuation) return null
  if (current <= valuation.cheap) return { label: '便宜', color: 'text-emerald-600' }
  if (current <= valuation.fair) return { label: '合理偏便宜', color: 'text-emerald-500' }
  if (current <= valuation.expensive) return { label: '合理偏貴', color: 'text-amber-500' }
  return { label: '昂貴', color: 'text-red-500' }
}

const yieldTier = computed(() => priceTier(data.value?.current_price, data.value?.valuation_yield))
const peTier = computed(() => priceTier(data.value?.current_price, data.value?.valuation_pe))

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
    <RouterLink to="/" class="text-sm text-sky-600 hover:underline">← 回清單</RouterLink>

    <div v-if="loading" class="text-slate-500 py-8 text-center">{{ loadingMessage }}</div>
    <div v-else-if="error && !data" class="py-8">
      <p class="text-slate-700">{{ error }}</p>
      <p class="text-sm text-slate-500 mt-2">請確認代號正確（4-6 碼數字 / 字母），或稍後重試。</p>
    </div>
    <div v-else-if="data">
      <!-- Header -->
      <div class="flex items-start justify-between mt-2 mb-5 gap-3">
        <div class="min-w-0">
          <h1 class="text-2xl font-bold">
            {{ meta?.name || rawData?.name || code }}
            <span class="text-base font-mono text-slate-500 ml-2">{{ code }}</span>
            <span v-if="isDynamic" class="ml-2 text-xs text-sky-600 font-normal align-middle">即時抓取</span>
          </h1>
          <div class="text-sm text-slate-500 mt-1">
            收盤 {{ rawData.close_date }} ·
            <span class="font-bold text-slate-900 text-base">{{ fmt(rawData.current_price) }}</span>
            <span
              v-if="rawData.change != null"
              :class="rawData.change >= 0 ? 'text-red-500' : 'text-emerald-600'"
              class="ml-2"
            >
              {{ rawData.change >= 0 ? '+' : '' }}{{ fmt(rawData.change) }}
              ({{ rawData.change >= 0 ? '+' : '' }}{{ fmt(rawData.change_pct, 2) }}%)
            </span>
          </div>
        </div>
        <button
          @click="watchlist.toggle(code)"
          class="px-3 py-1.5 rounded-lg border text-sm transition shrink-0"
          :class="
            watchlist.has(code)
              ? 'bg-amber-50 border-amber-400 text-amber-700'
              : 'bg-white border-slate-300 hover:border-sky-400'
          "
        >
          {{ watchlist.has(code) ? '★ 已自選' : '☆ 加入自選' }}
        </button>
      </div>

      <!-- 進階設定 -->
      <details class="mb-5 group" :open="hasCustomization">
        <summary
          class="cursor-pointer text-sm font-medium text-sky-600 hover:text-sky-700 inline-flex items-center gap-1.5 select-none list-none"
        >
          <span class="inline-block transition-transform group-open:rotate-90 text-xs">▶</span>
          進階設定
          <span
            v-if="hasCustomization"
            class="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 font-normal"
          >已自訂</span>
        </summary>

        <div class="mt-3 bg-white rounded-lg border border-slate-200 p-4 space-y-4">
          <!-- 股利取值 -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">股利取值</label>
            <select
              v-model="settings.dividend_mode"
              class="w-full px-3 py-1.5 rounded border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
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
              class="mt-2 w-full px-3 py-1.5 rounded border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <!-- EPS -->
          <div v-if="rawData.eps_ttm">
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">EPS（用於 PE 法）</label>
            <select
              v-model="settings.eps_mode"
              class="w-full px-3 py-1.5 rounded border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
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
              class="mt-2 w-full px-3 py-1.5 rounded border border-slate-300 bg-white text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            />
          </div>

          <!-- 安全邊際 -->
          <div>
            <label class="block text-xs font-semibold text-slate-700 mb-1.5">
              安全邊際 <strong class="text-sky-700 ml-1">{{ settings.margin_of_safety }}%</strong>
            </label>
            <input
              v-model.number="settings.margin_of_safety"
              type="range"
              min="0"
              max="50"
              step="5"
              class="w-full accent-sky-600"
            />
            <p class="text-[11px] text-slate-500 mt-1 leading-snug">
              套用 {{ settings.margin_of_safety }}% 折扣到便宜價與合理價（昂貴價不變，作為賣出參考）
            </p>
          </div>

          <button
            v-if="hasCustomization"
            @click="resetSettings"
            class="text-xs text-slate-500 hover:text-red-500 underline"
          >重設為預設值</button>
        </div>
      </details>

      <!-- 殖利率法估值表 -->
      <section class="mb-6">
        <div class="flex items-baseline gap-2 mb-2">
          <h2 class="text-lg font-semibold">殖利率法估值</h2>
          <span v-if="yieldTier" class="text-sm font-medium" :class="yieldTier.color">
            目前位置：{{ yieldTier.label }}
          </span>
        </div>
        <div
          v-if="data.yield_stats && data.yield_stats.avg < 0.02"
          class="mb-2 px-3 py-2 bg-amber-50 border border-amber-200 rounded text-xs text-slate-700 leading-relaxed"
        >
          ⚠️ 此股殖利率偏低（平均 {{ fmt(data.yield_stats.avg * 100, 2) }}%）—— 殖利率法對成長股會嚴重低估合理價，請以下方 PE 法為主要參考。
        </div>
        <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
          <table class="w-full text-sm">
            <tbody>
              <tr class="border-b border-slate-100">
                <td class="px-4 py-2.5 bg-slate-50 w-1/3 sm:w-1/4">便宜價</td>
                <td class="px-4 py-2.5 text-emerald-600 font-bold">{{ fmt(data.valuation_yield?.cheap) }}</td>
                <td class="px-4 py-2.5 text-xs text-slate-500 hidden sm:table-cell">
                  股利 {{ fmt(data.dividend_used) }} / 高殖利率 {{ fmt(data.yield_stats?.high * 100, 2) }}%
                </td>
              </tr>
              <tr class="border-b border-slate-100">
                <td class="px-4 py-2.5 bg-slate-50">合理價</td>
                <td class="px-4 py-2.5 text-sky-600 font-bold">{{ fmt(data.valuation_yield?.fair) }}</td>
                <td class="px-4 py-2.5 text-xs text-slate-500 hidden sm:table-cell">
                  股利 {{ fmt(data.dividend_used) }} / 平均殖利率 {{ fmt(data.yield_stats?.avg * 100, 2) }}%
                </td>
              </tr>
              <tr>
                <td class="px-4 py-2.5 bg-slate-50">昂貴價</td>
                <td class="px-4 py-2.5 text-red-500 font-bold">{{ fmt(data.valuation_yield?.expensive) }}</td>
                <td class="px-4 py-2.5 text-xs text-slate-500 hidden sm:table-cell">
                  股利 {{ fmt(data.dividend_used) }} / 低殖利率 {{ fmt(data.yield_stats?.low * 100, 2) }}%
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          {{ dividendLabel }} {{ fmt(data.dividend_used) }} 元 · 殖利率區間取自近 3 年
          <span v-if="settings.margin_of_safety > 0" class="text-amber-600">· 安全邊際 {{ settings.margin_of_safety }}%</span>
        </p>

        <div
          v-if="data.valuation_yield && data.price_history?.length"
          class="mt-3 bg-white rounded-lg border border-slate-200 p-3"
        >
          <BandChart
            :history="data.price_history"
            :bands="data.valuation_yield"
            :current-price="data.current_price"
          />
        </div>
      </section>

      <!-- PE 法估值表 -->
      <section v-if="data.valuation_pe" class="mb-6">
        <div class="flex items-baseline gap-2 mb-2">
          <h2 class="text-lg font-semibold">本益比 (PE) 法估值</h2>
          <span v-if="peTier" class="text-sm font-medium" :class="peTier.color">
            目前位置：{{ peTier.label }}
          </span>
        </div>
        <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
          <table class="w-full text-sm">
            <tbody>
              <tr class="border-b border-slate-100">
                <td class="px-4 py-2.5 bg-slate-50 w-1/3 sm:w-1/4">便宜價</td>
                <td class="px-4 py-2.5 text-emerald-600 font-bold">{{ fmt(data.valuation_pe.cheap) }}</td>
                <td class="px-4 py-2.5 text-xs text-slate-500 hidden sm:table-cell">EPS × 低 PE {{ fmt(data.pe_stats?.low, 1) }}</td>
              </tr>
              <tr class="border-b border-slate-100">
                <td class="px-4 py-2.5 bg-slate-50">合理價</td>
                <td class="px-4 py-2.5 text-sky-600 font-bold">{{ fmt(data.valuation_pe.fair) }}</td>
                <td class="px-4 py-2.5 text-xs text-slate-500 hidden sm:table-cell">EPS × 平均 PE {{ fmt(data.pe_stats?.avg, 1) }}</td>
              </tr>
              <tr>
                <td class="px-4 py-2.5 bg-slate-50">昂貴價</td>
                <td class="px-4 py-2.5 text-red-500 font-bold">{{ fmt(data.valuation_pe.expensive) }}</td>
                <td class="px-4 py-2.5 text-xs text-slate-500 hidden sm:table-cell">EPS × 高 PE {{ fmt(data.pe_stats?.high, 1) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="text-xs text-slate-500 mt-1">
          {{ epsLabel }} {{ fmt(data.eps_ttm) }} 元
          <span v-if="settings.margin_of_safety > 0" class="text-amber-600">· 安全邊際 {{ settings.margin_of_safety }}%</span>
        </p>

        <div
          v-if="data.valuation_pe && data.price_history?.length"
          class="mt-3 bg-white rounded-lg border border-slate-200 p-3"
        >
          <BandChart
            :history="data.price_history"
            :bands="data.valuation_pe"
            :current-price="data.current_price"
          />
        </div>
      </section>

      <!-- ADR 比較 -->
      <section v-if="data.adr" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">美股 ADR 比較</h2>
        <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600 text-xs">
                <th class="px-3 py-2 text-left font-semibold w-1/4">&nbsp;</th>
                <th class="px-3 py-2 text-center font-semibold">台股 {{ code }}</th>
                <th class="px-3 py-2 text-center font-semibold">ADR {{ data.adr.symbol }}</th>
              </tr>
            </thead>
            <tbody>
              <tr class="border-t border-slate-100">
                <td class="px-3 py-2 text-slate-500 text-xs">收盤日</td>
                <td class="px-3 py-2 text-center font-mono text-xs">{{ data.close_date }}</td>
                <td class="px-3 py-2 text-center font-mono text-xs">{{ data.adr.close_date }}</td>
              </tr>
              <tr class="border-t border-slate-100">
                <td class="px-3 py-2 text-slate-500 text-xs">收盤價</td>
                <td class="px-3 py-2 text-center font-bold">{{ fmt(data.current_price) }}</td>
                <td class="px-3 py-2 text-center font-bold">${{ fmt(data.adr.close) }}</td>
              </tr>
              <tr class="border-t border-slate-100">
                <td class="px-3 py-2 text-slate-500 text-xs">今日漲跌</td>
                <td
                  class="px-3 py-2 text-center font-bold"
                  :class="data.change >= 0 ? 'text-red-500' : 'text-emerald-600'"
                >
                  <span v-if="data.change != null">
                    {{ data.change >= 0 ? '+' : '' }}{{ fmt(data.change) }}
                    <span class="text-xs font-normal opacity-80">
                      ({{ data.change >= 0 ? '+' : '' }}{{ fmt(data.change_pct, 2) }}%)
                    </span>
                  </span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td
                  class="px-3 py-2 text-center font-bold"
                  :class="data.adr.change >= 0 ? 'text-red-500' : 'text-emerald-600'"
                >
                  <span v-if="data.adr.change != null">
                    {{ data.adr.change >= 0 ? '+' : '' }}{{ fmt(data.adr.change) }}
                    <span class="text-xs font-normal opacity-80">
                      ({{ data.adr.change_pct >= 0 ? '+' : '' }}{{ fmt(data.adr.change_pct, 2) }}%)
                    </span>
                  </span>
                  <span v-else class="text-slate-400">—</span>
                </td>
              </tr>
            </tbody>
          </table>
          <div class="border-t border-slate-200 px-4 py-3 bg-sky-50/50 grid grid-cols-2 gap-3 text-sm">
            <div>
              <div class="text-slate-500 text-xs">ADR 隱含台股價</div>
              <div class="font-bold">{{ fmt(data.adr.implied_tw_price) }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">溢價率</div>
              <div class="font-bold" :class="data.adr.premium_pct >= 0 ? 'text-red-500' : 'text-emerald-600'">
                {{ data.adr.premium_pct >= 0 ? '+' : '' }}{{ fmt(data.adr.premium_pct, 2) }}%
              </div>
            </div>
          </div>
        </div>
        <p class="text-xs text-slate-500 mt-2 leading-relaxed">
          ⏰ ADR 收盤晚於台股約 14~15 小時。「ADR 今日漲跌」反映美股最近一個交易日相對前一日的變化，可作為台股<strong>隔日開盤</strong>方向的參考訊號。
          <br>1 ADR = {{ data.adr.ratio }} 股，匯率 USD/TWD = {{ fmt(data.adr.fx_rate, 3) }}
        </p>
      </section>

      <!-- 歷年股利 -->
      <section v-if="data.dividend_history?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">歷年股利</h2>
        <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600">
                <th class="px-4 py-2 text-left">年度</th>
                <th class="px-4 py-2 text-right">現金股利</th>
                <th class="px-4 py-2 text-right">當年殖利率</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="d in data.dividend_history" :key="d.year" class="border-t border-slate-100">
                <td class="px-4 py-2">{{ d.year }}</td>
                <td class="px-4 py-2 text-right">{{ fmt(d.cash_dividend) }}</td>
                <td class="px-4 py-2 text-right">{{ fmt(d.yield * 100, 2) }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- EPS 季度 -->
      <section v-if="data.eps_quarterly?.length" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">EPS 季度明細</h2>
        <div class="bg-white rounded-lg shadow-sm border border-slate-200 overflow-hidden">
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
    </div>
  </div>
</template>

<style scoped>
summary::-webkit-details-marker { display: none; }
summary::marker { display: none; }
</style>
