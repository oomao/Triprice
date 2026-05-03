import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'triprice.watchlist'

export const useWatchlistStore = defineStore('watchlist', () => {
  const initial = (() => {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    } catch {
      return []
    }
  })()

  const codes = ref(initial)

  watch(
    codes,
    (val) => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
    },
    { deep: true }
  )

  function add(code) {
    if (!codes.value.includes(code)) codes.value.push(code)
  }

  function remove(code) {
    codes.value = codes.value.filter((c) => c !== code)
  }

  function toggle(code) {
    if (has(code)) remove(code)
    else add(code)
  }

  function has(code) {
    return codes.value.includes(code)
  }

  return { codes, add, remove, toggle, has }
})
