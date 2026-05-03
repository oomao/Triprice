<script setup>
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'

const data = ref(null)
const loading = ref(true)
const error = ref(null)

const search = ref('')
const categoryFilter = ref('all')
const sortKey = ref('total')
const sortDir = ref('desc')

const CATEGORIES = [
  { v: 'all', label: '全部' },
  { v: 'tw_market', label: '台股大盤' },
  { v: 'dividend', label: '高股息' },
  { v: 'us_tech', label: '美股/科技' },
  { v: 'foreign', label: '海外' },
  { v: 'other', label: '其他' },
]

const SORT_KEYS = [
  { v: 'total', label: '綜合分' },
  { v: 'yield_pct', label: '殖利率' },
  { v: 'return_1y', label: '1Y 報酬' },
  { v: 'avg_turnover', label: '日均成交' },
  { v: 'volatility', label: '波動度' },
  { v: 'current_price', label: '現價' },
]

onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/etf_list.json`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function get(e, key) {
  if (key === 'total') return e.scores?.total
  return e[key]
}

const filtered = computed(() => {
  if (!data.value?.etfs) return []
  const q = search.value.trim().toLowerCase()
  let arr = data.value.etfs.filter((e) => {
    if (categoryFilter.value !== 'all' && e.category !== categoryFilter.value) return false
    if (!q) return true
    return e.code.toLowerCase().includes(q) || (e.name || '').toLowerCase().includes(q)
  })
  arr = [...arr].sort((a, b) => {
    const av = get(a, sortKey.value)
    const bv = get(b, sortKey.value)
    if (av == null && bv == null) return 0
    if (av == null) return 1
    if (bv == null) return -1
    return sortDir.value === 'desc' ? bv - av : av - bv
  })
  return arr
})

function setSort(key) {
  if (sortKey.value === key) {
    sortDir.value = sortDir.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortKey.value = key
    sortDir.value = 'desc'
  }
}

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  })
}

function fmtTurnover(n) {
  if (n == null || isNaN(n)) return '—'
  // 億 = 1e8 NTD
  if (n >= 1e8) return `${(n / 1e8).toFixed(1)} 億`
  if (n >= 1e4) return `${(n / 1e4).toFixed(0)} 萬`
  return Math.round(n).toLocaleString()
}

function scoreColor(s) {
  if (s == null) return 'text-slate-400'
  if (s >= 70) return 'text-emerald-600 font-bold'
  if (s >= 50) return 'text-[#0a0e16]'
  if (s >= 30) return 'text-amber-600'
  return 'text-red-500'
}

function categoryLabel(c) {
  return CATEGORIES.find((x) => x.v === c)?.label || c
}

function categoryBadge(c) {
  switch (c) {
    case 'tw_market': return 'bg-[#0a0e16]/10 text-[#0a0e16]'
    case 'dividend':  return 'bg-emerald-100 text-emerald-700'
    case 'us_tech':   return 'bg-violet-100 text-violet-700'
    case 'foreign':   return 'bg-amber-100 text-amber-700'
    default:          return 'bg-slate-100 text-slate-600'
  }
}
</script>

<template>
  <div>
    <div class="flex items-baseline justify-between mb-3 flex-wrap gap-2">
      <h1 class="text-xl font-bold tracking-tight">ETF 全覽</h1>
      <span v-if="data" class="text-xs text-slate-500">
        共 {{ data.count }} 檔 · 更新 {{ data.updated?.replace(/:\d{2}\+\d{2}:\d{2}$/, '') }}
      </span>
    </div>
    <p class="text-sm text-slate-500 mb-4 leading-relaxed">
      綜合分 = 殖利率 / 1Y 報酬 / 規模（日均成交）/ 穩定度（年化波動倒數）四項相對排名等權平均。
      <strong>分數為相對性的排名，不是絕對好壞</strong>。預設過濾掉債券 ETF 和槓桿型。
    </p>

    <div v-if="loading" class="text-slate-500 py-8 text-center">載入中…</div>
    <div v-else-if="error" class="bg-red-50 border border-red-200 p-4 text-sm border text-slate-700">
      載入失敗：{{ error }}
    </div>
    <div v-else-if="!data" class="bg-amber-50 border border-amber-200 p-4 text-sm border">
      尚無 ETF 資料 — 請執行 <code class="text-xs">python scripts/fetch_etf.py</code> 後重試。
    </div>
    <div v-else>
      <!-- Filters -->
      <div class="bg-white border border-[#e7e7e1] p-3 mb-4 grid sm:grid-cols-3 gap-3">
        <div class="sm:col-span-2">
          <label class="block text-xs font-semibold text-slate-700 mb-1">搜尋（代號 / 名稱）</label>
          <input
            v-model="search"
            type="text"
            placeholder="例：0050、台灣 50、半導體"
            class="w-full px-3 py-1.5 rounded border border-slate-300 text-sm focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16]"
          />
        </div>
        <div>
          <label class="block text-xs font-semibold text-slate-700 mb-1">分類</label>
          <select
            v-model="categoryFilter"
            class="w-full px-3 py-1.5 rounded border border-slate-300 text-sm bg-white focus:outline-none focus:ring-1 focus:ring-[#0a0e16]/30 focus:border-[#0a0e16]"
          >
            <option v-for="c in CATEGORIES" :key="c.v" :value="c.v">{{ c.label }}</option>
          </select>
        </div>
      </div>

      <!-- Mobile sort dropdown -->
      <div class="sm:hidden mb-3">
        <select
          :value="`${sortKey}:${sortDir}`"
          @change="(e) => { const [k, d] = e.target.value.split(':'); sortKey = k; sortDir = d }"
          class="w-full px-3 py-2 rounded border border-slate-300 text-sm bg-white"
        >
          <option v-for="k in SORT_KEYS" :key="k.v + '_d'" :value="`${k.v}:desc`">{{ k.label }} ↓</option>
          <option v-for="k in SORT_KEYS" :key="k.v + '_a'" :value="`${k.v}:asc`">{{ k.label }} ↑</option>
        </select>
      </div>

      <div class="text-xs text-slate-500 mb-2">符合：{{ filtered.length }} 檔</div>

      <!-- Table -->
      <div class="bg-white border border-[#e7e7e1] overflow-hidden">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="bg-slate-50 text-slate-600 text-xs">
                <th class="px-3 py-2 text-left font-semibold">代號 / 名稱</th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden sm:table-cell" @click="setSort('current_price')">
                  現價<span v-if="sortKey === 'current_price'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100" @click="setSort('return_1y')">
                  1Y 報酬<span v-if="sortKey === 'return_1y'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100" @click="setSort('yield_pct')">
                  殖利率<span v-if="sortKey === 'yield_pct'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden md:table-cell" @click="setSort('avg_turnover')">
                  日均成交<span v-if="sortKey === 'avg_turnover'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100 hidden md:table-cell" @click="setSort('volatility')">
                  波動度<span v-if="sortKey === 'volatility'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
                <th class="px-3 py-2 text-right font-semibold cursor-pointer hover:bg-slate-100" @click="setSort('total')">
                  綜合分<span v-if="sortKey === 'total'">{{ sortDir === 'desc' ? ' ↓' : ' ↑' }}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="e in filtered"
                :key="e.code"
                class="border-t border-slate-100 hover:bg-slate-50 transition"
              >
                <td class="px-3 py-2.5">
                  <RouterLink :to="`/stock/${e.code}`" class="block group">
                    <div class="font-mono text-slate-500 text-xs">{{ e.code }}</div>
                    <div class="font-semibold group-hover:text-[#b4530b] transition leading-tight">{{ e.name }}</div>
                    <span :class="['inline-block text-[10px] px-1.5 py-0.5 rounded mt-0.5', categoryBadge(e.category)]">
                      {{ categoryLabel(e.category) }}
                    </span>
                  </RouterLink>
                </td>
                <td class="px-3 py-2.5 text-right hidden sm:table-cell font-mono">{{ fmt(e.current_price) }}</td>
                <td class="px-3 py-2.5 text-right font-mono"
                  :class="e.return_1y == null ? '' : (e.return_1y >= 0 ? 'text-red-500' : 'text-emerald-600')"
                >
                  <span v-if="e.return_1y != null">{{ e.return_1y >= 0 ? '+' : '' }}{{ fmt(e.return_1y, 1) }}%</span>
                  <span v-else-if="e.split_detected" class="text-slate-400 text-xs" title="近 1 年內偵測到單日下跌 > 30%（疑似分割/減資），FinMind 免費版無法調整還原">N/A*</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5 text-right font-mono">
                  <span v-if="e.yield_pct">{{ fmt(e.yield_pct) }}%</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5 text-right font-mono hidden md:table-cell text-xs">{{ fmtTurnover(e.avg_turnover) }}</td>
                <td class="px-3 py-2.5 text-right font-mono hidden md:table-cell">
                  <span v-if="e.volatility != null">{{ fmt(e.volatility, 1) }}%</span>
                  <span v-else class="text-slate-400">—</span>
                </td>
                <td class="px-3 py-2.5 text-right" :class="scoreColor(e.scores?.total)">
                  {{ e.scores?.total != null ? fmt(e.scores.total, 0) : '—' }}
                </td>
              </tr>
              <tr v-if="!filtered.length">
                <td colspan="7" class="text-center text-slate-400 py-6 text-sm">無符合的 ETF</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Methodology -->
      <details class="mt-4 group">
        <summary class="cursor-pointer text-xs text-[#b4530b] hover:text-[#0a0e16] select-none">
          <span class="inline-block transition-transform group-open:rotate-90 mr-1">▶</span>
          綜合分計算方式
        </summary>
        <div class="mt-2 bg-slate-50 border border-slate-200 rounded p-3 text-xs leading-relaxed text-slate-600 space-y-1">
          <p><strong>四個維度，每個 0~100 分（相對排名，min-max normalize），等權平均得綜合分。</strong></p>
          <p>• <strong>殖利率分</strong>：TTM 現金股利 ÷ 現價，越高越好</p>
          <p>• <strong>1Y 報酬分</strong>：近 1 年含息報酬，越高越好</p>
          <p>• <strong>規模分</strong>：近 60 日平均成交金額（log 轉換），越高越好（流動性好）</p>
          <p>• <strong>穩定度分</strong>：年化波動度（日報酬 std × √250），越低越好</p>
          <p class="pt-1 text-slate-500">分母為當前清單範圍內的 ETF — 換言之，這是「同儕中的相對排名」，不是絕對標準。費用率因 FinMind 不提供，未納入評分。</p>
          <p class="text-slate-500"><strong>* N/A 標示</strong>：近 1 年內偵測到單日下跌 &gt; 30%（疑似股票分割或減資，例 0050 於 2024-12 進行 1:4 分割）。FinMind 免費版未提供調整還原價，因此跳過該檔的 1Y 報酬分數，避免誤導。</p>
        </div>
      </details>
    </div>
  </div>
</template>
