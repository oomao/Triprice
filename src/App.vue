<script setup>
import { ref, onMounted, onBeforeUnmount, computed, provide } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
// vite-plugin-pwa virtual module: tracks SW update lifecycle.
// `needRefresh` flips to true when a new SW has been downloaded and is
// waiting; calling updateSW(true) triggers skipWaiting + reload so the user
// jumps to the new version without manually clearing cache.
import { useRegisterSW } from 'virtual:pwa-register/vue'
import { fetchData } from './lib/data.js'
import StockSearch from './components/StockSearch.vue'

// Track the SW registration so we can ping it on visibility / hourly poll.
const swRegistration = ref(null)

const { needRefresh, updateServiceWorker } = useRegisterSW({
  immediate: true,
  onRegisteredSW(_url, registration) {
    if (!registration) return
    swRegistration.value = registration
  },
})

// 三層觸發更新檢查的 layer 2 + 3 — 都掛在 mount 時、unmount 時 cleanup。
// App 是 root component 不會卸載,但 lifecycle 對齊比較好維護。
let swPollIntervalId
function onVisibilityChange() {
  if (!document.hidden) {
    swRegistration.value?.update().catch(() => {})
  }
}

onMounted(() => {
  swPollIntervalId = setInterval(() => {
    swRegistration.value?.update().catch(() => {})
  }, 60 * 60 * 1000)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onBeforeUnmount(() => {
  clearInterval(swPollIntervalId)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})

function applyUpdate() {
  updateServiceWorker(true) // reloads the page with the new SW active
}

function dismissUpdate() {
  needRefresh.value = false
}

const route = useRoute()
const lastUpdated = ref({})

onMounted(async () => {
  try {
    lastUpdated.value = (await fetchData('last_updated.json', { optional: true })) || {}
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

// Primary destinations. 自選 now lives inside 總覽 (★ filter); 設定 / 說明 are
// header icons so the nav fits a phone without horizontal scrolling.
const NAV = [
  { to: '/',         label: '總覽', icon: 'M3 4h14M3 10h14M3 16h9' },
  { to: '/adr',      label: '夜盤', icon: 'M15 11.5A6 6 0 1 1 8.5 5a4.7 4.7 0 0 0 6.5 6.5Z' },
  { to: '/etf',      label: 'ETF',  icon: 'M4 16V9m4 7V5m4 11v-5m4 5V7' },
  { to: '/screener', label: '選股', icon: 'M3 5h14l-5 6v5l-4 1v-6L3 5Z' },
  { to: '/market',   label: '大盤', icon: 'M3 15l4-5 3 3 6-7M13 6h3v3' },
]
const isActive = (to) => (to === '/' ? route.path === '/' : route.path.startsWith(to))
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- Header: charcoal bar — wordmark, primary tabs (desktop), global search, settings / help. -->
    <header class="sticky top-0 z-20 text-white" :style="{ background: 'var(--header-bg)' }">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center gap-3 sm:gap-5">
        <RouterLink to="/" class="shrink-0 flex items-baseline gap-2 group">
          <span class="text-lg font-extrabold tracking-tight">Triprice</span>
          <span class="hidden lg:inline text-[10px] uppercase tracking-[0.18em] text-slate-400 group-hover:text-amber-400 transition">TW · valuation tool</span>
        </RouterLink>
        <nav class="hidden md:flex items-center text-[13px] h-full">
          <RouterLink
            v-for="n in NAV"
            :key="n.to"
            :to="n.to"
            class="px-3 h-full flex items-center transition relative"
            :class="isActive(n.to) ? 'active-nav' : ''"
          >
            <span class="text-slate-300 hover:text-white">{{ n.label }}</span>
          </RouterLink>
        </nav>
        <div class="flex-1 min-w-0 md:max-w-xs md:ml-auto">
          <StockSearch />
        </div>
        <div class="flex items-center gap-1 shrink-0 -mr-2">
          <RouterLink to="/settings" class="icon-btn" :class="{ 'icon-active': route.path === '/settings' }" aria-label="設定" title="設定">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" class="w-[18px] h-[18px]"><circle cx="10" cy="10" r="2.6" /><path d="M10 2.5v2M10 15.5v2M2.5 10h2M15.5 10h2M4.7 4.7l1.4 1.4M13.9 13.9l1.4 1.4M4.7 15.3l1.4-1.4M13.9 6.1l1.4-1.4" stroke-linecap="round" /></svg>
          </RouterLink>
          <RouterLink to="/about" class="icon-btn" :class="{ 'icon-active': route.path === '/about' }" aria-label="說明" title="說明">
            <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" class="w-[18px] h-[18px]"><circle cx="10" cy="10" r="7.5" /><path d="M7.9 7.8a2.2 2.2 0 1 1 3 2.05c-.55.22-.9.7-.9 1.3v.35" stroke-linecap="round" /><circle cx="10" cy="14.2" r=".6" fill="currentColor" /></svg>
          </RouterLink>
        </div>
      </div>
    </header>

    <main class="flex-1 max-w-6xl w-full mx-auto px-4 sm:px-6 py-5 sm:py-7 overflow-x-clip">
      <RouterView v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>

    <!-- Update banner: shows when a newer SW is downloaded and waiting.
         Sticky bottom, dismissable. Solves the "PWA cache shows old build" pain. -->
    <transition name="fade">
      <div
        v-if="needRefresh"
        class="fixed inset-x-0 bottom-[calc(3.5rem+env(safe-area-inset-bottom))] md:bottom-0 z-30 px-4 pb-3 pt-3 sm:pb-4"
        role="status"
        aria-live="polite"
      >
        <div class="max-w-md mx-auto bg-slate-900 text-slate-100 border border-amber-400 shadow-lg flex items-center gap-3 px-4 py-3 text-sm">
          <span class="text-amber-400">●</span>
          <span class="flex-1">新版本已就緒</span>
          <button
            type="button"
            @click="dismissUpdate"
            class="text-xs text-slate-400 hover:text-slate-200 px-2 py-1"
          >稍後</button>
          <button
            type="button"
            @click="applyUpdate"
            class="text-xs font-semibold bg-amber-400 text-slate-900 hover:bg-amber-300 px-3 py-1.5"
          >重新載入</button>
        </div>
      </div>
    </transition>

    <!-- Footer: thin status bar, looks like a tool, not a marketing page. -->
    <footer class="border-t mb-[calc(3.5rem+env(safe-area-inset-bottom))] md:mb-0" :style="{ borderColor: 'var(--rule)', background: 'var(--surface-2)' }">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 py-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-600 font-mono">
        <span class="text-[10px] uppercase tracking-widest text-slate-500 font-sans">Triprice</span>
        <span v-if="twTime" class="hidden sm:inline">TW <span class="text-slate-900 font-semibold">{{ twTime }}</span></span>
        <span v-if="usTime" class="hidden sm:inline">ADR <span class="text-slate-900 font-semibold">{{ usTime }}</span></span>
        <span class="ml-auto text-slate-500 font-sans text-[10px] uppercase tracking-widest">資料僅供參考 · 非投資建議</span>
      </div>
    </footer>

    <!-- Mobile tab bar: thumb-reachable primary navigation (PWA-friendly). -->
    <nav
      class="md:hidden fixed inset-x-0 bottom-0 z-20 border-t grid grid-cols-5"
      :style="{ background: 'var(--surface)', borderColor: 'var(--rule)', paddingBottom: 'env(safe-area-inset-bottom)' }"
      aria-label="主選單"
    >
      <RouterLink
        v-for="n in NAV"
        :key="n.to"
        :to="n.to"
        class="h-14 flex flex-col items-center justify-center gap-0.5 text-[10px] transition"
        :class="isActive(n.to) ? 'tab-active' : 'text-slate-500'"
      >
        <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" class="w-5 h-5"><path :d="n.icon" /></svg>
        {{ n.label }}
      </RouterLink>
    </nav>
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
  left: 0.75rem;
  right: 0.75rem;
  bottom: 0;
  height: 2px;
  background: #f59e0b;
}

.icon-btn {
  width: 2.25rem;
  height: 2.25rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 0.375rem;
  color: #94a3b8;
  transition: color 0.15s, background-color 0.15s;
}
.icon-btn:hover { color: #fff; background: rgb(255 255 255 / 0.08); }
.icon-active { color: #f59e0b; }

.tab-active { color: var(--accent); font-weight: 600; }
</style>
