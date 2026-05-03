<script setup>
import { ref, onMounted, computed, inject } from 'vue'
import { useWatchlistStore } from '../stores/watchlist'

const watchlist = useWatchlistStore()
const lastUpdated = inject('lastUpdated', ref({}))

const stocks = ref(null)
const loading = ref(true)
const error = ref(null)
const search = ref('')

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

function fmtTime(iso) {
  if (!iso) return ''
  return iso.replace(/:\d{2}\+\d{2}:\d{2}$/, '').replace('T', ' ')
}

const filteredCategories = computed(() => {
  if (!stocks.value) return []
  const cats = []

  // Watchlist as first category if user has any
  if (watchlist.codes.length > 0) {
    cats.push({
      key: '_watchlist',
      label: '★ 自選',
      stocks: [...watchlist.codes],
      isWatchlist: true,
    })
  }

  for (const [key, cat] of Object.entries(stocks.value.categories)) {
    cats.push({ key, label: cat.label, stocks: cat.stocks, isWatchlist: false })
  }

  const q = search.value.trim().toLowerCase()
  return cats.map((c) => ({
    ...c,
    stocks: c.stocks.filter((code) => {
      if (!q) return true
      const meta = stocks.value.tw_stocks[code]
      return code.toLowerCase().includes(q) || meta?.name?.toLowerCase().includes(q)
    }),
  })).filter((c) => c.stocks.length > 0)
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-1">股票清單</h1>
    <p class="text-sm text-slate-500 mb-2">點選任一股票查看便宜 / 合理 / 昂貴價</p>

    <!-- 資料更新時間 banner -->
    <div
      v-if="lastUpdated.tw || lastUpdated.us"
      class="mb-4 text-xs text-slate-600 bg-sky-50 border border-sky-200 rounded px-3 py-2 flex flex-wrap gap-x-4 gap-y-1"
    >
      <span v-if="lastUpdated.tw">
        <span class="text-slate-500">台股資料更新：</span>
        <strong class="font-mono">{{ fmtTime(lastUpdated.tw) }}</strong>
      </span>
      <span v-if="lastUpdated.us">
        <span class="text-slate-500">ADR 資料更新：</span>
        <strong class="font-mono">{{ fmtTime(lastUpdated.us) }}</strong>
      </span>
    </div>

    <input
      v-model="search"
      type="search"
      placeholder="搜尋代號或名稱…"
      class="w-full mb-5 px-4 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
    />

    <div v-if="loading" class="text-slate-500 py-8 text-center">載入中…</div>
    <div v-else-if="error" class="text-red-600 py-8 text-center">載入失敗：{{ error }}</div>
    <div v-else-if="stocks">
      <div v-for="cat in filteredCategories" :key="cat.key" class="mb-6">
        <h2
          class="text-base font-semibold mb-2 flex items-center gap-2"
          :class="cat.isWatchlist ? 'text-amber-700' : 'text-slate-700'"
        >
          {{ cat.label }}
          <span class="text-xs font-normal text-slate-400">({{ cat.stocks.length }})</span>
        </h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          <RouterLink
            v-for="code in cat.stocks"
            :key="cat.key + '-' + code"
            :to="`/stock/${code}`"
            class="bg-white rounded-lg px-3 py-2 shadow-sm hover:shadow-md hover:border-sky-400 transition border relative"
            :class="cat.isWatchlist
              ? 'border-amber-200 hover:border-amber-400'
              : 'border-slate-200'"
          >
            <span
              v-if="!cat.isWatchlist && watchlist.has(code)"
              class="absolute top-1 right-2 text-xs text-amber-500"
              title="已加入自選"
            >★</span>
            <div class="font-mono text-xs text-slate-500">{{ code }}</div>
            <div class="font-medium text-sm truncate">
              {{ stocks.tw_stocks[code]?.name || '(自訂代號)' }}
            </div>
            <div v-if="stocks.tw_stocks[code]?.adr" class="text-xs text-sky-600 mt-0.5">
              ADR: {{ stocks.tw_stocks[code].adr }}
            </div>
          </RouterLink>
        </div>
      </div>
      <div v-if="filteredCategories.length === 0" class="text-slate-500 py-8 text-center">
        找不到符合的股票
      </div>
    </div>
  </div>
</template>
