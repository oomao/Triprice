<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { useWatchlistStore } from '../stores/watchlist'
import { computeFreshness } from '../lib/freshness.js'

const watchlist = useWatchlistStore()
const lastUpdated = inject('lastUpdated', ref({}))

const stocks = ref(null)
const loading = ref(true)
const error = ref(null)
const search = ref('')

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
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

const filteredCategories = computed(() => {
  if (!stocks.value) return []
  const cats = []

  if (watchlist.codes.length > 0) {
    cats.push({
      key: '_watchlist',
      label: '自選',
      stocks: [...watchlist.codes],
      isWatchlist: true,
    })
  }

  for (const [key, cat] of Object.entries(stocks.value.categories)) {
    cats.push({ key, label: cat.label, stocks: cat.stocks, isWatchlist: false })
  }

  const q = search.value.trim().toLowerCase()
  return cats
    .map((c) => ({
      ...c,
      stocks: c.stocks.filter((code) => {
        if (!q) return true
        const meta = stocks.value.tw_stocks[code]
        return code.toLowerCase().includes(q) || meta?.name?.toLowerCase().includes(q)
      }),
    }))
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
      <div class="text-xs text-slate-500 font-mono uppercase tracking-wider hidden sm:block">
        {{ stocks ? Object.values(stocks.categories).reduce((s, c) => s + c.stocks.length, 0) : '—' }} 檔預載
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
          </RouterLink>
        </div>
      </div>
      <div v-if="filteredCategories.length === 0" class="text-slate-500 py-8 text-center text-sm">
        找不到符合的股票
      </div>
    </div>
  </div>
</template>
