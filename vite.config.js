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
      registerType: 'autoUpdate',
      includeAssets: ['icon.svg'],
      manifest: {
        name: 'Triprice — 三價儀',
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
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.endsWith('.json'),
            handler: 'StaleWhileRevalidate',
            options: {
              cacheName: 'data-cache',
              expiration: { maxAgeSeconds: 60 * 60 * 24 * 7 }
            }
          }
        ]
      }
    })
  ]
}))
