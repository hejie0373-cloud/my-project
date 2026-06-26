import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/auth/signin',
      name: 'SignIn',
      component: () => import('@/views/Auth/SignIn.vue'),
      meta: { guest: true },
    },
    {
      path: '/auth/signup',
      name: 'SignUp',
      component: () => import('@/views/Auth/SignUp.vue'),
      meta: { guest: true },
    },
    { path: '/auth/login', redirect: '/auth/signin' },
    {
      path: '/auth/qr-confirm/:qrId',
      name: 'QrConfirm',
      component: () => import('@/views/Auth/QrConfirmView.vue'),
    },
    {
      path: '/onboarding',
      name: 'Onboarding',
      component: () => import('@/views/Onboarding/OnboardingView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/dashboard',
      name: 'Dashboard',
      component: () => import('@/views/Dashboard/DashboardView.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/customers',
      name: 'CustomerList',
      component: () => import('@/views/Customers/CustomerList.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/customers/:id',
      name: 'CustomerDetail',
      component: () => import('@/views/Customers/CustomerDetail.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/campaigns',
      name: 'CampaignList',
      component: () => import('@/views/Campaigns/CampaignList.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/campaigns/new',
      name: 'CampaignEditor',
      component: () => import('@/views/Campaigns/CampaignEditor.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/analytics',
      name: 'Analytics',
      component: () => import('@/views/Analytics/AnalyticsView.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('@/views/Settings/SettingsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/billing',
      name: 'Billing',
      component: () => import('@/views/Billing/BillingView.vue'),
      meta: { requiresAuth: true, requiresStore: true },
    },
    {
      path: '/payment/alipay/result',
      name: 'AlipayResult',
      component: () => import('@/views/Billing/AlipayResultView.vue'),
      meta: { public: true },
    },
    {
      path: '/admin',
      name: 'Admin',
      component: () => import('@/views/Admin/AdminDashboard.vue'),
      meta: { requiresAuth: true, roles: ['super_admin'] },
    },
    {
      path: '/admin/stores',
      name: 'AdminStores',
      component: () => import('@/views/Admin/AdminStores.vue'),
      meta: { requiresAuth: true, roles: ['super_admin'] },
    },
    {
      path: '/admin/stores/:id',
      name: 'AdminStoreDetail',
      component: () => import('@/views/Admin/AdminStoreDetail.vue'),
      meta: { requiresAuth: true, roles: ['super_admin'] },
    },
    {
      path: '/admin/payment-orders',
      name: 'AdminPaymentOrders',
      component: () => import('@/views/Admin/AdminPaymentOrders.vue'),
      meta: { requiresAuth: true, roles: ['super_admin'] },
    },
    { path: '/', redirect: '/dashboard' },
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

router.beforeEach(async (to, _from, next) => {
  const auth = useAuthStore()
  if (to.meta.public) {
    return next()
  }

  const isAlipayReturn =
    to.path === '/billing' &&
    to.query.payment === 'alipay' &&
    typeof to.query.order_id === 'string'

  // 支付宝回跳必须先进入页面完成公开验签，不能被过期 token 或店铺状态拦截。
  if (isAlipayReturn) {
    return next()
  }

  // 已登录但用户信息未加载 → 拉取
  if (auth.isLoggedIn && !auth.user) {
    await auth.fetchMe()
  }

  // 已登录访问 guest 页面 → 管理员去后台，商家去仪表盘
  if (to.meta.guest && auth.isLoggedIn) {
    if (auth.roles.includes('super_admin')) return next('/admin')
    if (!auth.hasStore) return next('/onboarding')
    return next('/dashboard')
  }

  // 管理员访问商家页面 → 重定向到管理后台
  if (auth.roles.includes('super_admin') && to.path.startsWith('/dashboard')) {
    return next('/admin')
  }

  // 未登录访问需要认证的页面 → 跳转登录（保存原URL）
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return next(`/auth/signin?redirect=${encodeURIComponent(to.fullPath)}`)
  }

  // 已登录但无店铺，访问需要店铺的页面 → 跳转引导
  if (to.meta.requiresStore && auth.isLoggedIn && !auth.hasStore) {
    return next('/onboarding')
  }

  // 需要特定角色的页面
  if (to.meta.roles && auth.isLoggedIn) {
    const required = to.meta.roles as string[]
    const hasRole = auth.roles.some((r) => required.includes(r))
    if (!hasRole) return next('/dashboard')
  }

  next()
})

export default router
