import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue')
  },
  {
    // 自選 merged into the overview table (★ filter); keep old links / home-screen
    // shortcuts working.
    path: '/watchlist',
    redirect: { path: '/', query: { list: 'watch' } }
  },
  {
    path: '/stock/:code',
    name: 'stock-detail',
    component: () => import('../views/StockDetailView.vue'),
    props: true
  },
  {
    path: '/etf',
    name: 'etf',
    component: () => import('../views/ETFListView.vue')
  },
  {
    path: '/screener',
    name: 'screener',
    component: () => import('../views/ScreenerView.vue')
  },
  {
    path: '/market',
    name: 'market',
    component: () => import('../views/MarketView.vue')
  },
  {
    path: '/adr',
    name: 'adr',
    component: () => import('../views/ADRDashboardView.vue')
  },
  {
    path: '/settings',
    name: 'settings',
    component: () => import('../views/SettingsView.vue')
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('../views/AboutView.vue')
  }
]

export default createRouter({
  history: createWebHashHistory(),
  routes,
  scrollBehavior(to, from, saved) {
    // Restore position on back/forward (e.g. returning to a long overview table).
    return saved || { top: 0 }
  }
})
