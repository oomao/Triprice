<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { CONDITIONS, evaluate } from '../lib/screener.js'

const stocksMeta = ref(null)
const stocks = ref([])     // array of full TW JSONs
const fx = ref(null)       // fx.json — has vix
const loading = ref(true)
const error = ref(null)

// User selections (persisted)
const STORAGE_KEY = 'triprice.screener.v1'
const initial = (() => {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') } catch { return {} }
})()

const active = reactive({   // which conditions are turned on
  vix_high:        initial.active?.vix_high ?? false,
  monthly_kd_low:  initial.active?.monthly_kd_low ?? true,
  pb_low:          initial.active?.pb_low ?? false,
  yield_high:      initial.active?.yield_high ?? true,
  pe_low_pctile:   initial.active?.pe_low_pctile ?? true,
  below_ma60:      initial.active?.below_ma60 ?? false,
})

const params = reactive({
  vix_high:        initial.params?.vix_high ?? CONDITIONS.vix_high.defaultParam,
  monthly_kd_low:  initial.params?.monthly_kd_low ?? CONDITIONS.monthly_kd_low.defaultParam,
  pb_low:          initial.params?.pb_low ?? CONDITIONS.pb_low.defaultParam,
  yield_high:      initial.params?.yield_high ?? CONDITIONS.yield_high.defaultParam,
  pe_low_pctile:   initial.params?.pe_low_pctile ?? CONDITIONS.pe_low_pctile.defaultParam,
  below_ma60:      initial.params?.below_ma60 ?? CONDITIONS.below_ma60.defaultParam,
})

const showOnlyHits = ref(initial.showOnlyHits ?? true)
const sortKey = ref(initial.sortKey ?? 'hitCount')   // 'hitCount' | 'yield_pct' | 'pe_pctile' | 'monthly_k' | 'pbr'
const sortDir = ref(initial.sortDir ?? 'desc')

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      active: { ...active },
      params: { ...params },
      showOnlyHits: showOnlyHits.value,
      sortKey: sortKey.value,
      sortDir: sortDir.value,
    }))
  } catch { /* ignore */ }
}

