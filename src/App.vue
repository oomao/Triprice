<script setup>
import { ref, onMounted, computed, provide } from 'vue'
import { RouterLink, RouterView } from 'vue-router'

const lastUpdated = ref({})

onMounted(async () => {
  try {
    const res = await fetch(`${import.meta.env.BASE_URL}data/last_updated.json`)
    if (res.ok) lastUpdated.value = await res.json()
  } catch {
    // Silently ignore — file may not exist on first deploy
  }
})

// Share with child views (HomeView etc.)
provide('lastUpdated', lastUpdated)

function fmtTime(iso) {
  if (!iso) return ''
  return iso.replace(/:\d{2}\+\d{2}:\d{2}$/, '').replace('T', ' ')
}

const twTime = computed(() => fmtTime(lastUpdated.value.tw))
const usTime = computed(() => fmtTime(lastUpdated.value.us))
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-sky-600 text-white shadow sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        <RouterLink to="/" class="flex items-center gap-2 font-bold">
          <span class="text-xl">Triprice</span>
        </RouterLink>
        <nav class="flex gap-3 sm:gap-5 text-sm">
          <RouterLink to="/" class="hover:underline" active-class="underline">清單</RouterLink>
          <RouterLink to="/watchlist" class="hover:underline" active-class="underline">自選</RouterLink>
          <RouterLink to="/adr" class="hover:underline" active-class="underline">ADR 訊號</RouterLink>
          <RouterLink to="/about" class="hover:underline" active-class="underline">說明</RouterLink>
        </nav>
      </div>
    </header>

    <main class="flex-1 max-w-5xl w-full mx-auto px-4 py-5">
      <RouterView v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </RouterView>
    </main>

    <footer class="bg-slate-100 text-slate-500 text-xs text-center py-3 px-4 leading-relaxed">
      <div>資料僅供參考，非投資建議</div>
      <div v-if="twTime || usTime" class="mt-1 text-[11px]">
        <span v-if="twTime">台股更新 {{ twTime }}</span>
        <span v-if="twTime && usTime" class="mx-1">·</span>
        <span v-if="usTime">ADR 更新 {{ usTime }}</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
