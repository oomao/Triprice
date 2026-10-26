<script setup>
import { computed } from 'vue'
import { positionPct } from '../lib/position.js'

// Horizontal cheap → fair → expensive scale with a marker at the current price.
// Position is piecewise (0% = cheap, 50% = fair, 100% = expensive); the visible
// domain runs a little past both ends so out-of-band prices still read correctly.
const props = defineProps({
  bands: { type: Object, required: true }, // { cheap, fair, expensive }
  price: { type: Number, default: null },
  compact: { type: Boolean, default: false },
})

const LO = -20
const HI = 120
const x = (pct) => ((Math.max(LO, Math.min(HI, pct)) - LO) / (HI - LO)) * 100

const pct = computed(() => positionPct(props.price, props.bands))
const markerX = computed(() => (pct.value == null ? null : x(pct.value)))
const overflow = computed(() => (pct.value == null ? 0 : pct.value < LO ? -1 : pct.value > HI ? 1 : 0))

const zones = [
  { from: LO, to: 0, cls: 'bg-emerald-500/60' },
  { from: 0, to: 50, cls: 'bg-emerald-500/25' },
  { from: 50, to: 100, cls: 'bg-amber-500/35' },
  { from: 100, to: HI, cls: 'bg-red-500/55' },
]

function fmt(n) {
  if (n == null || isNaN(n)) return '—'
  const d = Math.abs(n) >= 1000 ? 0 : Math.abs(n) >= 100 ? 1 : 2
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: d })
}
</script>

<template>
  <div :class="compact ? '' : 'pt-6 pb-7'" class="relative select-none">
    <!-- track -->
    <div class="relative overflow-hidden rounded-full" :class="compact ? 'h-1.5' : 'h-2.5'">
      <div
        v-for="z in zones"
        :key="z.from"
        class="absolute inset-y-0"
        :class="z.cls"
        :style="{ left: x(z.from) + '%', width: x(z.to) - x(z.from) + '%' }"
      ></div>
    </div>

    <!-- tick marks at cheap / fair / expensive -->
    <template v-if="!compact">
      <div
        v-for="t in [{ p: 0, k: '便宜', v: bands.cheap, c: 'text-emerald-600' }, { p: 50, k: '合理', v: bands.fair, c: 'text-slate-700' }, { p: 100, k: '昂貴', v: bands.expensive, c: 'text-red-500' }]"
        :key="t.p"
        class="absolute bottom-0 -translate-x-1/2 text-center leading-tight"
        :style="{ left: x(t.p) + '%' }"
      >
        <div class="mx-auto w-px h-1.5 bg-slate-400 -mt-0.5 mb-0.5"></div>
        <div class="text-[10px] text-slate-500">{{ t.k }}</div>
        <div class="text-[11px] font-mono font-semibold" :class="t.c">{{ fmt(t.v) }}</div>
      </div>
    </template>

    <!-- current price marker: a zero-size anchor at the track's centre line -->
    <div
      v-if="markerX != null"
      class="absolute"
      :style="{ left: markerX + '%', top: compact ? '50%' : 'calc(1.5rem + 0.3125rem)' }"
    >
      <div
        class="absolute left-0 top-0 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2"
        :class="compact ? 'w-2.5 h-2.5' : 'w-3.5 h-3.5'"
        :style="{ background: 'var(--ink)', '--tw-ring-color': 'var(--surface)' }"
      ></div>
      <div
        v-if="!compact"
        class="absolute left-0 bottom-[10px] text-[10px] font-mono font-bold whitespace-nowrap"
        :class="markerX < 15 ? '' : markerX > 85 ? '-translate-x-full' : '-translate-x-1/2'"
        :style="{ color: 'var(--ink)' }"
      >
        <span v-if="overflow < 0">‹ </span>現價 {{ fmt(price) }}<span v-if="overflow > 0"> ›</span>
      </div>
    </div>
  </div>
</template>
