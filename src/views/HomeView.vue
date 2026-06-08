<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { useWatchlistStore } from '../stores/watchlist'
import { useAlertsStore } from '../stores/alerts'
import { computeFreshness } from '../lib/freshness.js'
import { positionPct, preferredBands, positionTier, clampPct } from '../lib/position.js'

const watchlist = useWatchlistStore()
const alerts = useAlertsStore()
const lastUpdated = inject('lastUpdated', ref({}))

const stocks = ref(null)
const loading = ref(true)
const error = ref(null)
const search = ref('')
const sortByCheap = ref(false)
const priced = ref(new Map()) // code -> stock JSON (current price + valuation bands)

// Day-scale thresholds so a normal weekend gap does NOT show as stale.
const freshness = computed(() =>
  computeFreshness(lastUpdated.value.tw, {
    warnHours: 80,   // ~3.3 days
    staleHours: 168, // 7 days → red
    staleNote: '資料可能過期，請查 GitHub Actions',
  })
)

onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/stocks.json`)
    stocks.value = await res.json()
    // Background-load each preloaded stock's valuation so the list can show a
    // cheapness bar — turns the catalog into a scannable decision panel. Cards
    // render immediately; bars fill in as data arrives.
    const codes = new Set()
    for (const cat of Object.values(stocks.value.categories)) cat.stocks.forEach((c) => codes.add(c))
    watchlist.codes.forEach((c) => codes.add(c))
    Object.keys(alerts.targets).forEach((c) => codes.add(c)) // so alerts on any code get checked
    loadPrices([...codes])
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

async function loadPrices(codes) {
  await Promise.all(codes.map(async (code) => {
    if (priced.value.has(code)) return
    try {
      const res = await fetch(`${import.meta.env.BASE_URL}data/tw/${code}.json`)
      if (!res.ok) return
      const data = await res.json()
      // Read priced.value AFTER the await, then copy-set-assign atomically.
      // (Capturing the Map before the await races under 26 concurrent fetches —
      //  each would mutate a stale copy and lose all but the last update.)
      const next = new Map(priced.value)
      next.set(code, data)
      priced.value = next
    } catch { /* not preloaded — skip */ }
  }))
}

// code -> { price, change_pct, pct (0..100 within cheap↔expensive), tier, bar }
const posByCode = computed(() => {
  const m = {}
  for (const [code, d] of priced.value) {
    const pb = preferredBands(d)
    const pct = pb ? positionPct(d.current_price, pb.bands) : null
    m[code] = {
      price: d.current_price,
      change_pct: d.change_pct,
      pct,
      tier: positionTier(pct),
      bar: clampPct(pct),
    }
  }
  return m
})

function matchesSearch(code) {
  const q = search.value.trim().toLowerCase()
  if (!q) return true
  const meta = stocks.value.tw_stocks[code]
  return code.toLowerCase().includes(q) || meta?.name?.toLowerCase().includes(q)
}

// Flat, de-duplicated, search-filtered, sorted cheapest → expensive (unknown last).
const sortedStocks = computed(() => {
  if (!stocks.value) return []
  const seen = new Set()
  const codes = []
  for (const cat of Object.values(stocks.value.categories)) {
    for (const c of cat.stocks) {
      if (seen.has(c)) continue
      seen.add(c)
      if (matchesSearch(c)) codes.push(c)
    }
  }
  return codes.sort((a, b) => {
    const pa = posByCode.value[a]?.pct
    const pb = posByCode.value[b]?.pct
    if (pa == null && pb == null) return 0
    if (pa == null) return 1
    if (pb == null) return -1
    return pa - pb
  })
})

// Alerts whose target is reached (latest close ≤ target). posByCode only holds
// fetched codes; onMounted also fetches alerted codes so every alert is checked.
const triggeredAlerts = computed(() => {
  if (!stocks.value) return []
  const out = []
  for (const [code, target] of Object.entries(alerts.targets)) {
    const p = posByCode.value[code]?.price
    if (p != null && p <= target) {
      out.push({ code, name: stocks.value.tw_stocks[code]?.name || code, price: p, target })
    }
  }
  return out
})

const filteredCategories = computed(() => {
  if (!stocks.value) return []
  if (sortByCheap.value) {
    return [{ key: '_sorted', label: '依便宜度（便宜 → 昂貴）', stocks: sortedStocks.value, isWatchlist: false }]
  }
  const cats = []
  if (watchlist.codes.length > 0) {
    cats.push({ key: '_watchlist', label: '自選', stocks: [...watchlist.codes], isWatchlist: true })
  }
  for (const [key, cat] of Object.entries(stocks.value.categories)) {
    cats.push({ key, label: cat.label, stocks: cat.stocks, isWatchlist: false })
  }
  return cats
    .map((c) => ({ ...c, stocks: c.stocks.filter(matchesSearch) }))
    .filter((c) => c.stocks.length > 0)
})
</script>

<template>
  <div>
    <!-- Page header: tighter, single-line. No marketing copy. -->
    <div class="mb-5 flex items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">股票清單</h1>
        <p class="text-sm text-slate-500 mt-1">點選任一股票查看 三價 估值</p>
        <span v-if="freshness"
              class="inline-block mt-1.5 px-2 py-0.5 rounded border text-[11px] font-medium"
              :class="freshness.cls">
          資料 {{ freshness.label }}
        </span>
      </div>
      <div class="flex flex-col items-end gap-1.5 shrink-0">
        <button
          @click="sortByCheap = !sortByCheap"
          class="text-xs px-2.5 py-1 rounded border transition"
          :class="sortByCheap ? 'border-[#0a0e16] bg-[#0a0e16] text-white' : 'border-[#d8d8d2] text-slate-600 hover:border-[#0a0e16]'"
        >
          {{ sortByCheap ? '✓ 依便宜度' : '依便宜度排序' }}
        </button>
        <span class="text-xs text-slate-500 font-mono uppercase tracking-wider hidden sm:block">
          {{ stocks ? Object.values(stocks.categories).reduce((s, c) => s + c.stocks.length, 0) : '—' }} 檔預載
        </span>
      </div>
    </div>

    <!-- 到價提醒：有目標價達成時置頂提醒（純前端、開 app 時比對） -->
    <div v-if="triggeredAlerts.length" class="mb-4 px-3 py-2.5 rounded border border-amber-300 bg-amber-50">
      <div class="text-sm font-semibold text-amber-800 mb-1">🔔 {{ triggeredAlerts.length }} 檔已到價（跌破你設的目標）</div>
      <div class="flex flex-wrap gap-x-4 gap-y-1">
        <RouterLink
          v-for="a in triggeredAlerts"
          :key="a.code"
          :to="`/stock/${a.code}`"
          class="text-xs text-amber-900 hover:underline font-mono"
        >{{ a.code }} {{ a.name }} · {{ a.price.toFixed(2) }} ≤ {{ a.target.toFixed(2) }}</RouterLink>
      </div>
    </div>

    <input
      v-model="search"
      type="search"
      placeholder="搜尋代號或名稱"
      class="w-full mb-5 px-3.5 py-2.5 rounded border border-[#d8d8d2] bg-white text-base focus:outline-none focus:border-[#0a0e16] focus:ring-1 focus:ring-[#0a0e16]/20 transition"
    />

    <!-- Loading skeleton -->
    <div v-if="loading">
      <div class="space-y-5">
        <div v-for="n in 2" :key="n">
          <div class="skel h-4 w-20 mb-2"></div>
          <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
            <div v-for="m in 4" :key="m" class="skel h-14"></div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="error" class="text-red-600 py-8 text-sm">載入失敗：{{ error }}</div>

    <div v-else-if="stocks">
      <div v-for="cat in filteredCategories" :key="cat.key" class="mb-6">
        <div class="flex items-baseline justify-between mb-2">
          <h2
            class="text-sm uppercase tracking-[0.16em] font-semibold flex items-baseline gap-2"
            :class="cat.isWatchlist ? 'text-amber-700' : 'text-slate-600'"
          >
            <span v-if="cat.isWatchlist" class="text-amber-500">◆</span>
            {{ cat.label }}
            <span class="text-xs font-mono text-slate-400 normal-case tracking-normal">{{ cat.stocks.length }}</span>
          </h2>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          <RouterLink
            v-for="code in cat.stocks"
            :key="cat.key + '-' + code"
            :to="`/stock/${code}`"
            class="bg-white px-3 py-2.5 border transition relative group"
            :class="cat.isWatchlist
              ? 'border-amber-200 hover:border-amber-500 hover:bg-amber-50/50'
              : 'border-[#e7e7e1] hover:border-[#0a0e16] hover:bg-slate-50/50'"
          >
            <span
              v-if="!cat.isWatchlist && watchlist.has(code)"
              class="absolute top-1.5 right-2 text-xs text-amber-500"
              title="已加入自選"
            >◆</span>
            <div class="font-mono text-xs text-slate-500 leading-none">{{ code }}</div>
            <div class="font-medium text-base truncate mt-1.5 leading-tight">
              {{ stocks.tw_stocks[code]?.name || '(自訂代號)' }}
            </div>
            <div v-if="stocks.tw_stocks[code]?.adr" class="text-xs text-slate-500 mt-1 font-mono">
              ADR · {{ stocks.tw_stocks[code].adr }}
            </div>
            <!-- cheapness position bar (fills in once valuation loads in background) -->
            <div v-if="posByCode[code]?.pct != null" class="mt-2">
              <div class="flex items-baseline justify-between text-[10px] leading-none mb-1">
                <span :class="posByCode[code].tier.text" class="font-semibold">{{ posByCode[code].tier.label }} · {{ posByCode[code].pct }}%</span>
                <span v-if="posByCode[code].change_pct != null"
                      :class="posByCode[code].change_pct >= 0 ? 'text-red-500' : 'text-emerald-600'"
                      class="font-mono">
                  {{ posByCode[code].change_pct >= 0 ? '+' : '' }}{{ posByCode[code].change_pct }}%
                </span>
              </div>
              <div class="h-1 bg-slate-200 rounded-full relative overflow-hidden" title="0% = 便宜價, 100% = 昂貴價">
                <div class="absolute inset-y-0 left-0 rounded-full" :class="posByCode[code].tier.bar" :style="{ width: posByCode[code].bar + '%' }"></div>
              </div>
            </div>
          </RouterLink>
        </div>
      </div>
      <div v-if="filteredCategories.length === 0" class="text-slate-500 py-8 text-center text-sm">
        找不到符合的股票
      </div>
    </div>
  </div>
</template>
