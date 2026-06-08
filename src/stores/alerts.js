import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'triprice.alerts'

// Per-stock price alerts. A target fires when the latest close ≤ target
// ("等便宜了再買"). Pure front-end: no server, no push — the banner shows when
// the user opens the app. Persisted to localStorage like the watchlist store.
export const useAlertsStore = defineStore('alerts', () => {
  const initial = (() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    } catch {
      return {}
    }
  })()

  const targets = ref(initial) // { [code]: number }

  watch(
    targets,
    (val) => {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
      } catch {}
    },
    { deep: true }
  )

  function set(code, price) {
    const n = Number(price)
    if (!code || !Number.isFinite(n) || n <= 0) return
    targets.value = { ...targets.value, [code]: Math.round(n * 100) / 100 }
  }

  function remove(code) {
    const next = { ...targets.value }
    delete next[code]
    targets.value = next
  }

  function get(code) {
    return targets.value[code] ?? null
  }

  return { targets, set, remove, get }
})
