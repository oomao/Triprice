<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useWatchlistStore } from '../stores/watchlist'

const watchlist = useWatchlistStore()
const stocks = ref(null)
const customCode = ref('')
const errMsg = ref('')
const loaded = ref(new Map()) // code -> stock JSON
const loadingCodes = ref(new Set())

const CODE_RE = /^[0-9A-Z]{2,6}$/

onMounted(async () => {
  const res = await fetch(`${import.meta.env.BASE_URL}data/stocks.json`)
  stocks.value = await res.json()
  await refreshAll()
})

watch(() => watchlist.codes.length, () => refreshAll())

async function loadOne(code) {
  if (loaded.value.has(code) || loadingCodes.value.has(code)) return
  loadingCodes.value.add(code)
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/tw/${code}.json`)
    if (res.ok) {
      const j = await res.json()
      loaded.value.set(code, j)
      // Trigger reactivity (Map mutations aren't deep-reactive in Vue 3 by default)
      loaded.value = new Map(loaded.value)
    }
  } catch {
    // ignore — code may not be preloaded; user can click into detail to fetch dynamically
  } finally {
    loadingCodes.value.delete(code)
  }
}

async function refreshAll() {
  await Promise.all(watchlist.codes.map((c) => loadOne(c)))
}

function addCustom() {
  const c = customCode.value.trim().toUpperCase()
  errMsg.value = ''
  if (!c) return
  if (!CODE_RE.test(c)) {
    errMsg.value = '代號格式錯誤（請輸入 2~6 碼字母或數字）'
    return
  }
  watchlist.add(c)
  customCode.value = ''
}

function preferredBands(d) {
  // Prefer PE method when available (better for growth stocks); otherwise yield method.
  if (d?.valuation_pe) return { bands: d.valuation_pe, method: 'pe' }
  if (d?.valuation_yield) return { bands: d.valuation_yield, method: 'yield' }
  return null
}

function positionPct(price, bands) {
  if (!price || !bands) return null
  if (bands.expensive === bands.cheap) return null
  const pct = ((price - bands.cheap) / (bands.expensive - bands.cheap)) * 100
  return Math.round(pct)
}

function stockEntry(code) {
  const d = loaded.value.get(code)
  if (!d) return { code, name: stocks.value?.tw_stocks?.[code]?.name, loaded: false }
  const ref = preferredBands(d)
  const pos = ref ? positionPct(d.current_price, ref.bands) : null
  return {
    code,
    name: d.name || stocks.value?.tw_stocks?.[code]?.name || code,
    loaded: true,
    price: d.current_price,
    change_pct: d.change_pct,
    method: ref?.method,
    bands: ref?.bands,
    position: pos,
    eps_ttm: d.eps_ttm,
    yield_pct: d.yield_stats?.avg ? Math.round(d.yield_stats.avg * 10000) / 100 : null,
  }
}

const entries = computed(() => watchlist.codes.map(stockEntry))

const summary = computed(() => {
  const valid = entries.value.filter((e) => e.position != null)
  if (!valid.length) return null
  const avg = valid.reduce((s, e) => s + e.position, 0) / valid.length
  const sorted = [...valid].sort((a, b) => a.position - b.position)
  return {
    count: valid.length,
    total: entries.value.length,
    avg: Math.round(avg),
    cheapest: sorted[0],
    priciest: sorted[sorted.length - 1],
  }
})

function tierColor(pct) {
  if (pct == null) return 'text-slate-400'
  if (pct < 0) return 'text-emerald-700'
  if (pct < 50) return 'text-emerald-500'
  if (pct < 100) return 'text-amber-500'
  return 'text-red-500'
}
function tierLabel(pct) {
  if (pct == null) return '—'
  if (pct < 0) return '便宜以下'
  if (pct < 33) return '便宜'
  if (pct < 67) return '合理'
  if (pct < 100) return '偏貴'
  return '昂貴以上'
}
function tierBg(pct) {
  if (pct == null) return 'bg-slate-100'
  if (pct < 0) return 'bg-emerald-100'
  if (pct < 50) return 'bg-emerald-50'
  if (pct < 100) return 'bg-amber-50'
  return 'bg-red-50'
}

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}
</script>

<template>
  <div>
    <h1 class="text-xl font-bold tracking-tight mb-1">自選股</h1>
    <p class="text-xs text-slate-500 mb-4">手動加入任意股票代號（台股 4 碼，例：2330）</p>

    <div class="flex gap-2 mb-1">
      <input
        v-model="customCode"
        @keyup.enter="addCustom"
        @input="errMsg = ''"
        type="text"
        placeholder="輸入股票代號…"
        class="flex-1 px-3 py-2 border border-[#d8d8d2] focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16] bg-white transition"
      />
      <button
        @click="addCustom"
        class="px-4 py-2 bg-[#0a0e16] text-white hover:bg-black transition font-medium text-sm"
      >新增</button>
    </div>
    <p v-if="errMsg" class="text-sm text-red-600 mb-4">{{ errMsg }}</p>
    <div v-else class="mb-4"></div>

    <!-- Aggregate summary -->
    <section v-if="summary" class="bg-white border border-[#e7e7e1] p-4 mb-4">
      <div class="flex items-baseline justify-between mb-2">
        <h2 class="text-base font-semibold">組合便宜度</h2>
        <span class="text-xs text-slate-500">{{ summary.count }} / {{ summary.total }} 檔已載入估值資料</span>
      </div>
      <div class="grid sm:grid-cols-3 gap-3">
        <div :class="['p-3 border border-slate-200', tierBg(summary.avg)]">
          <div class="text-xs text-slate-500">平均位置</div>
          <div :class="tierColor(summary.avg)" class="text-2xl font-bold">{{ summary.avg }}%</div>
          <div class="text-[11px] text-slate-500">{{ tierLabel(summary.avg) }}</div>
        </div>
        <RouterLink
          :to="`/stock/${summary.cheapest.code}`"
          class="p-3 border border-emerald-200 bg-emerald-50 hover:border-emerald-400 transition block"
        >
          <div class="text-xs text-slate-500">最便宜</div>
          <div class="font-bold leading-tight">{{ summary.cheapest.name }}</div>
          <div class="text-xs font-mono text-slate-500">{{ summary.cheapest.code }}</div>
          <div class="text-emerald-700 font-bold mt-1">{{ summary.cheapest.position }}%</div>
        </RouterLink>
        <RouterLink
          :to="`/stock/${summary.priciest.code}`"
          class="p-3 border border-red-200 bg-red-50 hover:border-red-400 transition block"
        >
          <div class="text-xs text-slate-500">最貴</div>
          <div class="font-bold leading-tight">{{ summary.priciest.name }}</div>
          <div class="text-xs font-mono text-slate-500">{{ summary.priciest.code }}</div>
          <div class="text-red-600 font-bold mt-1">{{ summary.priciest.position }}%</div>
        </RouterLink>
      </div>
      <p class="text-[11px] text-slate-500 mt-2 leading-snug">
        位置 0% 表示落在「便宜價」、100% 表示落在「昂貴價」。優先用 PE 法估值帶（成長股），無 EPS 時退回殖利率法。
      </p>
    </section>

    <!-- Empty state -->
    <div v-if="entries.length === 0" class="text-slate-500 py-8 text-center bg-white border border-dashed border-[#d8d8d2]">
      還沒加入自選股<br>
      <span class="text-xs">可從清單頁的個股詳情點「加入自選」，或在上方手動輸入代號</span>
    </div>

    <!-- Watchlist rows -->
    <div v-else class="space-y-2">
      <div
        v-for="e in entries"
        :key="e.code"
        class="bg-white border border-[#e7e7e1] overflow-hidden"
      >
        <div class="px-4 py-3 flex items-center justify-between gap-3">
          <RouterLink :to="`/stock/${e.code}`" class="flex-1 hover:opacity-70 min-w-0">
            <div class="flex items-baseline gap-2">
              <div class="font-mono text-xs text-slate-500 shrink-0">{{ e.code }}</div>
              <div class="font-medium truncate">{{ e.name || '（自訂）' }}</div>
            </div>
            <div v-if="e.loaded" class="text-xs text-slate-500 mt-0.5">
              {{ fmt(e.price) }}
              <span v-if="e.change_pct != null" :class="e.change_pct >= 0 ? 'text-red-500' : 'text-emerald-600'">
                ({{ e.change_pct >= 0 ? '+' : '' }}{{ fmt(e.change_pct, 2) }}%)
              </span>
              <span v-if="e.method" class="ml-1.5 text-[10px] px-1 py-0.5 rounded bg-slate-100 text-slate-600 uppercase">{{ e.method }}</span>
            </div>
            <div v-else class="text-xs text-slate-400 mt-0.5">未預載資料 — 點擊查看</div>
          </RouterLink>
          <div v-if="e.position != null" class="text-right shrink-0">
            <div :class="tierColor(e.position)" class="text-lg font-bold leading-none">{{ e.position }}%</div>
            <div class="text-[10px] text-slate-500 mt-0.5">{{ tierLabel(e.position) }}</div>
          </div>
          <button
            @click="watchlist.remove(e.code)"
            class="text-slate-400 hover:text-red-500 transition px-1 text-xl shrink-0"
            aria-label="移除"
          >×</button>
        </div>
        <!-- Position bar -->
        <div v-if="e.position != null && e.bands" class="px-4 pb-3">
          <div class="relative h-2 rounded-full bg-gradient-to-r from-emerald-300 via-amber-200 to-red-300 overflow-visible">
            <div
              class="absolute top-1/2 -translate-y-1/2 w-1 h-4 bg-slate-900 rounded"
              :style="{ left: `${Math.max(0, Math.min(100, e.position))}%` }"
              title="目前位置"
            ></div>
          </div>
          <div class="flex justify-between text-[10px] text-slate-400 mt-1 font-mono">
            <span>{{ fmt(e.bands.cheap) }}</span>
            <span>{{ fmt(e.bands.fair) }}</span>
            <span>{{ fmt(e.bands.expensive) }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
