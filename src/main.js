import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { applyTheme, applyFontSize } from './stores/settings'

// Read persisted settings once at boot. Used by both the early apply
// (FOUC avoidance) and the OS-theme media-query listener below.
function readPersistedTheme() {
  try {
    const raw = localStorage.getItem('triprice.settings.v1')
    return raw ? (JSON.parse(raw).theme || 'system') : 'system'
  } catch {
    return 'system'
  }
}

try {
  const raw = localStorage.getItem('triprice.settings.v1')
  const s = raw ? JSON.parse(raw) : {}
  applyTheme(s.theme || 'system')
  applyFontSize(s.fontSize || 'normal')
} catch {
  applyTheme('system')
  applyFontSize('normal')
}

// Listen for OS-level dark/light flips even when the user never opened
// the Settings page (which would otherwise be the first place the store
// gets instantiated). Re-applies only when current preference is 'system'.
if (typeof window !== 'undefined' && window.matchMedia) {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  const handler = () => {
    if (readPersistedTheme() === 'system') applyTheme('system')
  }
  if (mq.addEventListener) mq.addEventListener('change', handler)
  else if (mq.addListener) mq.addListener(handler) // legacy Safari
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
