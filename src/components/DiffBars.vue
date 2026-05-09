<script setup>
import { computed } from 'vue'

const props = defineProps({
  twChangePct: { type: Number, default: null },
  adrChangePct: { type: Number, default: null },
  twLabel: { type: String, default: '台股 今日' },
  adrLabel: { type: String, default: 'ADR 今日' },
  twDate: { type: String, default: '' },
  adrDate: { type: String, default: '' },
  // Hide the naive "差距 → 隔日方向" hint when used next to the cleaned
  // Ridge prediction (which is more rigorous and would conflict).
  showDiffSignal: { type: Boolean, default: true },
})

// Layout: 3 fixed columns — left label / center bar (bidirectional) / right value.
// All numbers are in the SVG's viewBox space (px-equivalent).
const W = 320
const H = 110
const PAD_T = 22
const PAD_B = 8
const COL_LABEL = 78    // left column width (label + date)
const COL_VALUE = 64    // right column width (always visible value)
const BAR_H = 18
const ROW_GAP = 6
const BAR_LEFT = COL_LABEL
const BAR_RIGHT = W - COL_VALUE
const MID_X = (BAR_LEFT + BAR_RIGHT) / 2
const HALF = (BAR_RIGHT - BAR_LEFT) / 2

// Auto-scale: max(|tw|, |adr|, 1) with 15% headroom so a 0.3% move is still visible.
const maxAbs = computed(() => {
  const tw = Math.abs(props.twChangePct ?? 0)
  const adr = Math.abs(props.adrChangePct ?? 0)
  return Math.max(tw, adr, 1) * 1.15
})

function barFor(v, y) {
  if (v == null || isNaN(v)) return null
  const len = HALF * (v / maxAbs.value)
  return {
    x: len >= 0 ? MID_X : MID_X + len,
    width: Math.abs(len),
    y,
    color: v >= 0 ? '#dc2626' : '#10b981',
  }
}

const twBar = computed(() => barFor(props.twChangePct, PAD_T))
const adrBar = computed(() => barFor(props.adrChangePct, PAD_T + BAR_H + ROW_GAP))

const adrRowY = computed(() => PAD_T + BAR_H + ROW_GAP)

// Diff: ADR change minus TW change. Positive ⇒ ADR did better than TW today
// ⇒ leading bullish for TW next open. Pp = "percentage point".
const diff = computed(() => {
  if (props.twChangePct == null || props.adrChangePct == null) return null
  return props.adrChangePct - props.twChangePct
})

const diffSignal = computed(() => {
  const d = diff.value
  if (d == null) return null
  if (d >= 1.5)  return { label: '隔日台股可能補漲', tone: 'strong-bull' }
  if (d >= 0.3)  return { label: '隔日台股偏多',     tone: 'bull' }
  if (d >  -0.3) return { label: '隔日台股偏中性',   tone: 'neutral' }
  if (d >  -1.5) return { label: '隔日台股偏空',     tone: 'bear' }
  return                  { label: '隔日台股可能補跌', tone: 'strong-bear' }
})

const diffColorClass = computed(() => {
  switch (diffSignal.value?.tone) {
    case 'strong-bull': return 'text-red-700 bg-red-50 border-red-300'
    case 'bull':        return 'text-red-600 bg-red-50 border-red-200'
    case 'neutral':     return 'text-slate-700 bg-slate-50 border-slate-300'
    case 'bear':        return 'text-emerald-600 bg-emerald-50 border-emerald-200'
    case 'strong-bear': return 'text-emerald-700 bg-emerald-50 border-emerald-300'
    default:            return 'text-slate-500 bg-slate-50 border-slate-200'
  }
})

function fmtPct(v) {
  if (v == null || isNaN(v)) return '—'
  return `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`
}

function pctColor(v) {
  if (v == null) return 'var(--ink-muted)'
  return v >= 0 ? '#dc2626' : '#10b981'
}
</script>

<template>
  <div>
    <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="max-height: 130px">
      <!-- 0% baseline + tick label -->
      <line :x1="MID_X" :x2="MID_X"
            :y1="PAD_T - 6" :y2="PAD_T + BAR_H * 2 + ROW_GAP + 4"
            stroke="var(--rule)" stroke-width="1.2" />
      <text :x="MID_X" :y="PAD_T - 8" text-anchor="middle"
            fill="var(--ink-muted)" font-size="9"
            font-family="ui-monospace, monospace">0%</text>

      <!-- ── TW row ─────────────────────────────────────── -->
      <text :x="BAR_LEFT - 8" :y="PAD_T + BAR_H / 2 + 1"
            text-anchor="end" fill="var(--ink)"
            font-size="11" font-weight="600">{{ twLabel }}</text>
      <text v-if="twDate" :x="BAR_LEFT - 8" :y="PAD_T + BAR_H / 2 + 11"
            text-anchor="end" fill="var(--ink-muted)"
            font-size="8" font-family="ui-monospace, monospace">{{ twDate }}</text>
      <rect v-if="twBar" :x="twBar.x" :y="twBar.y"
            :width="Math.max(twBar.width, 1.5)" :height="BAR_H"
            :fill="twBar.color" rx="1" />
      <text :x="BAR_RIGHT + 6" :y="PAD_T + BAR_H / 2 + 4"
            text-anchor="start" :fill="pctColor(twChangePct)"
            font-size="12" font-weight="700"
            font-family="ui-sans-serif, system-ui, sans-serif">
        {{ fmtPct(twChangePct) }}
      </text>

      <!-- ── ADR row ────────────────────────────────────── -->
      <text :x="BAR_LEFT - 8" :y="adrRowY + BAR_H / 2 + 1"
            text-anchor="end" fill="var(--ink)"
            font-size="11" font-weight="600">{{ adrLabel }}</text>
      <text v-if="adrDate" :x="BAR_LEFT - 8" :y="adrRowY + BAR_H / 2 + 11"
            text-anchor="end" fill="var(--ink-muted)"
            font-size="8" font-family="ui-monospace, monospace">{{ adrDate }}</text>
      <rect v-if="adrBar" :x="adrBar.x" :y="adrBar.y"
            :width="Math.max(adrBar.width, 1.5)" :height="BAR_H"
            :fill="adrBar.color" rx="1" />
      <text :x="BAR_RIGHT + 6" :y="adrRowY + BAR_H / 2 + 4"
            text-anchor="start" :fill="pctColor(adrChangePct)"
            font-size="12" font-weight="700"
            font-family="ui-sans-serif, system-ui, sans-serif">
        {{ fmtPct(adrChangePct) }}
      </text>
    </svg>

    <div v-if="diff != null && diffSignal && showDiffSignal"
         :class="['mt-1 px-2.5 py-1.5 border text-xs flex items-center justify-between flex-wrap gap-2', diffColorClass]">
      <span>
        ADR − 台股 差距
        <strong class="ml-1 font-mono">{{ diff >= 0 ? '+' : '' }}{{ diff.toFixed(2) }} pp</strong>
      </span>
      <span class="font-semibold">→ {{ diffSignal.label }}</span>
    </div>
    <div v-else-if="diff != null"
         class="mt-1 text-[11px] text-slate-500 text-right font-mono">
      ADR − 台股 差距 <strong>{{ diff >= 0 ? '+' : '' }}{{ diff.toFixed(2) }} pp</strong>
    </div>
  </div>
</template>
