<script setup>
import { computed } from 'vue'

const props = defineProps({
  // [{d, f (foreign), tr (trust), de (dealer), t (total)}, ...] sorted ascending
  // Units are SHARES (FinMind convention for per-stock institutional flow).
  chips: { type: Array, required: true },
  daysToShow: { type: Number, default: 30 },
})

const W = 640
const H = 130
const PAD_L = 8
const PAD_R = 8
const PAD_T = 6
const PAD_B = 18

const visible = computed(() => (props.chips || []).slice(-props.daysToShow))
const valid = computed(() => visible.value.length >= 3)

const yMax = computed(() => {
  if (!valid.value) return 1
  let m = 0
  for (const c of visible.value) {
    const segs = [Math.abs(c.f), Math.abs(c.tr), Math.abs(c.de)]
    const total = segs.reduce((a, b) => a + b, 0)
    if (total > m) m = total
  }
  return m || 1
})

function xAt(i, total) {
  if (total <= 1) return PAD_L
  return PAD_L + ((W - PAD_L - PAD_R) * i) / Math.max(1, total)
}

const mid = (PAD_T + (H - PAD_B)) / 2

function yScale(v) {
  // half height for either side
  const halfH = (H - PAD_B - PAD_T) / 2
  return halfH * (v / yMax.value)
}

const bars = computed(() => {
  if (!valid.value) return []
  const total = visible.value.length
  const barW = Math.max(2, (W - PAD_L - PAD_R) / total * 0.8)
  return visible.value.map((c, i) => {
    const cx = xAt(i, total) + ((W - PAD_L - PAD_R) / total) / 2 - barW / 2
    // Stack the three (foreign, trust, dealer) per side (positive above mid, negative below).
    const segments = []
    let yPos = mid
    let yNeg = mid
    const stackSeg = (val, fill, name) => {
      if (val === 0) return
      const h = yScale(Math.abs(val))
      if (val > 0) {
        segments.push({ x: cx, y: yPos - h, w: barW, h, fill, name, val })
        yPos -= h
      } else {
        segments.push({ x: cx, y: yNeg, w: barW, h, fill, name, val })
        yNeg += h
      }
    }
    stackSeg(c.f, '#0ea5e9', 'foreign')
    stackSeg(c.tr, '#f59e0b', 'trust')
    stackSeg(c.de, '#8b5cf6', 'dealer')
    return { date: c.d, segments }
  })
})

const xTicks = computed(() => {
  const arr = visible.value
  if (!arr.length) return []
  const step = Math.ceil(arr.length / 5)
  const out = []
  for (let i = 0; i < arr.length; i += step) {
    out.push({ x: xAt(i, arr.length) + ((W - PAD_L - PAD_R) / arr.length) / 2, label: arr[i].d.slice(5) })
  }
  return out
})

function fmtShares(v) {
  // v in shares; show as 萬股 or 千股
  const a = Math.abs(v)
  if (a >= 1e7) return `${(v / 1e7).toFixed(1)} 千萬`
  if (a >= 1e4) return `${(v / 1e4).toFixed(1)} 萬`
  return v.toLocaleString() + ' 股'
}

const summary5d = computed(() => {
  if (!valid.value) return null
  const last5 = visible.value.slice(-5)
  let f = 0, tr = 0, de = 0, t = 0
  for (const c of last5) { f += c.f; tr += c.tr; de += c.de; t += c.t }
  return { f, tr, de, t, days: last5.length }
})
</script>

<template>
  <div v-if="valid">
    <div class="flex items-center justify-between mb-2">
      <div class="text-xs text-slate-500">近 {{ visible.length }} 個交易日（單位：股）</div>
      <div class="text-[10px] text-slate-500 flex gap-2.5">
        <span class="inline-flex items-center gap-1"><span class="w-3 h-2 bg-sky-500"></span>外資</span>
        <span class="inline-flex items-center gap-1"><span class="w-3 h-2 bg-amber-500"></span>投信</span>
        <span class="inline-flex items-center gap-1"><span class="w-3 h-2 bg-violet-500"></span>自營</span>
      </div>
    </div>
    <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" class="w-full" style="height: 130px">
      <line :x1="PAD_L" :x2="W - PAD_R" :y1="mid" :y2="mid" stroke="#cbd5e1" stroke-width="0.6" stroke-dasharray="3 3" />
      <g v-for="(b, i) in bars" :key="i">
        <rect
          v-for="(s, j) in b.segments"
          :key="j"
          :x="s.x" :y="s.y" :width="s.w" :height="s.h" :fill="s.fill"
        >
          <title>{{ b.date }} {{ s.name }}: {{ fmtShares(s.val) }}</title>
        </rect>
      </g>
      <g v-for="t in xTicks" :key="t.x">
        <text :x="t.x" :y="H - 4" text-anchor="middle" fill="#94a3b8" font-size="9" font-family="ui-monospace, monospace">{{ t.label }}</text>
      </g>
    </svg>

    <div v-if="summary5d" class="grid grid-cols-4 gap-2 text-xs mt-3">
      <div class="bg-slate-50 rounded p-2 border border-slate-200">
        <div class="text-slate-500 text-[10px]">外資 5 日</div>
        <div :class="summary5d.f >= 0 ? 'text-red-500' : 'text-emerald-600'" class="font-bold font-mono">{{ summary5d.f >= 0 ? '+' : '' }}{{ fmtShares(summary5d.f) }}</div>
      </div>
      <div class="bg-slate-50 rounded p-2 border border-slate-200">
        <div class="text-slate-500 text-[10px]">投信 5 日</div>
        <div :class="summary5d.tr >= 0 ? 'text-red-500' : 'text-emerald-600'" class="font-bold font-mono">{{ summary5d.tr >= 0 ? '+' : '' }}{{ fmtShares(summary5d.tr) }}</div>
      </div>
      <div class="bg-slate-50 rounded p-2 border border-slate-200">
        <div class="text-slate-500 text-[10px]">自營 5 日</div>
        <div :class="summary5d.de >= 0 ? 'text-red-500' : 'text-emerald-600'" class="font-bold font-mono">{{ summary5d.de >= 0 ? '+' : '' }}{{ fmtShares(summary5d.de) }}</div>
      </div>
      <div class="bg-slate-100 rounded p-2 border border-slate-300">
        <div class="text-slate-500 text-[10px]">合計 5 日</div>
        <div :class="summary5d.t >= 0 ? 'text-red-500' : 'text-emerald-600'" class="font-bold font-mono">{{ summary5d.t >= 0 ? '+' : '' }}{{ fmtShares(summary5d.t) }}</div>
      </div>
    </div>
  </div>
  <div v-else class="text-xs text-slate-400 italic py-3">尚無三大法人籌碼資料</div>
</template>
