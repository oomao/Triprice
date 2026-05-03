<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import { useWatchlistStore } from '../stores/watchlist'

const route = useRoute()
const watchlist = useWatchlistStore()
const data = ref(null)
const stocksMeta = ref(null)
const loading = ref(true)
const error = ref(null)

const code = computed(() => route.params.code)
const meta = computed(() => stocksMeta.value?.tw_stocks?.[code.value])

async function load() {
  loading.value = true
  error.value = null
  data.value = null
  try {
    const base = import.meta.env.BASE_URL
    const [stocksRes, dataRes] = await Promise.all([
      fetch(`${base}data/stocks.json`),
      fetch(`${base}data/tw/${code.value}.json`)
    ])
    stocksMeta.value = await stocksRes.json()
    if (dataRes.ok) {
      data.value = await dataRes.json()
    } else {
      error.value = '尚無此股票的估值資料'
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
    maximumFractionDigits: d
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
</script>

<template>
  <div>
    <RouterLink to="/" class="text-sm text-sky-600 hover:underline">← 回清單</RouterLink>

    <div v-if="loading" class="text-slate-500 py-8 text-center">載入中…</div>
    <div v-else-if="error && !data" class="py-8">
      <p class="text-slate-700">{{ error }}</p>
      <p class="text-sm text-slate-500 mt-2">資料抓取 script 還沒跑過。執行 <code class="bg-slate-200 px-1 rounded">python scripts/fetch_tw.py {{ code }}</code> 後重試。</p>
    </div>
    <div v-else-if="data">
      <!-- Header -->
      <div class="flex items-start justify-between mt-2 mb-5">
        <div>
          <h1 class="text-2xl font-bold">
            {{ meta?.name }}
            <span class="text-base font-mono text-slate-500 ml-2">{{ code }}</span>
          </h1>
          <div class="text-sm text-slate-500 mt-1">
            收盤 {{ data.close_date }} ·
            <span class="font-bold text-slate-900 text-base">{{ fmt(data.current_price) }}</span>
            <span v-if="data.change != null" :class="data.change >= 0 ? 'text-red-500' : 'text-emerald-600'" class="ml-2">
              {{ data.change >= 0 ? '+' : '' }}{{ fmt(data.change) }}
              ({{ data.change >= 0 ? '+' : '' }}{{ fmt(data.change_pct, 2) }}%)
            </span>
          </div>
        </div>
        <button
          @click="watchlist.toggle(code)"
          class="px-3 py-1.5 rounded-lg border text-sm transition"
          :class="watchlist.has(code)
            ? 'bg-amber-50 border-amber-400 text-amber-700'
            : 'bg-white border-slate-300 hover:border-sky-400'"
        >
          {{ watchlist.has(code) ? '★ 已自選' : '☆ 加入自選' }}
        </button>
      </div>

      <!-- 殖利率法估值表 -->
      <section class="mb-6">
        <div class="flex items-baseline gap-2 mb-2">
          <h2 class="text-lg font-semibold">殖利率法估值</h2>
          <span v-if="yieldTier" class="text-sm font-medium" :class="yieldTier.color">
            目前位置：{{ yieldTier.label }}
          </span>
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
          使用最近一年股利 {{ fmt(data.dividend_used) }} 元 · 殖利率區間取自近 3 年
        </p>
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
          使用近 4 季 EPS 合計 {{ fmt(data.eps_ttm) }} 元
        </p>
      </section>

      <!-- ADR 比較 -->
      <section v-if="data.adr" class="mb-6">
        <h2 class="text-lg font-semibold mb-2">美股 ADR 比較</h2>
        <div class="bg-white rounded-lg shadow-sm border border-slate-200 p-4">
          <div class="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div class="text-slate-500 text-xs">ADR 代號</div>
              <div class="font-mono font-bold">{{ data.adr.symbol }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">ADR 收盤 ({{ data.adr.close_date }})</div>
              <div class="font-bold">${{ fmt(data.adr.close) }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">隱含台股價</div>
              <div class="font-bold">{{ fmt(data.adr.implied_tw_price) }}</div>
            </div>
            <div>
              <div class="text-slate-500 text-xs">溢價率</div>
              <div class="font-bold" :class="data.adr.premium_pct >= 0 ? 'text-red-500' : 'text-emerald-600'">
                {{ data.adr.premium_pct >= 0 ? '+' : '' }}{{ fmt(data.adr.premium_pct, 2) }}%
              </div>
            </div>
          </div>
          <p class="text-xs text-slate-500 mt-3 leading-relaxed">
            ⏰ ADR 收盤晚於台股約 14~15 小時，此溢價率可作為台股<strong>隔日開盤</strong>方向的參考訊號。
            <br>1 ADR = {{ data.adr.ratio }} 股，匯率 USD/TWD = {{ fmt(data.adr.fx_rate, 3) }}
          </p>
        </div>
      </section>

      <!-- 歷年股利明細 -->
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

      <!-- EPS 明細 -->
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
