import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'home',
    component: () => import('../views/HomeView.vue')
  },
  {
    path: '/watchlist',
    name: 'watchlist',
    component: () => import('../views/WatchlistView.vue')
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
  scrollBehavior() {
    return { top: 0 }
  }
})
