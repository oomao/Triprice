import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// GitHub Pages serves at /<repo-name>/, so set base for production builds.
// Override with VITE_BASE_PATH env var (used by deploy workflow if needed).
const BASE = process.env.VITE_BASE_PATH || '/Triprice/'

export default defineConfig(({ mode }) => ({
  base: mode === 'production' ? BASE : '/',
  plugins: [
    vue(),
    tailwindcss(),
    VitePWA({
      // 'prompt' 才會 fire onNeedRefresh → 觸發 App.vue 的 banner。
      // 'autoUpdate' 模式 plugin 內部直接 window.location.reload(),
      // 不會呼叫 onNeedRefresh,banner 等於 dead code。
      registerType: 'prompt',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'Triprice',
        short_name: 'Triprice',
        description: '台股殖利率法 / PE 法估值，含美股 ADR 比較',
        lang: 'zh-Hant',
        theme_color: '#0ea5e9',
        background_color: '#ffffff',
        display: 'standalone',
        start_url: mode === 'production' ? BASE : '/',
        scope: mode === 'production' ? BASE : '/',
        icons: [
          { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,json}'],
        navigateFallback: mode === 'production' ? `${BASE}index.html` : '/index.html',
        // 不設 clientsClaim / skipWaiting — 配合 'prompt' 模式由 user 點
        // 「重新載入」才觸發 skipWaiting,避免使用者操作到一半被自動切版
        // 造成已 lazy-load 的 chunk 404。
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            // Data JSONs change daily — fetch fresh first, fallback to cache
            // only when offline / network slow. Previously StaleWhileRevalidate
            // showed users yesterday's data until next page load.
            urlPattern: ({ url }) => url.pathname.endsWith('.json'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'data-cache',
              networkTimeoutSeconds: 3,
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 7 }
            }
          }
        ]
      }
    })
  ]
}))
