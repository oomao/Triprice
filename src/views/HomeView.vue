<script setup>
import { ref, computed, onMounted, inject, watch } from 'vue'
import { useRoute, useRouter, RouterLink } from 'vue-router'
import { useWatchlistStore } from '../stores/watchlist'
import { useAlertsStore } from '../stores/alerts'
import { computeFreshness, TW_SCHEDULE } from '../lib/freshness.js'
import { fetchData } from '../lib/data.js'
import { getCached } from '../lib/finmind.js'
import { valuationView, TIER_ORDER, tierByKey, METHOD_LABEL } from '../lib/position.js'
import ValuationScale from '../components/ValuationScale.vue'

// 總覽: the decision surface. One sortable table of every preloaded stock plus the
// user's custom watchlist codes, with where each price sits in its valuation band,
// how far it is from fair value, and today's context (data date, TAIEX, ADR signal).
const route = useRoute()
const router = useRouter()
const watchlist = useWatchlistStore()
const alerts = useAlertsStore()
const lastUpdated = inject('lastUpdated', ref({}))

const meta = ref(null)
const market = ref(null)
const signal = ref(null)
const names = ref(null) // data/names.json — only loaded when the watchlist has custom codes
const priced = ref(new Map()) // code -> stock JSON
const loading = ref(true)
const error = ref(null)
const search = ref('')
const tierFilter = ref(null)

// ---- per-viewer view prefs (list / sort); wrapped because storage can throw ----
const PREFS_KEY = 'triprice.overview.v1'
const prefs = (() => {
  try { return JSON.parse(localStorage.getItem(PREFS_KEY) || '{}') } catch { return {} }
})()
const list = ref(route.query.list || prefs.list || 'all') // 'all' | 'watch' | category key
const sortKey = ref(prefs.sortKey || 'pos')
const sortDir = ref(prefs.sortDir || 'asc')
watch([list, sortKey, sortDir], () => {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify({ list: list.value, sortKey: sortKey.value, sortDir: sortDir.value }))
  } catch { /* storage unavailable */ }
})
watch(() => route.query.list, (v) => { if (v) list.value = v })
watch(list, () => { tierFilter.value = null })

const freshness = computed(() =>
  computeFreshness(lastUpdated.value.tw, { schedule: TW_SCHEDULE, staleNote: '資料可能過期' })
)

onMounted(async () => {
  try {
    meta.value = await fetchData('stocks.json')
  } catch (e) {
    error.value = e.message
    loading.value = false
    return
  }
  loading.value = false
  fetchData('market.json', { optional: true }).then((m) => { market.value = m })
  fetchData('adr_signal.json', { optional: true }).then((s) => { signal.value = s })
  const codes = new Set()
  for (const cat of Object.values(meta.value.categories)) cat.stocks.forEach((c) => codes.add(c))
  watchlist.codes.forEach((c) => codes.add(c))
  Object.keys(alerts.targets).forEach((c) => codes.add(c)) // so every alert gets checked
  loadPrices([...codes])
  if (watchlist.codes.some((c) => !meta.value.tw_stocks[c])) {
    fetchData('names.json', { optional: true }).then((n) => { names.value = n?.names || null })
  }
})

// A newly starred custom code (from a stock page) should appear without a reload.
watch(() => watchlist.codes.length, () => {
  if (meta.value) loadPrices(watchlist.codes.filter((c) => !priced.value.has(c)))
})

async function loadPrices(codes) {
  await Promise.all(codes.map(async (code) => {
    if (priced.value.has(code)) return
    // Preloaded → static JSON; custom code → whatever the stock page last fetched live.
    const data = meta.value.tw_stocks[code]
      ? await fetchData(`tw/${code}.json`, { optional: true })
      : getCached(code)
    if (!data) return
    // Copy-set-assign AFTER the await (capturing the Map earlier loses updates
    // under concurrent fetches — the "26 bars, only 1 shows" bug).
    const next = new Map(priced.value)
    next.set(code, data)
    priced.value = next
  }))
}

