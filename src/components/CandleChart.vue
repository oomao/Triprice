<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  // [{d, o, h, l, c, v}, ...] sorted ascending
  kline: { type: Array, required: true },
})

// Range selector — controls how many trailing days to render.
const RANGES = [
  { v: 30, label: '1M' },
  { v: 60, label: '3M' },
  { v: 120, label: '6M' },
  { v: 250, label: '1Y' },
]
const range = ref(120)

const W = 640
const H_PRICE = 200
const H_VOL = 50
const H = H_PRICE + H_VOL + 30
const PAD_L = 50
const PAD_R = 8
const PAD_T = 12
const GAP = 14

const visible = computed(() => {
  const arr = props.kline || []
  if (!arr.length) return []
  return arr.slice(-range.value)
})

const valid = computed(() => visible.value.length >= 5)

// Moving averages (computed over the FULL kline so MA at the start of the
// visible window is correct, then sliced to visible range).
function computeMA(period) {
  const full = props.kline || []
  const out = []
  for (let i = 0; i < full.length; i++) {
    if (i < period - 1) {
      out.push(null)
      continue
    }
    let sum = 0
    for (let j = i - period + 1; j <= i; j++) sum += full[j].c
    out.push(sum / period)
  }
  return out.slice(-range.value)
}
const ma5 = computed(() => computeMA(5))
const ma20 = computed(() => computeMA(20))
const ma60 = computed(() => computeMA(60))

const yPriceRange = computed(() => {
  if (!valid.value) return { min: 0, max: 1 }
  let min = Infinity, max = -Infinity
  for (const k of visible.value) {
    if (k.l < min) min = k.l
    if (k.h > max) max = k.h
  }
  // include MAs for stable axis
  const mas = [...ma5.value, ...ma20.value, ...ma60.value].filter((v) => v != null)
  for (const v of mas) {
    if (v < min) min = v
    if (v > max) max = v
  }
  if (max === min) {
    max = min * 1.05
    min = min * 0.95
  }
  const pad = (max - min) * 0.05
  return { min: min - pad, max: max + pad }
})

const yVolMax = computed(() => {
  if (!valid.value) return 1
  return Math.max(...visible.value.map((k) => k.v || 0)) || 1
})

function xAt(i, total) {
  if (total <= 1) return PAD_L
  return PAD_L + ((W - PAD_L - PAD_R) * i) / (total - 1)
}

function yPrice(v) {
  const { min, max } = yPriceRange.value
  return PAD_T + (H_PRICE * (1 - (v - min) / (max - min)))
}

function yVol(v) {
  const top = PAD_T + H_PRICE + GAP
  return top + (H_VOL * (1 - v / yVolMax.value))
}

const candleWidth = computed(() => {
  const n = visible.value.length
  if (n < 2) return 6
  const span = (W - PAD_L - PAD_R) / n
  return Math.max(1.5, Math.min(8, span * 0.7))
})

function maPath(arr) {
  if (!arr.length) return ''
  let started = false
  return arr
    .map((v, i) => {
      if (v == null) return ''
      const cmd = !started ? 'M' : 'L'
      started = true
      return `${cmd}${xAt(i, arr.length).toFixed(1)},${yPrice(v).toFixed(1)}`
    })
    .filter(Boolean)
    .join(' ')
}

const xTicks = computed(() => {
  const arr = visible.value
  if (!arr.length) return []
  const seenMonth = new Set()
  let lastYear = null
  const ticks = []
  arr.forEach((p, i) => {
    const ym = p.d?.slice(0, 7)
    if (!ym || seenMonth.has(ym)) return
    seenMonth.add(ym)
    const year = p.d.slice(0, 4)
    const month = p.d.slice(5, 7)
    // Year-aware label: show YYYY/MM on first tick and at year boundaries; MM otherwise.
    const label = (lastYear !== year) ? `${year}/${month}` : month
    lastYear = year
    ticks.push({ x: xAt(i, arr.length), label })
  })
  if (ticks.length > 6) {
    const step = Math.ceil(ticks.length / 6)
    return ticks.filter((_, i) => i % step === 0 || ticks[i].label.includes('/'))
  }
  return ticks
})

