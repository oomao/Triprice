<script setup>
import { computed } from 'vue'

const props = defineProps({
  // Required: today's % change for both legs
  twChangePct: { type: Number, default: null },
  adrChangePct: { type: Number, default: null },
  twLabel: { type: String, default: '台股 今日' },
  adrLabel: { type: String, default: 'ADR 今日' },
  // Optional context line
  twDate: { type: String, default: '' },
  adrDate: { type: String, default: '' },
})

const W = 320
const H = 110
const PAD_L = 60      // room for left labels
const PAD_R = 50      // room for right values
const PAD_T = 18
const PAD_B = 30
const BAR_H = 18
const ROW_GAP = 8
const MID_X = (PAD_L + (W - PAD_R)) / 2

// Auto-scale axis: max(|tw|, |adr|, 1) so a 0.3% move isn't invisible
const maxAbs = computed(() => {
  const tw = Math.abs(props.twChangePct ?? 0)
  const adr = Math.abs(props.adrChangePct ?? 0)
  return Math.max(tw, adr, 1) * 1.15 // 15% headroom
})

const halfWidth = (W - PAD_L - PAD_R) / 2

function barFor(v, y) {
  if (v == null || isNaN(v)) return null
  const len = halfWidth * (v / maxAbs.value)
  return {
    x: len >= 0 ? MID_X : MID_X + len,
    width: Math.abs(len),
    y,
    color: v >= 0 ? '#dc2626' : '#10b981',
    valX: len >= 0 ? MID_X + Math.abs(len) + 4 : MID_X + len - 4,
    valAnchor: len >= 0 ? 'start' : 'end',
  }
}

const twBar = computed(() => barFor(props.twChangePct, PAD_T))
const adrBar = computed(() => barFor(props.adrChangePct, PAD_T + BAR_H + ROW_GAP))

// Diff: ADR change minus TW change. Positive => ADR did better in its session
// than TW did in same-day session => leading bullish for TW next open.
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
</script>

<template>
  <div>
    <svg :viewBox="`0 0 ${W} ${H}`" class="w-full" style="max-height: 130px">
      <!-- 0% baseline -->
      <line :x1="MID_X" :x2="MID_X" :y1="PAD_T - 4" :y2="PAD_T + BAR_H * 2 + ROW_GAP + 4"
            stroke="var(--rule)" stroke-width="1.2" />
      <text :x="MID_X" :y="PAD_T - 6" text-anchor="middle"
            fill="var(--ink-muted)" font-size="9" font-family="ui-monospace, monospace">0%</text>

      <!-- TW row -->
      <text :x="PAD_L - 6" :y="PAD_T + BAR_H / 2 + 4" text-anchor="end"
            fill="var(--ink)" font-size="11" font-weight="600">{{ twLabel }}</text>
      <rect v-if="twBar" :x="twBar.x" :y="twBar.y" :width="twBar.width" :height="BAR_H"
            :fill="twBar.color" rx="1" />
      <text v-if="twBar" :x="twBar.valX" :y="twBar.y + BAR_H / 2 + 4" :text-anchor="twBar.valAnchor"
            :fill="twBar.color" font-size="11" font-weight="700"
            font-family="ui-sans-serif, system-ui, sans-serif">
        {{ fmtPct(twChangePct) }}
      </text>

      <!-- ADR row -->
      <text :x="PAD_L - 6" :y="adrBar?.y + BAR_H / 2 + 4 || PAD_T + BAR_H + ROW_GAP + BAR_H / 2 + 4"
            text-anchor="end" fill="var(--ink)" font-size="11" font-weight="600">{{ adrLabel }}</text>
      <rect v-if="adrBar" :x="adrBar.x" :y="adrBar.y" :width="adrBar.width" :height="BAR_H"
            :fill="adrBar.color" rx="1" />
      <text v-if="adrBar" :x="adrBar.valX" :y="adrBar.y + BAR_H / 2 + 4" :text-anchor="adrBar.valAnchor"
            :fill="adrBar.color" font-size="11" font-weight="700"
            font-family="ui-sans-serif, system-ui, sans-serif">
        {{ fmtPct(adrChangePct) }}
      </text>

      <!-- Date axis labels -->
      <text v-if="twDate" :x="PAD_L - 6" :y="PAD_T + BAR_H + 4" text-anchor="end"
            fill="var(--ink-muted)" font-size="8" font-family="ui-monospace, monospace">
        {{ twDate }}
      </text>
      <text v-if="adrDate" :x="PAD_L - 6" :y="(adrBar?.y || (PAD_T + BAR_H + ROW_GAP)) + BAR_H + 4" text-anchor="end"
            fill="var(--ink-muted)" font-size="8" font-family="ui-monospace, monospace">
        {{ adrDate }}
      </text>
    </svg>

    <div v-if="diff != null && diffSignal" :class="['mt-1 px-2.5 py-1.5 border text-xs flex items-center justify-between', diffColorClass]">
      <span>
        ADR − 台股 差距
        <strong class="ml-1">{{ diff >= 0 ? '+' : '' }}{{ diff.toFixed(2) }} pp</strong>
      </span>
      <span class="font-semibold">→ {{ diffSignal.label }}</span>
    </div>
  </div>
</template>
