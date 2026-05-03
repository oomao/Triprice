<script setup>
import { ref, onMounted, computed } from 'vue'
import { useWatchlistStore } from '../stores/watchlist'

const watchlist = useWatchlistStore()
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

const filteredCategories = computed(() => {
  if (!stocks.value) return []
  const q = search.value.trim().toLowerCase()
  return Object.entries(stocks.value.categories).map(([key, cat]) => ({
    key,
    label: cat.label,
    stocks: cat.stocks.filter((code) => {
      if (!q) return true
      const meta = stocks.value.tw_stocks[code]
      return code.includes(q) || meta?.name?.toLowerCase().includes(q)
    })
  })).filter((c) => c.stocks.length > 0)
})
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-1">股票清單</h1>
    <p class="text-sm text-slate-500 mb-4">點選任一股票查看便宜 / 合理 / 昂貴價</p>

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
        <h2 class="text-base font-semibold text-slate-700 mb-2">{{ cat.label }}</h2>
        <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
          <RouterLink
            v-for="code in cat.stocks"
            :key="code"
            :to="`/stock/${code}`"
            class="bg-white rounded-lg px-3 py-2 shadow-sm hover:shadow-md hover:border-sky-400 transition border border-slate-200 relative"
          >
            <span
              v-if="watchlist.has(code)"
              class="absolute top-1 right-2 text-xs text-amber-500"
              title="已加入自選"
            >★</span>
            <div class="font-mono text-xs text-slate-500">{{ code }}</div>
            <div class="font-medium text-sm truncate">{{ stocks.tw_stocks[code]?.name }}</div>
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