// ---- rows ----
const rows = computed(() => {
  if (!meta.value) return []
  const seen = new Set()
  const out = []
  const push = (code, cat) => {
    if (seen.has(code)) return
    seen.add(code)
    const m = meta.value.tw_stocks[code]
    const d = priced.value.get(code)
    out.push({
      code,
      cat,
      order: out.length,
      name: m?.name || names.value?.[code] || (d?.name !== code ? d?.name : null) || null,
      adr: m?.adr || null,
      custom: !m,
      d,
      v: d ? valuationView(d) : null,
    })
  }
  for (const [key, cat] of Object.entries(meta.value.categories)) cat.stocks.forEach((c) => push(c, key))
  watchlist.codes.forEach((c) => push(c, null))
  return out
})

function matchesSearch(r) {
  const q = search.value.trim().toLowerCase()
  if (!q) return true
  return r.code.toLowerCase().includes(q) || (r.name || '').toLowerCase().includes(q)
}

const scoped = computed(() =>
  rows.value.filter((r) => {
    if (list.value === 'watch' && !watchlist.has(r.code)) return false
    if (list.value !== 'all' && list.value !== 'watch' && r.cat !== list.value) return false
    return matchesSearch(r)
  })
)

const SORTS = {
  default: { get: (r) => r.order, dir: 'asc' },
  code: { get: (r) => r.code, dir: 'asc' },
  price: { get: (r) => r.d?.current_price, dir: 'desc' },
  chg: { get: (r) => r.d?.change_pct, dir: 'desc' },
  pos: { get: (r) => r.v?.primary?.pct, dir: 'asc' },
  fair: { get: (r) => r.v?.primary?.bands.fair, dir: 'desc' },
  toFair: { get: (r) => r.v?.primary?.toFair, dir: 'desc' },
  yield: { get: (r) => r.v?.curYield, dir: 'desc' },
  pe: { get: (r) => r.v?.curPe, dir: 'asc' },
}

function setSort(k) {
  if (sortKey.value === k) sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  else {
    sortKey.value = k
    sortDir.value = SORTS[k].dir
  }
}

const visible = computed(() => {
  const s = SORTS[sortKey.value] || SORTS.pos
  const mul = sortDir.value === 'asc' ? 1 : -1
  return scoped.value
    .filter((r) => !tierFilter.value || r.v?.primary?.tier.key === tierFilter.value)
    .slice()
    .sort((a, b) => {
      const va = s.get(a)
      const vb = s.get(b)
      if (va == null && vb == null) return a.order - b.order
      if (va == null) return 1 // unknowns always last
      if (vb == null) return -1
      if (typeof va === 'string') return va.localeCompare(vb) * mul
      return (va - vb) * mul || a.order - b.order
    })
})

// Valuation distribution of the current list (drives the clickable stacked bar).
const distribution = computed(() => {
  const counts = Object.fromEntries(TIER_ORDER.map((k) => [k, 0]))
  let sum = 0
  let n = 0
  let cheapest = null
  for (const r of scoped.value) {
    const p = r.v?.primary
    if (p?.pct == null) continue
    counts[p.tier.key]++
    sum += p.pct
    n++
    if (!cheapest || p.pct < cheapest.v.primary.pct) cheapest = r
  }
  return { counts, n, avg: n ? Math.round(sum / n) : null, cheapest }
})

// ---- header context ----
const closeDate = computed(() => {
  let max = null
  for (const d of priced.value.values()) if (d.close_date && (!max || d.close_date > max)) max = d.close_date
  return max
})
const WEEKDAY = '日一二三四五六'
function fmtDate(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-').map(Number)
  return `${m}/${d}（${WEEKDAY[new Date(y, m - 1, d).getDay()]}）`
}

const taiex = computed(() => market.value?.indices?.TAIEX || null)

const triggeredAlerts = computed(() => {
  const out = []
  for (const [code, target] of Object.entries(alerts.targets)) {
    const d = priced.value.get(code)
    const p = d?.current_price
    if (p != null && p <= target) {
      out.push({ code, name: meta.value?.tw_stocks[code]?.name || d?.name || code, price: p, target })
    }
  }
  return out
})
const alertCount = computed(() => Object.keys(alerts.targets).length)

