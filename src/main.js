import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import { applyTheme, applyFontSize } from './stores/settings'

// Apply persisted theme + font size BEFORE Vue mounts to avoid FOUC.
try {
  const raw = localStorage.getItem('triprice.settings.v1')
  const s = raw ? JSON.parse(raw) : {}
  applyTheme(s.theme || 'system')
  applyFontSize(s.fontSize || 'normal')
} catch {
  applyTheme('system')
  applyFontSize('normal')
}

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