onMounted(async () => {
  try {
    const base = import.meta.env.BASE_URL
    const stocksRes = await fetch(`${base}data/stocks.json`)
    stocksMeta.value = await stocksRes.json()
    const codes = Object.keys(stocksMeta.value.tw_stocks)
    const fxRes = fetch(`${base}data/fx.json`)
    const stockResults = await Promise.all(
      codes.map(c => fetch(`${base}data/tw/${c}.json`).then(r => r.ok ? r.json() : null).catch(() => null))
    )
    stocks.value = stockResults.filter(Boolean)
    const fxR = await fxRes
    if (fxR.ok) fx.value = await fxR.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const activeKeys = computed(() => Object.keys(active).filter(k => active[k]))
const marketCtx = computed(() => ({ vix: fx.value?.vix ?? null }))

const evaluated = computed(() => {
  return stocks.value.map(s => evaluate(s, activeKeys.value, params, marketCtx.value))
})

const filtered = computed(() => {
  const list = showOnlyHits.value && activeKeys.value.length > 0
    ? evaluated.value.filter(e => e.hitCount > 0)
    : evaluated.value
  return [...list].sort((a, b) => {
    const av = a[sortKey.value]
    const bv = b[sortKey.value]
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return sortDir.value === 'desc' ? bv - av : av - bv
  })
})

function toggle(key) { active[key] = !active[key]; persist() }
function setSort(k) {
  if (sortKey.value === k) sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  else { sortKey.value = k; sortDir.value = k === 'pe_pctile' || k === 'monthly_k' || k === 'pbr' ? 'asc' : 'desc' }
  persist()
}
function onParamInput() { persist() }

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}
function hitClass(v) {
  if (v === true) return 'bg-emerald-50 border-emerald-300 text-emerald-700'
  if (v === false) return 'bg-slate-50 border-slate-200 text-slate-400'
  return 'bg-amber-50 border-amber-200 text-amber-600'  // null = no data
}
function hitMark(v) {
  if (v === true) return '✓'
  if (v === false) return ''
  return '?'
}
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold tracking-tight mb-1">多條件選股器</h1>
    <p class="text-sm text-slate-500 mb-5 leading-relaxed">
      勾選條件 + 設參數，把符合的股票排出來。VIX 為大盤層級條件（一檔只會 hit 0/1 次）。
      <strong>所有運算都在你的瀏覽器執行</strong>，沒上傳。
    </p>

    <div v-if="loading" class="py-8">
      <div class="skel h-32 w-full mb-3"></div>
      <div class="skel h-64 w-full"></div>
    </div>
    <div v-else-if="error" class="text-red-600 py-8 text-sm">載入失敗：{{ error }}</div>
    <div v-else>
      <!-- VIX banner -->
      <div v-if="fx?.vix != null"
           class="mb-4 px-3 py-2 border bg-white text-sm flex items-center justify-between flex-wrap gap-2"
           :class="fx.vix >= 30 ? 'border-red-300 bg-red-50' : 'border-[#e7e7e1]'">
        <span>
          <strong>VIX</strong>
          <span class="ml-2 font-mono text-lg" :class="fx.vix >= 30 ? 'text-red-600' : (fx.vix >= 20 ? 'text-amber-600' : 'text-emerald-600')">
            {{ fmt(fx.vix) }}
          </span>
          <span class="ml-2 text-xs text-slate-500">
            {{ fx.vix < 15 ? '極度平靜' : fx.vix < 20 ? '平靜' : fx.vix < 30 ? '溫和警戒' : fx.vix < 40 ? '高度警戒' : '恐慌' }}
          </span>
        </span>
        <span class="text-[11px] text-slate-500 font-mono">{{ fx.vix_date }}</span>
      </div>

      <!-- Conditions panel -->
      <section class="bg-white border border-[#e7e7e1] p-4 mb-4">
        <div class="flex items-baseline justify-between mb-3">
          <h2 class="text-base font-semibold tracking-tight">條件</h2>
          <label class="text-xs text-slate-600 inline-flex items-center gap-1.5 cursor-pointer">
            <input type="checkbox" v-model="showOnlyHits" @change="persist" class="accent-[#0a0e16]" />
            僅顯示有命中的個股
          </label>
        </div>
        <div class="grid sm:grid-cols-2 gap-2">
          <label
            v-for="(c, key) in CONDITIONS"
            :key="key"
            class="flex items-start gap-3 p-3 border cursor-pointer transition"
            :class="active[key]
              ? 'bg-[#0a0e16]/5 border-[#0a0e16]'
              : 'bg-white border-[#e7e7e1] hover:border-[#0a0e16]'"
          >
            <input
              type="checkbox" :checked="active[key]" @change="toggle(key)"
              class="mt-0.5 accent-[#0a0e16]"
            />
            <div class="flex-1 min-w-0">
              <div class="flex items-baseline gap-2">
                <span class="font-semibold text-sm">{{ c.label }}</span>
                <span v-if="c.isMarketWide" class="text-[10px] uppercase tracking-wider text-slate-500">market</span>
              </div>
              <div class="text-xs text-slate-500 mt-0.5 leading-snug">{{ c.hint }}</div>
              <div v-if="!c.paramless && active[key]" class="mt-2 flex items-center gap-2">
                <span class="text-xs text-slate-600">
                  {{ key === 'pe_low_pctile' ? '≤' : (key === 'yield_high' || key === 'vix_high') ? '≥' : '≤' }}
                </span>
                <input
                  type="number"
                  v-model.number="params[key]"
                  @input="onParamInput"
                  step="0.5"
                  class="w-20 px-2 py-0.5 text-sm border border-[#d8d8d2] focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16]"
                />
                <span class="text-xs text-slate-500">{{ c.paramUnit }}</span>
              </div>
            </div>
          </label>
        </div>
      </section>

      <!-- Result count -->
      <div class="text-xs text-slate-500 mb-2">
        匹配 {{ filtered.length }} / {{ stocks.length }} 檔
        <span v-if="activeKeys.length === 0" class="text-amber-600 ml-2">（請先勾選至少一個條件）</span>
      </div>

      <!-- Result table -->
      <div class="bg-white border border-[#e7e7e1] overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600 text-xs">
                <th class="px-3 py-2 text-left font-semibold">代號 / 名稱</th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100"
                    @click="setSort('hitCount')">
                  命中<span v-if="sortKey === 'hitCount'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden sm:table-cell"
                    @click="setSort('yield_pct')">
                  殖利率<span v-if="sortKey === 'yield_pct'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden sm:table-cell"
                    @click="setSort('pbr')">
                  PBR<span v-if="sortKey === 'pbr'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden md:table-cell"
                    @click="setSort('pe_pctile')">
                  PE 百分位<span v-if="sortKey === 'pe_pctile'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden md:table-cell"
                    @click="setSort('monthly_k')">
                  月 K<span v-if="sortKey === 'monthly_k'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-center font-semibold">狀態</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in filtered" :key="e.code" class="border-t border-[#e7e7e1] hover:bg-slate-50/50 transition">
                <td class="px-3 py-2.5">
                  <RouterLink :to="`/stock/${e.code}`" class="block group">
                    <div class="font-mono text-[11px] text-slate-500">{{ e.code }}</div>
                    <div class="font-semibold text-sm group-hover:text-[#b4530b] transition">{{ e.name }}</div>
                  </RouterLink>
                </td>
                <td class="px-3 py-2.5 text-right">
                  <span class="font-bold text-base" :class="e.hitCount >= activeKeys.length && activeKeys.length > 0 ? 'text-emerald-600' : 'text-slate-700'">
                    {{ e.hitCount }}
                  </span>
                  <span class="text-[10px] text-slate-400">/{{ activeKeys.length }}</span>
                </td>
                <td class="px-3 py-2.5 text-right font-mono hidden sm:table-cell">
                  <span v-if="e.yield_pct">{{ fmt(e.yield_pct) }}%</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5 text-right font-mono hidden sm:table-cell">
                  <span v-if="e.pbr">{{ fmt(e.pbr) }}</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5 text-right font-mono hidden md:table-cell">
                  <span v-if="e.pe_pctile != null">{{ fmt(e.pe_pctile, 0) }}%</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5 text-right font-mono hidden md:table-cell">
                  <span v-if="e.monthly_k != null">{{ fmt(e.monthly_k, 0) }}</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5">
                  <div class="flex flex-wrap gap-1 justify-center">
                    <span
                      v-for="key in activeKeys" :key="key"
                      :title="`${CONDITIONS[key].label}: ${e.hits[key] === true ? '命中' : e.hits[key] === false ? '未達' : '無資料'}`"
                      :class="['inline-flex items-center justify-center w-5 h-5 border text-[10px] font-mono', hitClass(e.hits[key])]"
                    >{{ hitMark(e.hits[key]) }}</span>
                  </div>
                </td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="7" class="text-center text-slate-400 py-8 text-sm">
                  {{ activeKeys.length === 0 ? '請勾選至少一個條件' : '沒有股票符合目前的條件組合' }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <details class="mt-4 group">
        <summary class="cursor-pointer text-xs text-[#b4530b] hover:text-[#0a0e16] select-none">
          <span class="inline-block transition-transform group-open:rotate-90 mr-1">▶</span>
          狀態欄位說明
        </summary>
        <div class="mt-2 text-xs text-slate-600 leading-relaxed bg-slate-50 border border-[#e7e7e1] p-3 space-y-1.5">
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center justify-center w-5 h-5 border bg-emerald-50 border-emerald-300 text-emerald-700 text-[10px] font-mono">✓</span>
            條件達標
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center justify-center w-5 h-5 border bg-slate-50 border-slate-200 text-slate-400 text-[10px] font-mono"></span>
            條件未達標
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center justify-center w-5 h-5 border bg-amber-50 border-amber-200 text-amber-600 text-[10px] font-mono">?</span>
            資料不足無法判斷（例 ETF 無 PE / PBR；EPS 缺失）
          </div>
        </div>
      </details>
    </div>
  </div>
</template>