const listTabs = computed(() => {
  if (!meta.value) return []
  return [
    { key: 'all', label: '全部' },
    { key: 'watch', label: '★ 自選', count: watchlist.codes.length },
    ...Object.entries(meta.value.categories).map(([key, c]) => ({ key, label: c.label })),
  ]
})

// ---- formatting ----
function fmtPrice(n) {
  if (n == null || isNaN(n)) return '—'
  const d = Math.abs(n) >= 1000 ? 0 : Math.abs(n) >= 100 ? 1 : 2
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}
function signed(n, d = 1, suffix = '%') {
  if (n == null || isNaN(n)) return '—'
  return (n > 0 ? '+' : '') + Number(n).toFixed(d) + suffix
}
const upDown = (n) => (n == null ? 'text-slate-400' : n > 0 ? 'text-red-600' : n < 0 ? 'text-emerald-700' : 'text-slate-500')

function openRow(r) {
  router.push(`/stock/${r.code}`)
}

const COLS = 'md:grid-cols-[1.75rem_minmax(8.5rem,1.25fr)_5rem_4.25rem_minmax(11rem,1.8fr)_5rem_4.75rem_3.75rem_3.5rem]'
</script>

<template>
  <div>
    <!-- Title row -->
    <div class="mb-4 flex items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold tracking-tight">總覽</h1>
        <p class="text-sm text-slate-500 mt-0.5">每檔股價落在自己估值帶的哪裡 — 點任一列看完整估值</p>
      </div>
    </div>

    <!-- Context strip: data date · TAIEX · ADR night signal · valuation mix -->
    <div class="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
      <div class="bg-white border border-[#e7e7e1] px-3 py-2.5">
        <div class="text-[10px] uppercase tracking-[0.16em] text-slate-500">資料日期</div>
        <div class="mt-1 text-lg font-bold tnum leading-tight">收盤 {{ fmtDate(closeDate) }}</div>
        <span v-if="freshness" class="inline-block mt-1 px-1.5 py-px rounded border text-[10px] font-medium" :class="freshness.cls">
          {{ freshness.label }}
        </span>
      </div>

      <RouterLink to="/market" class="bg-white border border-[#e7e7e1] px-3 py-2.5 hover:border-[#0a0e16] transition group">
        <div class="text-[10px] uppercase tracking-[0.16em] text-slate-500 flex justify-between">加權指數 <span class="text-slate-400 group-hover:text-slate-700">›</span></div>
        <template v-if="taiex">
          <div class="mt-1 text-lg font-bold tnum leading-tight">{{ taiex.current.toLocaleString('en-US', { maximumFractionDigits: 0 }) }}</div>
          <div class="text-xs font-mono mt-0.5" :class="upDown(taiex.change_pct)">
            {{ signed(taiex.change, 0, '') }} ({{ signed(taiex.change_pct, 2) }})
          </div>
        </template>
        <div v-else class="mt-1 text-sm text-slate-400">—</div>
      </RouterLink>

      <RouterLink to="/adr" class="bg-white border border-[#e7e7e1] px-3 py-2.5 hover:border-[#0a0e16] transition group">
        <div class="text-[10px] uppercase tracking-[0.16em] text-slate-500 flex justify-between">夜盤訊號 <span class="text-slate-400 group-hover:text-slate-700">›</span></div>
        <template v-if="signal?.avg_premium_pct != null">
          <div class="mt-1 text-lg font-bold leading-tight" :class="upDown(signal.avg_premium_pct)">{{ signal.signal_label }}</div>
          <div class="text-xs font-mono mt-0.5 text-slate-500">
            ADR 溢價 <span :class="upDown(signal.avg_premium_pct)">{{ signed(signal.avg_premium_pct, 2) }}</span>
            <span v-if="signal.sox" class="hidden sm:inline"> · SOX <span :class="upDown(signal.sox.change_pct)">{{ signed(signal.sox.change_pct, 2) }}</span></span>
          </div>
        </template>
        <div v-else class="mt-1 text-sm text-slate-400">—</div>
      </RouterLink>

      <div class="bg-white border border-[#e7e7e1] px-3 py-2.5">
        <div class="text-[10px] uppercase tracking-[0.16em] text-slate-500 flex justify-between">
          估值分布
          <span v-if="distribution.avg != null" class="normal-case tracking-normal font-mono">平均 {{ distribution.avg }}%</span>
        </div>
        <div v-if="distribution.n" class="mt-2 flex h-2.5 rounded-full overflow-hidden gap-px">
          <button
            v-for="k in TIER_ORDER"
            v-show="distribution.counts[k]"
            :key="k"
            type="button"
            class="h-full transition-opacity"
            :class="[tierByKey(k).bar, tierFilter && tierFilter !== k ? 'opacity-30' : '']"
            :style="{ flexGrow: distribution.counts[k] }"
            :title="`${tierByKey(k).label} ${distribution.counts[k]} 檔 — 點擊只看這些`"
            @click="tierFilter = tierFilter === k ? null : k"
          ></button>
        </div>
        <div class="mt-1.5 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px]">
          <button
            v-for="k in TIER_ORDER"
            :key="k"
            type="button"
            class="tnum hover:underline"
            :class="[tierByKey(k).text, tierFilter === k ? 'font-bold underline' : '']"
            @click="tierFilter = tierFilter === k ? null : k"
          >{{ tierByKey(k).short }} {{ distribution.counts[k] }}</button>
        </div>
      </div>
    </div>

    <!-- 到價提醒 -->
    <div v-if="triggeredAlerts.length" class="mb-4 px-3 py-2.5 rounded border border-amber-300 bg-amber-50">
      <div class="text-sm font-semibold text-amber-800 mb-1">🔔 {{ triggeredAlerts.length }} 檔已到價（收盤 ≤ 你設的目標價）</div>
      <div class="flex flex-wrap gap-x-4 gap-y-1">
        <RouterLink
          v-for="a in triggeredAlerts"
          :key="a.code"
          :to="`/stock/${a.code}`"
          class="text-xs text-amber-900 hover:underline font-mono"
        >{{ a.code }} {{ a.name }} · {{ fmtPrice(a.price) }} ≤ {{ fmtPrice(a.target) }}</RouterLink>
      </div>
    </div>

    <!-- List tabs + table filter -->
    <div class="flex flex-col sm:flex-row sm:items-center gap-2 mb-2">
      <div class="flex gap-1 overflow-x-auto no-scrollbar -mx-4 px-4 sm:mx-0 sm:px-0 sm:flex-wrap">
        <button
          v-for="t in listTabs"
          :key="t.key"
          type="button"
          class="shrink-0 px-2.5 py-1 text-xs border rounded-full transition whitespace-nowrap"
          :class="list === t.key
            ? 'bg-[#0a0e16] border-[#0a0e16] text-white'
            : 'border-[#d8d8d2] text-slate-600 hover:border-[#0a0e16] bg-white'"
          @click="list = t.key"
        >
          {{ t.label }}<span v-if="t.count != null" class="ml-1 opacity-60 font-mono">{{ t.count }}</span>
        </button>
      </div>
      <input
        v-model="search"
        type="search"
        placeholder="在清單中篩選…"
        class="sm:ml-auto sm:w-48 px-3 py-1.5 rounded border border-[#d8d8d2] bg-white text-sm focus:outline-none focus:border-[#0a0e16]"
      />
    </div>

    <div v-if="tierFilter" class="mb-2 text-xs text-slate-600 flex items-center gap-2">
      只看 <span class="font-semibold" :class="tierByKey(tierFilter).text">{{ tierByKey(tierFilter).label }}</span>
      <button type="button" class="text-slate-400 hover:text-red-500" @click="tierFilter = null">✕ 清除</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="space-y-1.5">
      <div v-for="n in 8" :key="n" class="skel h-12"></div>
    </div>
    <div v-else-if="error" class="text-red-600 py-8 text-sm">載入失敗：{{ error }}</div>

    <div v-else class="bg-white border border-[#e7e7e1]">
      <!-- Column headers (desktop) -->
      <div class="hidden md:grid items-end gap-x-3 px-3 py-2 border-b border-[#e7e7e1] text-[11px] text-slate-500 select-none" :class="COLS">
        <span></span>
        <button type="button" class="th text-left" @click="setSort('code')">股票<i v-if="sortKey === 'code'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-right" @click="setSort('price')">收盤<i v-if="sortKey === 'price'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-right" @click="setSort('chg')">漲跌<i v-if="sortKey === 'chg'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-left" @click="setSort('pos')" title="0% = 便宜價、50% = 合理價、100% = 昂貴價">估值位置<i v-if="sortKey === 'pos'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-right" @click="setSort('fair')">合理價<i v-if="sortKey === 'fair'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-right" @click="setSort('toFair')" title="現價到合理價還差多少（正 = 低於合理價）">距合理<i v-if="sortKey === 'toFair'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-right" @click="setSort('yield')" title="最近一年現金股利 ÷ 現價">殖利率<i v-if="sortKey === 'yield'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
        <button type="button" class="th text-right" @click="setSort('pe')" title="現價 ÷ 近 4 季 EPS">PE<i v-if="sortKey === 'pe'">{{ sortDir === 'asc' ? '▲' : '▼' }}</i></button>
      </div>

      <!-- Mobile sort control -->
      <div class="md:hidden flex items-center gap-2 px-3 py-2 border-b border-[#e7e7e1] text-xs text-slate-500">
        排序
        <select
          :value="sortKey"
          class="px-2 py-1 border border-[#d8d8d2] bg-white rounded text-xs"
          @change="setSort($event.target.value)"
        >
          <option value="pos">估值位置</option>
          <option value="toFair">距合理價</option>
          <option value="chg">今日漲跌</option>
          <option value="yield">殖利率</option>
          <option value="pe">本益比</option>
          <option value="default">預設分類</option>
        </select>
        <button type="button" class="px-2 py-1 border border-[#d8d8d2] rounded" @click="sortDir = sortDir === 'asc' ? 'desc' : 'asc'">
          {{ sortDir === 'asc' ? '小→大' : '大→小' }}
        </button>
        <span class="ml-auto font-mono">{{ visible.length }} 檔</span>
      </div>

      <div
        v-for="r in visible"
        :key="r.code"
        class="row grid grid-cols-[1.75rem_1fr_auto] items-center gap-x-3 gap-y-1.5 px-3 py-2.5 border-b border-slate-100 last:border-b-0 cursor-pointer hover:bg-slate-50 transition"
        :class="COLS"
        @click="openRow(r)"
      >
        <!-- ★ -->
        <button
          type="button"
          class="text-base leading-none w-7 h-7 -ml-1 flex items-center justify-center rounded hover:bg-amber-50"
          :class="watchlist.has(r.code) ? 'text-amber-500' : 'text-slate-300 hover:text-amber-400'"
          :aria-label="watchlist.has(r.code) ? '移出自選' : '加入自選'"
          :title="watchlist.has(r.code) ? '移出自選' : '加入自選'"
          @click.stop="watchlist.toggle(r.code)"
        >{{ watchlist.has(r.code) ? '★' : '☆' }}</button>

        <!-- name -->
        <div class="min-w-0">
          <RouterLink :to="`/stock/${r.code}`" class="flex items-baseline gap-1.5 min-w-0" @click.stop>
            <span class="font-mono text-[11px] text-slate-500 shrink-0">{{ r.code }}</span>
            <span class="font-medium truncate">{{ r.name || '自訂代號' }}</span>
          </RouterLink>
          <div class="flex items-center gap-1.5 mt-0.5 text-[10px] text-slate-400 leading-none">
            <span v-if="r.adr" class="font-mono">ADR {{ r.adr }}</span>
            <span v-if="alerts.get(r.code) != null" class="text-amber-600" :title="`跌破 ${alerts.get(r.code)} 提醒`">🔔 {{ fmtPrice(alerts.get(r.code)) }}</span>
            <span v-if="r.custom && !r.d">未預載 · 點開即時抓取</span>
            <span v-else-if="r.custom" class="font-mono">即時資料</span>
          </div>
        </div>

        <!-- mobile: price + change -->
        <div class="md:hidden text-right tnum">
          <div class="font-semibold">{{ fmtPrice(r.d?.current_price) }}</div>
          <div class="text-[11px] font-mono" :class="upDown(r.d?.change_pct)">{{ signed(r.d?.change_pct, 2) }}</div>
        </div>

        <!-- desktop: price, change -->
        <div class="hidden md:block text-right tnum font-semibold">{{ fmtPrice(r.d?.current_price) }}</div>
        <div class="hidden md:block text-right text-[13px] font-mono" :class="upDown(r.d?.change_pct)">{{ signed(r.d?.change_pct, 2) }}</div>

        <!-- valuation position -->
        <div class="col-start-2 col-span-2 md:col-start-auto md:col-span-1 min-w-0">
          <template v-if="r.v?.primary?.pct != null">
            <ValuationScale :bands="r.v.primary.bands" :price="r.d.current_price" compact />
            <div class="mt-1 flex items-baseline gap-1.5 text-[11px] leading-none">
              <span class="font-semibold" :class="r.v.primary.tier.text">{{ r.v.primary.tier.label }} {{ r.v.primary.pct }}%</span>
              <span class="text-slate-400">{{ METHOD_LABEL[r.v.primary.method] }}</span>
              <span
                v-if="r.v.divergent"
                class="text-amber-600"
                :title="`${METHOD_LABEL[r.v.secondary.method]}：${r.v.secondary.tier.label} ${r.v.secondary.pct}% — 兩法位置相差半個估值帶以上`"
              >⚠ 兩法分歧</span>
              <span class="md:hidden ml-auto font-mono text-slate-500">
                距合理 <span :class="upDown(r.v.primary.toFair)">{{ signed(r.v.primary.toFair) }}</span>
              </span>
            </div>
          </template>
          <div v-else-if="r.d" class="text-[11px] text-slate-400">無估值資料</div>
          <div v-else-if="!r.custom" class="skel h-2 w-full"></div>
        </div>

        <!-- desktop: fair, distance, yield, PE -->
        <div class="hidden md:block text-right tnum text-[13px]">{{ fmtPrice(r.v?.primary?.bands.fair) }}</div>
        <div class="hidden md:block text-right tnum text-[13px] font-semibold" :class="upDown(r.v?.primary?.toFair)">{{ signed(r.v?.primary?.toFair) }}</div>
        <div class="hidden md:block text-right tnum text-[13px] text-slate-600">{{ r.v?.curYield != null ? r.v.curYield.toFixed(2) + '%' : '—' }}</div>
        <div class="hidden md:block text-right tnum text-[13px] text-slate-600">{{ r.v?.curPe != null ? r.v.curPe.toFixed(1) : '—' }}</div>
      </div>

      <div v-if="!visible.length" class="px-4 py-10 text-center text-sm text-slate-500">
        <template v-if="list === 'watch' && !watchlist.codes.length">
          還沒有自選股。<br />
          <span class="text-xs">在任一列點 ☆ 加入；或用上方搜尋開啟任意代號（例：6505），在個股頁點「加入自選」。</span>
        </template>
        <template v-else>沒有符合條件的股票</template>
      </div>
    </div>

    <p class="mt-2 text-[11px] text-slate-500 leading-relaxed">
      估值位置：0% = 便宜價、50% = 合理價、100% = 昂貴價（近 3 年 5 / 50 / 95 百分位）。有 EPS 用 PE 法，否則用殖利率法；
      <span class="text-amber-600">⚠ 兩法分歧</span> 表示殖利率法與 PE 法的位置相差 50 個百分點以上，建議進個股頁兩者一起看。
      <template v-if="alertCount"> · 🔔 追蹤中的到價提醒 {{ alertCount }} 個</template>
    </p>
  </div>
</template>

<style scoped>
.th { display: inline-flex; align-items: baseline; gap: 2px; white-space: nowrap; }
.th:hover { color: var(--ink); }
.text-right.th { justify-content: flex-end; }
.th i { font-style: normal; font-size: 9px; color: var(--accent); }
.no-scrollbar { scrollbar-width: none; }
.no-scrollbar::-webkit-scrollbar { display: none; }
</style>
