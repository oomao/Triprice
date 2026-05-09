<script setup>
import { ref, onMounted, computed, provide } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'

const route = useRoute()
const lastUpdated = ref({})

onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/last_updated.json`)
    if (res.ok) lastUpdated.value = await res.json()
  } catch {
    // Silent: file may not exist on first deploy
  }
})

provide('lastUpdated', lastUpdated)

function fmtTime(iso) {
  if (!iso) return ''
  return iso.replace(/:\d{2}\+\d{2}:\d{2}$/, '').replace('T', ' ')
}

const twTime = computed(() => fmtTime(lastUpdated.value.tw))
const usTime = computed(() => fmtTime(lastUpdated.value.us))

const NAV = [
  { to: '/',         label: '清單' },
  { to: '/adr',      label: 'ADR' },
  { to: '/etf',      label: 'ETF' },
  { to: '/screener', label: '選股' },
  { to: '/market',   label: '大盤' },
  { to: '/watchlist',label: '自選' },
  { to: '/settings', label: '設定' },
  { to: '/about',    label: '說明' },
]
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header: charcoal bar, wordmark left, nav tabs right. Active tab gets a thin bottom rule. -->
    <header class="sticky top-0 z-20 text-white" :style="{ background: 'var(--header-bg)' }">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-4">
        <RouterLink to="/" class="shrink-0 flex items-baseline gap-2 group">
          <span class="text-lg font-extrabold tracking-tight">Triprice</span>
          <span class="hidden sm:inline text-[10px] uppercase tracking-[0.18em] text-slate-400 group-hover:text-amber-400 transition">TW · valuation tool</span>
        </RouterLink>
        <nav class="ml-auto flex items-center text-[13px] overflow-x-auto whitespace-nowrap -mr-4 pr-4 sm:mr-0 sm:pr-0 nav-scroll">
          <RouterLink
            v-for="n in NAV"
            :key="n.to"
            :to="n.to"
            class="px-2.5 sm:px-3 py-2 transition relative shrink-0"
            active-class="active-nav"
            :exact-active-class="n.to === '/' ? 'active-nav' : undefined"
          >
            <span class="text-slate-300 hover:text-white">{{ n.label }}</span>
          </RouterLink>
        </nav>
      </div>
    </header>

    <main class="flex-1 max-w-5xl w-full mx-auto px-4 sm:px-6 py-5 sm:py-7 overflow-x-clip">
      <RouterView v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>

    <!-- Footer: thin status bar, looks like a tool, not a marketing page. -->
    <footer class="border-t" :style="{ borderColor: 'var(--rule)', background: 'var(--surface-2)' }">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-600 font-mono">
        <span class="text-[10px] uppercase tracking-widest text-slate-500 font-sans">Triprice</span>
        <span v-if="twTime" class="hidden sm:inline">TW <span class="text-slate-900 font-semibold">{{ twTime }}</span></span>
        <span v-if="usTime" class="hidden sm:inline">ADR <span class="text-slate-900 font-semibold">{{ usTime }}</span></span>
        <span class="ml-auto text-slate-500 font-sans text-[10px] uppercase tracking-widest">資料僅供參考 · 非投資建議</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from,
.fade-leave-to { opacity: 0; }

/* Active nav tab: white text + thin amber underline. */
.active-nav span { color: #ffffff; }
.active-nav::after {
  content: "";
  position: absolute;
  left: 0.625rem;
  right: 0.625rem;
  bottom: 0;
  height: 2px;
  background: #f59e0b;
}

/* Mobile nav: hide scrollbar so the horizontal-scroll fallback at narrow widths
   doesn't leave a 7px scrollbar across every page. */
.nav-scroll {
  scrollbar-width: none;
}
.nav-scroll::-webkit-scrollbar { display: none; }
</style>
