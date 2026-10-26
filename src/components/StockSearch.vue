<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { fetchData } from '../lib/data.js'

// Global "go to stock" box. Suggests every listed / OTC security by code or name
// (data/names.json, refreshed daily by fetch_etf.py), preloaded stocks first. Any
// well-formed code can be opened — the stock page fetches it live from FinMind.
const router = useRouter()
const q = ref('')
const open = ref(false)
const active = ref(0)
const input = ref(null)
const index = ref([]) // [{ code, name, tag }]
let indexLoaded = false

const CODE_RE = /^[0-9]{4,6}[A-Z]?$/

async function loadIndex() {
  if (indexLoaded) return
  indexLoaded = true
  const [stocks, names] = await Promise.all([
    fetchData('stocks.json', { optional: true }),
    fetchData('names.json', { optional: true }),
  ])
  const seen = new Set()
  const out = []
  for (const [code, m] of Object.entries(stocks?.tw_stocks || {})) {
    seen.add(code)
    out.push({ code, name: m.name, tag: '預載' })
  }
  let all = names?.names
  if (!all) {
    // names.json not generated yet → at least offer the ETF universe
    const etfs = await fetchData('etf_list.json', { optional: true })
    all = Object.fromEntries((etfs?.etfs || []).map((e) => [e.code, e.name]))
  }
  for (const [code, name] of Object.entries(all)) {
    if (seen.has(code)) continue
    out.push({ code, name, tag: code.startsWith('00') ? 'ETF' : '' })
  }
  index.value = out
}

const suggestions = computed(() => {
  const s = q.value.trim().toUpperCase()
  if (!s) return []
  const hits = index.value
    .filter((e) => e.code.startsWith(s) || e.name?.toUpperCase().includes(s))
    // code-prefix hits, then preloaded stocks (instant, full history), then names
    // that start with the query, then everything else by code
    .sort((a, b) =>
      (b.code.startsWith(s) - a.code.startsWith(s)) ||
      ((b.tag === '預載') - (a.tag === '預載')) ||
      ((b.name?.toUpperCase().startsWith(s) ?? 0) - (a.name?.toUpperCase().startsWith(s) ?? 0)) ||
      a.code.localeCompare(b.code))
    .slice(0, 8)
  if (CODE_RE.test(s) && !hits.some((h) => h.code === s)) {
    hits.push({ code: s, name: '查詢此代號（即時抓取）', tag: '其他' })
  }
  return hits
})

function go(code) {
  if (!code) return
  router.push(`/stock/${code}`)
  q.value = ''
  open.value = false
  input.value?.blur()
}

function onEnter() {
  const pick = suggestions.value[active.value]
  if (pick) go(pick.code)
  else if (CODE_RE.test(q.value.trim().toUpperCase())) go(q.value.trim().toUpperCase())
}

function move(d) {
  const n = suggestions.value.length
  if (!n) return
  active.value = (active.value + d + n) % n
}

function onFocus() {
  open.value = true
  loadIndex()
}

// "/" focuses the search box from anywhere (unless already typing in a field).
function onKey(e) {
  if (e.key !== '/' || e.metaKey || e.ctrlKey || e.altKey) return
  const t = e.target
  if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return
  e.preventDefault()
  input.value?.focus()
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
</script>

<template>
  <div class="relative w-full">
    <input
      ref="input"
      v-model="q"
      type="search"
      inputmode="search"
      autocomplete="off"
      placeholder="搜尋代號 / 名稱"
      aria-label="搜尋股票"
      class="search-input w-full h-8 pl-8 pr-8 rounded text-[13px] text-white placeholder:text-slate-400 bg-white/10 border border-white/10 focus:bg-white/15 focus:border-amber-400/70 focus:outline-none transition"
      @focus="onFocus"
      @blur="open = false"
      @input="active = 0; open = true"
      @keydown.down.prevent="move(1)"
      @keydown.up.prevent="move(-1)"
      @keydown.enter.prevent="onEnter"
      @keydown.esc="input?.blur()"
    />
    <svg class="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400 pointer-events-none" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="9" cy="9" r="6" /><path d="m14 14 4 4" stroke-linecap="round" /></svg>
    <kbd class="hidden lg:block absolute right-2 top-1/2 -translate-y-1/2 text-[10px] font-mono text-slate-500 border border-white/15 rounded px-1 leading-4 pointer-events-none">/</kbd>

    <ul
      v-if="open && suggestions.length"
      class="absolute left-0 right-0 top-full mt-1 z-40 bg-white border border-[#e7e7e1] shadow-lg text-[13px] text-slate-900 max-h-80 overflow-auto"
      role="listbox"
    >
      <li
        v-for="(s, i) in suggestions"
        :key="s.code + s.tag"
        role="option"
        :aria-selected="i === active"
        class="px-3 py-2 flex items-baseline gap-2 cursor-pointer"
        :class="i === active ? 'bg-slate-100' : ''"
        @mousedown.prevent="go(s.code)"
        @mouseenter="active = i"
      >
        <span class="font-mono text-xs text-slate-500 w-14 shrink-0">{{ s.code }}</span>
        <span class="truncate flex-1">{{ s.name }}</span>
        <span class="text-[10px] text-slate-400 shrink-0">{{ s.tag }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
/* The global dark-mode bridge restyles every <input>; keep this one on the header. */
.dark .search-input {
  background-color: rgb(255 255 255 / 0.08);
  color: #fff;
  border-color: rgb(255 255 255 / 0.1);
}
.search-input::-webkit-search-cancel-button { filter: invert(1) opacity(0.5); }
</style>
