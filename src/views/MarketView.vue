<script setup>
import { ref, onMounted, computed } from 'vue'

const data = ref(null)
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/market.json`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    data.value = await res.json()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

function fmt(n, d = 2) {
  if (n == null || isNaN(n)) return '—'
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: d,
    maximumFractionDigits: d,
  })
}

function fmtMoney(n) {
  // n is in NTD; convert to 億 for readability
  if (n == null || isNaN(n)) return '—'
  const yi = n / 1e8
  if (Math.abs(yi) >= 1) return `${yi >= 0 ? '+' : ''}${yi.toFixed(1)} 億`
  // Below 1 億 — fall back to 萬
  const wan = n / 1e4
  return `${wan >= 0 ? '+' : ''}${wan.toFixed(0)} 萬`
}

function moneyClass(n) {
  if (n == null || isNaN(n)) return 'text-slate-400'
  if (n > 0) return 'text-red-500'
  if (n < 0) return 'text-emerald-600'
  return 'text-slate-500'
}

// Mini sparkline rendering
const W = 320
const H = 80
const PAD = 6

function buildPath(history, width = W, height = H, pad = PAD) {
  if (!history?.length) return ''
  const closes = history.map((h) => h.c)
  const min = Math.min(...closes)
  const max = Math.max(...closes)
  const range = max - min || 1
  const n = closes.length
  return closes
    .map((c, i) => {
      const x = pad + ((width - pad * 2) * i) / Math.max(1, n - 1)
      const y = pad + (height - pad * 2) * (1 - (c - min) / range)
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

function buildBars(records, width = W, height = H, pad = PAD) {
  if (!records?.length) return []
  const vals = records.map((r) => r.total_net)
  const max = Math.max(...vals.map(Math.abs))
  if (max === 0) return []
  const n = records.length
  const barWidth = (width - pad * 2) / Math.max(1, n)
  const mid = height / 2
  return records.map((r, i) => {
    const x = pad + barWidth * i + barWidth * 0.1
    const v = r.total_net
    const ratio = v / max
    const h = Math.abs((mid - pad) * ratio)
    const y = ratio >= 0 ? mid - h : mid
    return {
      x,
      y,
      width: barWidth * 0.8,
      height: h || 0.5,
      fill: v >= 0 ? '#ef4444' : '#10b981',
      title: `${r.date}: ${(v / 1e8).toFixed(1)} 億`,
    }
  })
}

const taiexPath = computed(() => buildPath(data.value?.indices?.TAIEX?.history))
const otcPath = computed(() => buildPath(data.value?.indices?.OTC?.history))
const instBars = computed(() => buildBars(data.value?.institutional?.records))
</script>

<template>
  <div>
    <h1 class="text-xl font-bold tracking-tight mb-1">台股大盤</h1>
    <p class="text-xs text-slate-500 mb-5 leading-relaxed">
      加權指數 (TAIEX) + 櫃買指數 (OTC) 即時概況，搭配三大法人近期買賣超彙總。
    </p>

    <div v-if="loading" class="text-slate-500 py-8 text-center">載入中…</div>
    <div v-else-if="error" class="bg-red-50 border border-red-200 p-4 text-sm text-slate-700">
      載入失敗：{{ error }}
    </div>
    <div v-else-if="!data" class="bg-amber-50 border border-amber-200 p-4 text-sm">
      尚無大盤資料 — 請執行 <code class="text-xs">python scripts/fetch_market.py</code> 後重試。
    </div>
    <div v-else>
      <!-- Index cards -->
      <section class="grid sm:grid-cols-2 gap-3 mb-6">
        <div
          v-for="(idx, label) in data.indices"
          :key="label"
          class="bg-white border border-[#e7e7e1] p-4"
        >
          <div class="flex items-baseline justify-between mb-1">
            <div class="font-bold">{{ label === 'TAIEX' ? '加權指數' : '櫃買指數' }}</div>
            <div class="text-xs text-slate-500 font-mono">{{ idx.date }}</div>
          </div>
          <div class="flex items-baseline gap-3">
            <div class="text-2xl font-bold font-mono">{{ fmt(idx.current) }}</div>
            <div :class="idx.change >= 0 ? 'text-red-500' : 'text-emerald-600'" class="font-mono">
              {{ idx.change >= 0 ? '+' : '' }}{{ fmt(idx.change) }}
              <span class="text-sm">({{ idx.change_pct >= 0 ? '+' : '' }}{{ fmt(idx.change_pct) }}%)</span>
            </div>
          </div>
          <div class="text-xs text-slate-500 mt-1">
            1Y 報酬
            <strong :class="idx.return_1y >= 0 ? 'text-red-500' : 'text-emerald-600'">
              {{ idx.return_1y >= 0 ? '+' : '' }}{{ fmt(idx.return_1y, 1) }}%
            </strong>
          </div>
          <svg
            :viewBox="`0 0 ${W} ${H}`"
            preserveAspectRatio="none"
            class="w-full mt-3"
            style="height: 80px"
          >
            <path
              :d="label === 'TAIEX' ? taiexPath : otcPath"
              :stroke="idx.return_1y >= 0 ? '#dc2626' : '#10b981'"
              stroke-width="1.4"
              fill="none"
              stroke-linejoin="round"
              stroke-linecap="round"
            />
          </svg>
          <div class="text-[10px] text-slate-400 font-mono mt-1">近 1 年</div>
        </div>
      </section>

      <!-- Institutional flow -->
      <section v-if="data.institutional.latest" class="bg-white border border-[#e7e7e1] p-4 mb-6">
        <div class="flex items-baseline justify-between mb-3">
          <h2 class="text-base font-semibold">三大法人買賣超</h2>
          <span class="text-xs text-slate-500 font-mono">{{ data.institutional.latest.date }}</span>
        </div>
        <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <div class="text-xs text-slate-500">外資</div>
            <div :class="moneyClass(data.institutional.latest.foreign_net)" class="font-bold font-mono">
              {{ fmtMoney(data.institutional.latest.foreign_net) }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500">投信</div>
            <div :class="moneyClass(data.institutional.latest.trust_net)" class="font-bold font-mono">
              {{ fmtMoney(data.institutional.latest.trust_net) }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500">自營商</div>
            <div :class="moneyClass(data.institutional.latest.dealer_net)" class="font-bold font-mono">
              {{ fmtMoney(data.institutional.latest.dealer_net) }}
            </div>
          </div>
          <div>
            <div class="text-xs text-slate-500">合計</div>
            <div :class="moneyClass(data.institutional.latest.total_net)" class="font-bold font-mono">
              {{ fmtMoney(data.institutional.latest.total_net) }}
            </div>
          </div>
        </div>

        <div v-if="instBars.length" class="mt-4">
          <div class="text-xs text-slate-500 mb-1">近 {{ data.institutional.records.length }} 個交易日合計買賣超</div>
          <svg :viewBox="`0 0 ${W} ${H}`" preserveAspectRatio="none" class="w-full" style="height: 80px">
            <line :x1="PAD" :x2="W - PAD" :y1="H / 2" :y2="H / 2" stroke="#cbd5e1" stroke-width="0.6" stroke-dasharray="3 3" />
            <rect
              v-for="(b, i) in instBars"
              :key="i"
              :x="b.x" :y="b.y" :width="b.width" :height="b.height"
              :fill="b.fill"
            >
              <title>{{ b.title }}</title>
            </rect>
          </svg>
          <div class="flex justify-between text-[10px] text-slate-400 font-mono mt-1">
            <span>{{ data.institutional.records[0]?.date }}</span>
            <span>0</span>
            <span>{{ data.institutional.records[data.institutional.records.length - 1]?.date }}</span>
          </div>
        </div>
      </section>

      <p class="text-xs text-slate-500 leading-relaxed">
        資料更新：{{ data.updated?.replace(/:\d{2}\+\d{2}:\d{2}$/, '') }} · 數值單位 億新台幣（買超為紅，賣超為綠）
      </p>
    </div>
  </div>
</template>
