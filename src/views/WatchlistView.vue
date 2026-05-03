<script setup>
import { ref, onMounted, computed } from 'vue'
import { useWatchlistStore } from '../stores/watchlist'

const watchlist = useWatchlistStore()
const stocks = ref(null)
const customCode = ref('')
const errMsg = ref('')

// Allow 4-6 alphanumeric (TW: 2330, 0050, 00878 / US ADR: TSM, UMC)
const CODE_RE = /^[0-9A-Z]{2,6}$/

onMounted(async () => {
  const res = await fetch(`${import.meta.env.BASE_URL}data/stocks.json`)
  stocks.value = await res.json()
})

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

const myStocks = computed(() => watchlist.codes)
</script>

<template>
  <div>
    <h1 class="text-2xl font-bold mb-1">自選股</h1>
    <p class="text-sm text-slate-500 mb-4">手動加入任意股票代號（台股 4 碼，例：2330）</p>

    <div class="flex gap-2 mb-1">
      <input
        v-model="customCode"
        @keyup.enter="addCustom"
        @input="errMsg = ''"
        type="text"
        placeholder="輸入股票代號…"
        class="flex-1 px-3 py-2 rounded-lg border border-slate-300 focus:outline-none focus:ring-2 focus:ring-sky-500 bg-white"
      />
      <button
        @click="addCustom"
        class="px-4 py-2 bg-sky-600 text-white rounded-lg hover:bg-sky-700 transition font-medium"
      >新增</button>
    </div>
    <p v-if="errMsg" class="text-sm text-red-600 mb-4">{{ errMsg }}</p>
    <div v-else class="mb-4"></div>

    <div v-if="myStocks.length === 0" class="text-slate-500 py-8 text-center bg-white rounded-lg border border-dashed border-slate-300">
      還沒加入自選股<br>
      <span class="text-xs">可從清單頁的個股詳情點「加入自選」，或在上方手動輸入代號</span>
    </div>
    <div v-else class="space-y-2">
      <div
        v-for="code in myStocks"
        :key="code"
        class="bg-white rounded-lg shadow-sm border border-slate-200 px-4 py-3 flex items-center justify-between"
      >
        <RouterLink :to="`/stock/${code}`" class="flex-1 hover:opacity-70">
          <div class="font-mono text-xs text-slate-500">{{ code }}</div>
          <div class="font-medium">{{ stocks?.tw_stocks?.[code]?.name || '（自訂）' }}</div>
        </RouterLink>
        <button
          @click="watchlist.remove(code)"
          class="text-slate-400 hover:text-red-500 transition px-2 text-xl"
          aria-label="移除"
        >×</button>
      </div>
    </div>
  </div>
</template>
