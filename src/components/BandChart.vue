<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  // [{d:'YYYY-MM-DD', c:close, p?:per}, ...] sorted ascending
  history: { type: Array, required: true },
  // {cheap, fair, expensive} — three reference price levels
  bands: { type: Object, required: true },
  // optional current price marker (overrides last point of history)
  currentPrice: { type: Number, default: null },
  // labels for the three bands
  labels: {
    type: Object,
    default: () => ({ cheap: '便宜', fair: '合理', expensive: '昂貴' }),
  },
})

const W = 640
const H = 220
const PAD_L = 56
const PAD_R = 12
const PAD_T = 12
const PAD_B = 24

const points = computed(() =>
  (props.history || []).filter((d) => d && d.c > 0).map((d) => ({ ...d })),
)

const valid = computed(() => points.value.length >= 5 && props.bands)

const yRange = computed(() => {
  if (!valid.value) return { min: 0, max: 1 }
  const closes = points.value.map((p) => p.c)
  const cur = props.currentPrice ?? closes[closes.length - 1]
  const candidates = [
    ...closes,
    props.bands.cheap,
    props.bands.fair,
    props.bands.expensive,
    cur,
  ].filter((v) => typeof v === 'number' && !isNaN(v))
  let min = Math.min(...candidates)
  let max = Math.max(...candidates)
  if (max === min) {
    max = min * 1.1 || 1
    min = min * 0.9 || 0
  }
  // 6% padding so labels/markers don't clip
  const pad = (max - min) * 0.06
  return { min: min - pad, max: max + pad }
})

function xAt(i, total) {
  if (total <= 1) return PAD_L
  return PAD_L + ((W - PAD_L - PAD_R) * i) / (total - 1)
}

function yAt(v) {
  const { min, max } = yRange.value
  const range = max - min || 1
  return PAD_T + (H - PAD_T - PAD_B) * (1 - (v - min) / range)
}

const linePath = computed(() => {
  const pts = points.value
  if (pts.length === 0) return ''
  return pts
    .map((p, i) => `${i === 0 ? 'M' : 'L'}${xAt(i, pts.length).toFixed(1)},${yAt(p.c).toFixed(1)}`)
    .join(' ')
})

// Colored band rectangles. Top->bottom on screen (high price -> low):
//   above expensive  : red (overvalued)
//   expensive .. fair: amber (rich)
//   fair .. cheap    : green (reasonable)
//   below cheap      : emerald (deep value)
const bandRects = computed(() => {
  if (!valid.value) return []
  const { cheap, fair, expensive } = props.bands
  const top = PAD_T
  const bottom = H - PAD_B
  const yExp = yAt(expensive)
  const yFair = yAt(fair)
  const yCheap = yAt(cheap)
  return [
    { y: top, h: Math.max(0, yExp - top), fill: 'rgba(244, 63, 94, 0.07)' },
    { y: yExp, h: Math.max(0, yFair - yExp), fill: 'rgba(245, 158, 11, 0.07)' },
    { y: yFair, h: Math.max(0, yCheap - yFair), fill: 'rgba(16, 185, 129, 0.08)' },
    { y: yCheap, h: Math.max(0, bottom - yCheap), fill: 'rgba(5, 150, 105, 0.10)' },
  ]
})

const bandLines = computed(() => {
  if (!valid.value) return []
  const { cheap, fair, expensive } = props.bands
  return [
    { v: expensive, label: `${props.labels.expensive} ${fmt(expensive)}`, color: '#dc2626', dash: '4 3' },
    { v: fair, label: `${props.labels.fair} ${fmt(fair)}`, color: '#0284c7', dash: '5 0' },
    { v: cheap, label: `${props.labels.cheap} ${fmt(cheap)}`, color: '#059669', dash: '4 3' },
  ]
})

const currentY = computed(() => {
  if (!valid.value) return null
  const cur = props.currentPrice ?? points.value[points.value.length - 1].c
  return { v: cur, y: yAt(cur), x: W - PAD_R }
})

const xTicks = computed(() => {
  // Show year ticks at first occurrence of each year in dataset.
  const pts = points.value
  if (!pts.length) return []
  const seen = new Set()
  const ticks = []
  pts.forEach((p, i) => {
    const y = p.d?.slice(0, 4)
    if (y && !seen.has(y)) {
      seen.add(y)
      ticks.push({ x: xAt(i, pts.length), label: y })
    }
  })
  return ticks
})

// Where in [0,1] does current price sit relative to the cheap..expensive band?
const positionPct = computed(() => {
  if (!valid.value) return null
  const { cheap, expensive } = props.bands
  const cur = props.currentPrice ?? points.value[points.value.length - 1].c
  if (expensive === cheap) return null
  const pct = ((cur - cheap) / (expensive - cheap)) * 100
  return Math.round(pct)
})

function fmt(n) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 0 })
}

// === Hover crosshair ===
const hoverIdx = ref(null)
const svgRef = ref(null)

