import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '../services/auth'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/Home.vue'),
      meta: { title: '首页' },
    },
    {
      path: '/market',
      name: 'market',
      component: () => import('../views/MarketQuotesView.vue'),
      meta: { title: '行情' },
    },
    {
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../views/DashboardView.vue'),
      meta: { title: '市场看板' },
    },
    {
      path: '/market/stock',
      name: 'market-stock',
      component: () => import('../views/MarketStockView.vue'),
      meta: { title: '股票日线' },
    },
    {
      path: '/strategies',
      name: 'strategies',
      component: () => import('../views/StrategiesView.vue'),
      meta: { title: '我的策略', requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { title: '注册' },
    },
    {
      path: '/member',
      name: 'member',
      component: () => import('../views/MemberCenterView.vue'),
      meta: { title: '会员中心', requiresAuth: true },
    },
    {
      path: '/report-history',
      name: 'report-history',
      component: () => import('../views/BacktestReportHistoryView.vue'),
      meta: { title: '回测报告历史记录', requiresAuth: true },
    },
    {
      path: '/community',
      name: 'community',
      component: () => import('../views/CommunityView.vue'),
      meta: { title: '社区' },
    },
    {
      path: '/community/new',
      name: 'community-new',
      component: () => import('../views/CommunityNewView.vue'),
      meta: { title: '发帖', requiresAuth: true },
    },
    {
      path: '/community/post/:id',
      name: 'community-post',
      component: () => import('../views/CommunityPostView.vue'),
      meta: { title: '帖子' },
    },
    {
      path: '/docs',
      name: 'docs',
      component: () => import('../views/DocsView.vue'),
      meta: { title: '文档中心' },
    },
    {
      path: '/analytics/compare',
      name: 'strategy-compare',
      component: () => import('../views/StrategyCompareView.vue'),
      meta: { title: '多策略对比' },
    },
    {
      path: '/analytics/screen',
      name: 'factor-screener',
      component: () => import('../views/FactorScreenerView.vue'),
      meta: { title: '因子选股' },
    },
    {
      path: '/analytics/grid',
      name: 'grid-optimize',
      component: () => import('../views/GridOptimizeView.vue'),
      meta: { title: '参数优化' },
    },
    {
      path: '/analytics/realtime',
      name: 'realtime',
      component: () => import('../views/RealtimeView.vue'),
      meta: { title: '实时行情' },
    },
    {
      path: '/analytics/portfolio',
      name: 'portfolio',
      component: () => import('../views/PortfolioView.vue'),
      meta: { title: '组合回测' },
    },
    {
      path: '/analytics/paper',
      name: 'paper-trading',
      component: () => import('../views/PaperTradingView.vue'),
      meta: { title: '纸面交易' },
    },
    {
      path: '/analytics/heatmap',
      name: 'heatmap',
      component: () => import('../views/HeatmapView.vue'),
      meta: { title: '市场热力图' },
    },
  ],
  scrollBehavior(to, _from, saved) {
    if (saved) return saved
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0, behavior: 'smooth' }
  },
})

router.beforeEach((to) => {
  const token = getToken()
  const requiresAuth = Boolean(to.meta?.requiresAuth)

  if ((to.path === '/login' || to.path === '/register') && token) {
    return { path: '/' }
  }

  if (requiresAuth && !token) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  return true
})

router.afterEach((to) => {
  if (to.path === '/') {
    document.title = 'bitDance — Strategy Builder'
    return
  }
  const t = to.meta.title as string | undefined
  document.title = t ? `${t} · bitDance` : 'bitDance'
})

export default router
