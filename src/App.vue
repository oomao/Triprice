<script setup>
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-sky-600 text-white shadow sticky top-0 z-10">
      <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
        <RouterLink to="/" class="flex items-center gap-2 font-bold">
          <span class="text-xl">Triprice</span>
          <span class="text-xs opacity-75 hidden sm:inline">三價儀</span>
        </RouterLink>
        <nav class="flex gap-3 sm:gap-5 text-sm">
          <RouterLink to="/" class="hover:underline" active-class="underline">清單</RouterLink>
          <RouterLink to="/watchlist" class="hover:underline" active-class="underline">自選</RouterLink>
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

    <footer class="bg-slate-100 text-slate-500 text-xs text-center py-3 px-4">
      資料僅供參考，非投資建議 · 收盤資料每日更新
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
