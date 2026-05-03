import { defineStore } from 'pinia'
import { ref, reactive, watch, computed } from 'vue'

const STORAGE_KEY = 'triprice.settings.v1'

const DEFAULTS = {
  theme: 'system',         // 'light' | 'dark' | 'system'
  fontSize: 'normal',      // 'compact' | 'normal' | 'large'
  llmProvider: 'anthropic',// 'anthropic' | 'openai' | 'google'
  llmModel: '',            // empty → use provider default
  apiKeys: { anthropic: '', openai: '', google: '' },
}

const PROVIDER_DEFAULT_MODELS = {
  anthropic: 'claude-haiku-4-5-20251001',
  openai: 'gpt-4o-mini',
  google: 'gemini-2.0-flash',
}

function loadInitial() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return JSON.parse(JSON.stringify(DEFAULTS))
    const parsed = JSON.parse(raw)
    return {
      ...DEFAULTS,
      ...parsed,
      apiKeys: { ...DEFAULTS.apiKeys, ...(parsed.apiKeys || {}) },
    }
  } catch {
    return JSON.parse(JSON.stringify(DEFAULTS))
  }
}

function persist(s) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      theme: s.theme,
      fontSize: s.fontSize,
      llmProvider: s.llmProvider,
      llmModel: s.llmModel,
      apiKeys: { ...s.apiKeys },
    }))
  } catch {
    /* localStorage full or disabled */
  }
}

// Apply theme + fontSize to <html>. Called from store + main.js bootstrap.
export function applyTheme(theme) {
  const root = document.documentElement
  let effective = theme
  if (theme === 'system') {
    effective = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  }
  root.classList.toggle('dark', effective === 'dark')
  root.dataset.theme = effective
}

export function applyFontSize(size) {
  const root = document.documentElement
  root.classList.remove('font-compact', 'font-normal', 'font-large')
  root.classList.add(`font-${size}`)
}

export const useSettingsStore = defineStore('settings', () => {
  const initial = loadInitial()
  const theme = ref(initial.theme)
  const fontSize = ref(initial.fontSize)
  const llmProvider = ref(initial.llmProvider)
  const llmModel = ref(initial.llmModel)
  const apiKeys = reactive({ ...initial.apiKeys })

  // Side effects: apply to DOM and persist on every change.
  watch([theme, fontSize, llmProvider, llmModel, apiKeys], () => {
    applyTheme(theme.value)
    applyFontSize(fontSize.value)
    persist({
      theme: theme.value,
      fontSize: fontSize.value,
      llmProvider: llmProvider.value,
      llmModel: llmModel.value,
      apiKeys,
    })
  }, { deep: true, immediate: false })

  // Track system theme changes if user picked 'system'.
  if (typeof window !== 'undefined' && window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    mq.addEventListener?.('change', () => {
      if (theme.value === 'system') applyTheme('system')
    })
  }

  // Effective model: user override > provider default
  const effectiveModel = computed(() =>
    llmModel.value?.trim() || PROVIDER_DEFAULT_MODELS[llmProvider.value] || ''
  )

  // Has the user configured an API key for the active provider?
  const hasActiveApiKey = computed(() => {
    const k = apiKeys[llmProvider.value]
    return typeof k === 'string' && k.trim().length > 0
  })

  function activeApiKey() {
    return (apiKeys[llmProvider.value] || '').trim()
  }

  function reset() {
    theme.value = DEFAULTS.theme
    fontSize.value = DEFAULTS.fontSize
    llmProvider.value = DEFAULTS.llmProvider
    llmModel.value = DEFAULTS.llmModel
    apiKeys.anthropic = ''
    apiKeys.openai = ''
    apiKeys.google = ''
  }

  return {
    theme, fontSize, llmProvider, llmModel, apiKeys,
    effectiveModel, hasActiveApiKey, activeApiKey, reset,
    PROVIDER_DEFAULT_MODELS,
  }
})