// Hover state
const hoverIdx = ref(null)
const svgRef = ref(null)
function onMove(e) {
  const arr = visible.value
  if (!arr.length || !svgRef.value) return
  const rect = svgRef.value.getBoundingClientRect()
  const xRel = ((e.clientX - rect.left) / rect.width) * W
  const t = (xRel - PAD_L) / (W - PAD_L - PAD_R)
  const i = Math.round(t * (arr.length - 1))
  hoverIdx.value = Math.max(0, Math.min(arr.length - 1, i))
}
function onLeave() { hoverIdx.value = null }

const hover = computed(() => {
  if (hoverIdx.value == null) return null
  const k = visible.value[hoverIdx.value]
  if (!k) return null
  return {
    k,
    x: xAt(hoverIdx.value, visible.value.length),
    ma5: ma5.value[hoverIdx.value],
    ma20: ma20.value[hoverIdx.value],
    ma60: ma60.value[hoverIdx.value],
  }
})

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d })
}
function fmtVol(n) {
  if (!n) return '—'
  if (n >= 1e8) return (n / 1e8).toFixed(1) + '億'
  if (n >= 1e4) return (n / 1e4).toFixed(0) + '萬'
  return n.toLocaleString()
}
</script>

<template>
  <div v-if="valid" class="candle-chart">
    <div class="flex items-center justify-between mb-2">
      <div class="flex gap-1 text-xs">
        <button
          v-for="r in RANGES" :key="r.v"
          @click="range = r.v"
          :class="[
            'px-2 py-0.5 border transition',
            range === r.v
              ? 'bg-[#0a0e16] text-white border-[#0a0e16]'
              : 'bg-white text-slate-600 border-[#d8d8d2] hover:border-[#0a0e16]',
          ]"
        >{{ r.label }}</button>
      </div>
      <div class="text-[10px] text-slate-500 flex gap-2">
        <span class="inline-flex items-center gap-1"><span class="w-3 h-0.5 bg-amber-500"></span>MA5</span>
        <span class="inline-flex items-center gap-1"><span class="w-3 h-0.5 bg-sky-500"></span>MA20</span>
        <span class="inline-flex items-center gap-1"><span class="w-3 h-0.5 bg-violet-500"></span>MA60</span>
      </div>
    </div>

    <svg
      ref="svgRef"
      :viewBox="`0 0 ${W} ${H}`"
      preserveAspectRatio="none"
      class="w-full h-auto select-none"
      @mousemove="onMove"
      @mouseleave="onLeave"
      @touchmove.passive="(e) => e.touches[0] && onMove(e.touches[0])"
      @touchend="onLeave"
    >
      <!-- Price area gridlines -->
      <g v-for="t in xTicks" :key="t.x">
        <line :x1="t.x" :x2="t.x" :y1="PAD_T" :y2="PAD_T + H_PRICE" stroke="#e2e8f0" stroke-width="0.6" stroke-dasharray="2 3" />
        <text :x="t.x" :y="PAD_T + H_PRICE + GAP + H_VOL + 14" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="ui-sans-serif, system-ui, sans-serif">{{ t.label }}</text>
      </g>

      <!-- Price y-axis labels (5 levels) -->
      <g v-for="(p, i) in [0, 0.25, 0.5, 0.75, 1]" :key="i">
        <text
          :x="PAD_L - 4"
          :y="yPrice(yPriceRange.min + (yPriceRange.max - yPriceRange.min) * (1 - p)) + 3"
          text-anchor="end"
          fill="#94a3b8" font-size="9" font-family="ui-monospace, monospace"
        >{{ fmt(yPriceRange.min + (yPriceRange.max - yPriceRange.min) * (1 - p), 0) }}</text>
      </g>

      <!-- MA lines -->
      <path :d="maPath(ma60)" stroke="#8b5cf6" stroke-width="0.9" fill="none" opacity="0.85" />
      <path :d="maPath(ma20)" stroke="#0ea5e9" stroke-width="0.9" fill="none" opacity="0.85" />
      <path :d="maPath(ma5)" stroke="#f59e0b" stroke-width="0.9" fill="none" opacity="0.85" />

      <!-- Candles -->
      <g v-for="(k, i) in visible" :key="k.d">
        <line
          :x1="xAt(i, visible.length)" :x2="xAt(i, visible.length)"
          :y1="yPrice(k.h)" :y2="yPrice(k.l)"
          :stroke="k.c >= k.o ? '#dc2626' : '#10b981'"
          stroke-width="0.8"
        />
        <rect
          :x="xAt(i, visible.length) - candleWidth / 2"
          :y="yPrice(Math.max(k.o, k.c))"
          :width="candleWidth"
          :height="Math.max(0.6, Math.abs(yPrice(k.o) - yPrice(k.c)))"
          :fill="k.c >= k.o ? '#dc2626' : '#10b981'"
        />
      </g>

      <!-- Volume bars -->
      <g>
        <line :x1="PAD_L" :x2="W - PAD_R" :y1="PAD_T + H_PRICE + GAP + H_VOL" :y2="PAD_T + H_PRICE + GAP + H_VOL" stroke="#cbd5e1" stroke-width="0.6" />
        <rect
          v-for="(k, i) in visible" :key="`v-${k.d}`"
          :x="xAt(i, visible.length) - candleWidth / 2"
          :y="yVol(k.v)"
          :width="candleWidth"
          :height="(PAD_T + H_PRICE + GAP + H_VOL) - yVol(k.v)"
          :fill="k.c >= k.o ? 'rgba(220, 38, 38, 0.45)' : 'rgba(16, 185, 129, 0.45)'"
        />
      </g>

      <!-- Hover crosshair + tooltip (uses CSS vars so it themes) -->
      <g v-if="hover">
        <line :x1="hover.x" :x2="hover.x" :y1="PAD_T" :y2="PAD_T + H_PRICE + GAP + H_VOL" stroke="var(--ink-muted)" stroke-width="0.6" stroke-dasharray="2 2" />
        <g :transform="`translate(${Math.min(hover.x + 8, W - 130)}, ${PAD_T + 4})`">
          <rect width="125" height="78" rx="4" fill="var(--surface)" stroke="var(--rule)" stroke-width="0.7" />
          <text x="6" y="13" fill="var(--ink-muted)" font-size="10" font-family="ui-monospace, monospace">{{ hover.k.d }}</text>
          <text x="6" y="26" fill="var(--ink)" font-size="10" font-family="ui-sans-serif, system-ui, sans-serif">開 {{ fmt(hover.k.o, 0) }} 收 {{ fmt(hover.k.c, 0) }}</text>
          <text x="6" y="38" fill="var(--ink)" font-size="10" font-family="ui-sans-serif, system-ui, sans-serif">高 {{ fmt(hover.k.h, 0) }} 低 {{ fmt(hover.k.l, 0) }}</text>
          <text x="6" y="50" fill="var(--ink-muted)" font-size="10" font-family="ui-sans-serif, system-ui, sans-serif">量 {{ fmtVol(hover.k.v) }}</text>
          <text x="6" y="63" fill="#f59e0b" font-size="9" font-family="ui-sans-serif, system-ui, sans-serif">MA5 {{ hover.ma5 != null ? fmt(hover.ma5, 0) : '—' }}</text>
          <text x="65" y="63" fill="#0ea5e9" font-size="9" font-family="ui-sans-serif, system-ui, sans-serif">MA20 {{ hover.ma20 != null ? fmt(hover.ma20, 0) : '—' }}</text>
          <text x="6" y="74" fill="#8b5cf6" font-size="9" font-family="ui-sans-serif, system-ui, sans-serif">MA60 {{ hover.ma60 != null ? fmt(hover.ma60, 0) : '—' }}</text>
        </g>
      </g>
    </svg>
  </div>
  <div v-else class="text-xs text-slate-400 italic py-3">尚無 K 線資料</div>
</template>