function onMove(e) {
  const pts = points.value
  if (!pts.length) return
  const svg = svgRef.value
  if (!svg) return
  const rect = svg.getBoundingClientRect()
  const xRel = ((e.clientX - rect.left) / rect.width) * W
  const t = (xRel - PAD_L) / (W - PAD_L - PAD_R)
  const i = Math.round(t * (pts.length - 1))
  hoverIdx.value = Math.max(0, Math.min(pts.length - 1, i))
}
function onLeave() {
  hoverIdx.value = null
}

const hover = computed(() => {
  if (hoverIdx.value == null) return null
  const pts = points.value
  const p = pts[hoverIdx.value]
  if (!p) return null
  return {
    p,
    x: xAt(hoverIdx.value, pts.length),
    y: yAt(p.c),
  }
})
</script>

<template>
  <div v-if="valid" class="band-chart">
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
      <!-- Color bands -->
      <rect
        v-for="(r, i) in bandRects"
        :key="`band-${i}`"
        :x="PAD_L"
        :y="r.y"
        :width="W - PAD_L - PAD_R"
        :height="r.h"
        :fill="r.fill"
      />

      <!-- Year tick lines -->
      <g v-for="(t, i) in xTicks" :key="`tick-${i}`">
        <line
          :x1="t.x"
          :x2="t.x"
          :y1="PAD_T"
          :y2="H - PAD_B"
          stroke="#e2e8f0"
          stroke-width="1"
          stroke-dasharray="2 3"
        />
        <text
          :x="t.x"
          :y="H - 8"
          text-anchor="middle"
          fill="#94a3b8"
          font-size="10"
          font-family="ui-sans-serif, system-ui, sans-serif"
        >{{ t.label }}</text>
      </g>

      <!-- Band reference lines + right-side labels -->
      <g v-for="(b, i) in bandLines" :key="`bandline-${i}`">
        <line
          :x1="PAD_L"
          :x2="W - PAD_R"
          :y1="yAt(b.v)"
          :y2="yAt(b.v)"
          :stroke="b.color"
          stroke-width="1.2"
          :stroke-dasharray="b.dash"
          opacity="0.85"
        />
        <text
          :x="PAD_L - 6"
          :y="yAt(b.v) + 3"
          text-anchor="end"
          :fill="b.color"
          font-size="10"
          font-family="ui-sans-serif, system-ui, sans-serif"
          font-weight="600"
        >{{ b.label }}</text>
      </g>

      <!-- Price line -->
      <path
        :d="linePath"
        fill="none"
        stroke="#0f172a"
        stroke-width="1.4"
        stroke-linejoin="round"
        stroke-linecap="round"
      />

      <!-- Current price marker (right edge) -->
      <g v-if="currentY">
        <circle :cx="xAt(points.length - 1, points.length)" :cy="currentY.y" r="3.5" fill="#0f172a" />
        <text
          :x="W - PAD_R - 2"
          :y="currentY.y - 6"
          text-anchor="end"
          fill="#0f172a"
          font-size="11"
          font-weight="700"
          font-family="ui-sans-serif, system-ui, sans-serif"
        >{{ fmt(currentY.v) }}</text>
      </g>

      <!-- Hover crosshair + tooltip -->
      <g v-if="hover">
        <line :x1="hover.x" :x2="hover.x" :y1="PAD_T" :y2="H - PAD_B" stroke="#475569" stroke-width="0.8" stroke-dasharray="3 2" />
        <circle :cx="hover.x" :cy="hover.y" r="3" fill="#0284c7" />
        <g :transform="`translate(${Math.min(hover.x + 8, W - 110)}, ${Math.max(hover.y - 36, PAD_T + 4)})`">
          <rect width="100" height="32" rx="4" fill="white" stroke="#cbd5e1" stroke-width="0.8" />
          <text x="6" y="13" fill="#475569" font-size="10" font-family="ui-monospace, monospace">{{ hover.p.d }}</text>
          <text x="6" y="26" fill="#0f172a" font-size="11" font-weight="700" font-family="ui-sans-serif, system-ui, sans-serif">{{ fmt(hover.p.c) }}</text>
        </g>
      </g>
    </svg>

    <div v-if="positionPct != null" class="mt-2 text-xs text-slate-500">
      目前股價落在便宜～昂貴帶的
      <strong
        :class="
          positionPct < 0
            ? 'text-emerald-600'
            : positionPct < 50
              ? 'text-emerald-500'
              : positionPct < 100
                ? 'text-amber-500'
                : 'text-red-500'
        "
      >
        {{ positionPct < 0 ? '便宜以下' : positionPct > 100 ? '昂貴以上' : `${positionPct}%` }}
      </strong>
      位置（0% = 便宜價，100% = 昂貴價）
    </div>
  </div>
  <div v-else class="text-xs text-slate-400 italic py-3">
    歷史走勢資料尚未產生（下次資料更新後可看到）
  </div>
</template>
