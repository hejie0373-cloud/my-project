<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as billingApi from '@/api/billing'
import type { Subscription } from '@/api/billing'
import AIChatWidget from '@/components/AIChatWidget.vue'
import { useWebSocket } from '@/composables/useWebSocket'
import { useAuthStore } from '@/stores/auth'
import { useNotificationStore } from '@/stores/notification'

useWebSocket()

const auth = useAuthStore()
const notif = useNotificationStore()
void notif
const router = useRouter()
const route = useRoute()
const PAYMENT_RESULT_KEY = 'keliu:alipay-payment-result'

const merchantSubscription = ref<Subscription | null>(null)

const showNav = computed(() => auth.isLoggedIn && !route.meta.public && !route.path.startsWith('/auth/'))
const isAdmin = computed(() => auth.roles.includes('super_admin'))
const shouldLoadSubscription = computed(() => auth.isLoggedIn && auth.hasStore && !isAdmin.value)
const currentSection = computed(() => {
  if (route.path.startsWith('/dashboard')) return '经营总览'
  if (route.path.startsWith('/customers')) return '客户运营'
  if (route.path.startsWith('/campaigns')) return '营销活动'
  if (route.path.startsWith('/analytics')) return '数据分析'
  if (route.path.startsWith('/billing')) return '订阅支付'
  if (route.path.startsWith('/settings')) return '账号设置'
  if (route.path.startsWith('/admin')) return '平台管理'
  return '工作台'
})
const showQuotaNotice = computed(() => {
  if (!shouldLoadSubscription.value || !merchantSubscription.value) return false
  try {
    const s = merchantSubscription.value
    return s.planName === 'free'
  } catch {
    return false
  }
})

async function loadMerchantSubscription() {
  if (!shouldLoadSubscription.value) {
    merchantSubscription.value = null
    return
  }
  try {
    const { data } = await billingApi.getSubscription()
    merchantSubscription.value = data
  } catch {
    // 订阅信息加载失败不阻塞页面
    merchantSubscription.value = null
  }
}

watch(
  () => [auth.isLoggedIn, auth.user?.storeId],
  () => {
    void loadMerchantSubscription()
  },
  { immediate: true },
)

watch(
  () => route.path,
  () => {
    void loadMerchantSubscription()
  },
)

async function handleLogout() {
  await auth.logout()
  router.push('/auth/signin')
}

async function loadPaymentResult(order: any) {
  if (!auth.isLoggedIn) return
  if (!auth.user?.storeId || auth.user.storeId !== order.storeId) return
  await loadMerchantSubscription()
}

function handleStorage(event: StorageEvent) {
  if (event.key !== PAYMENT_RESULT_KEY || !event.newValue) return
  try {
    const order = JSON.parse(event.newValue)
    void loadPaymentResult(order)
  } catch {
    // ignore malformed data
  }
}

function handleMessage(event: MessageEvent) {
  if (event.origin !== window.location.origin) return
  if (event.data?.type !== 'alipay-payment-result') return
  void loadMerchantSubscription()
}

onMounted(() => {
  window.addEventListener('storage', handleStorage)
  window.addEventListener('message', handleMessage)
})

onBeforeUnmount(() => {
  window.removeEventListener('storage', handleStorage)
  window.removeEventListener('message', handleMessage)
})
</script>

<template>
  <div class="app-shell">
    <aside v-if="showNav" class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">客</span>
        <div class="brand-copy">
          <span class="brand-text">客留</span>
          <span class="brand-sub">Customer OS</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <template v-if="isAdmin">
          <div class="nav-group-title">平台</div>
          <router-link to="/admin" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">⌂</span><span>平台总览</span>
          </router-link>
          <router-link to="/admin/stores" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">店</span><span>店铺管理</span>
          </router-link>
          <router-link to="/admin/payment-orders" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">¥</span><span>支付订单</span>
          </router-link>
          <div class="nav-group-title">账号</div>
          <router-link to="/settings" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">设</span><span>个人中心</span>
          </router-link>
        </template>

        <template v-else>
          <div class="nav-group-title">工作台</div>
          <router-link to="/dashboard" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">仪</span><span>仪表盘</span>
          </router-link>
          <router-link to="/customers" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">客</span><span>客户管理</span>
          </router-link>
          <router-link to="/campaigns" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">营</span><span>营销活动</span>
          </router-link>
          <router-link to="/analytics" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">析</span><span>数据分析</span>
          </router-link>
          <div class="nav-group-title">商业化</div>
          <router-link to="/billing" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">¥</span><span>订阅支付</span>
          </router-link>
          <router-link to="/settings" class="nav-item" active-class="nav-item--active">
            <span class="nav-icon">设</span><span>个人中心</span>
          </router-link>
        </template>
      </nav>

      <div class="sidebar-footer">
        <router-link
          v-if="showQuotaNotice"
          to="/billing"
          class="trial-card"
        >
          <div>
            <div class="trial-title">免费版</div>
            <div class="trial-copy">
              <template v-if="merchantSubscription">
                AI {{ merchantSubscription.aiUsedToday }}/{{ merchantSubscription.aiDailyLimit }} · 活动 {{ merchantSubscription.campaignUsedToday }}/{{ merchantSubscription.campaignDailyLimit }}
              </template>
            </div>
          </div>
          <span class="trial-action">升级</span>
        </router-link>

        <div class="user-card">
          <div class="user-avatar">{{ (auth.user?.name || '客')[0] }}</div>
          <div class="user-meta">
            <div class="user-name">{{ auth.user?.name || auth.user?.phone || '用户' }}</div>
            <div class="user-role">{{ isAdmin ? '管理员' : '商家' }}</div>
          </div>
        </div>
        <button class="logout-btn" @click="handleLogout">退出登录</button>
      </div>
    </aside>

    <main :class="['main-content', { 'main-content--full': !showNav }]">
      <header v-if="showNav" class="topbar">
        <div class="topbar-title">
          <span class="topbar-kicker">{{ currentSection }}</span>
          <h1>{{ isAdmin ? '平台后台' : '商家工作台' }}</h1>
        </div>
        <div class="topbar-actions">
          <router-link v-if="!isAdmin" to="/billing" class="quota-pill">
            <span>当前套餐</span>
            <strong>{{ merchantSubscription?.planDisplayName || merchantSubscription?.planName || '免费版' }}</strong>
          </router-link>
          <button class="ghost-btn" type="button" @click="handleLogout">退出</button>
        </div>
      </header>

      <div :class="showNav ? 'content-frame' : 'content-frame content-frame--full'">
        <router-view />
      </div>
    </main>

    <AIChatWidget v-if="auth.isLoggedIn && !route.meta.public" />
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
  background:
    linear-gradient(180deg, rgba(0, 114, 178, 0.06), transparent 260px),
    var(--bg);
}

.sidebar {
  width: 248px;
  background: #111827;
  color: oklch(1 0 0);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  left: 0;
  bottom: 0;
  z-index: 100;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 76px;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.brand-icon {
  width: 40px;
  height: 40px;
  background: #0072b2;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.2rem;
  font-weight: 700;
  color: white;
}

.brand-copy {
  display: grid;
  gap: 1px;
}

.brand-text {
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: 0;
}

.brand-sub {
  color: rgba(255, 255, 255, 0.42);
  font-size: 0.72rem;
}

.sidebar-nav {
  flex: 1;
  padding: 18px 14px;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.nav-group-title {
  margin: 12px 10px 5px;
  color: rgba(255, 255, 255, 0.38);
  font-size: 0.72rem;
  font-weight: 700;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 42px;
  padding: 10px 12px;
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.66);
  font-size: 0.92rem;
  transition: all 0.15s;
  text-decoration: none;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.07);
  color: rgba(255, 255, 255, 0.92);
}

.nav-item--active {
  background: rgba(0, 114, 178, 0.24);
  color: #fff;
  font-weight: 600;
}

.nav-icon {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
  text-align: center;
  font-size: 0.82rem;
  font-weight: 700;
}

.sidebar-footer {
  padding: 16px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.trial-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.86);
  text-decoration: none;
  background: rgba(0, 114, 178, 0.16);
}

.trial-card--warning {
  border-color: oklch(0.78 0.16 75 / 0.8);
  background: oklch(0.78 0.16 75 / 0.16);
}

.trial-card--danger {
  border-color: oklch(0.62 0.2 25 / 0.85);
  background: oklch(0.62 0.2 25 / 0.16);
}

.trial-title {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.58);
}

.trial-copy {
  margin-top: 2px;
  font-size: 0.9rem;
  font-weight: 700;
}

.trial-action {
  flex-shrink: 0;
  font-size: 0.78rem;
  color: #7dd3fc;
  font-weight: 700;
}

.user-card {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 700;
  flex-shrink: 0;
}

.user-meta {
  min-width: 0;
}

.user-name {
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.9);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.45);
  margin-top: 2px;
}

.logout-btn {
  width: 100%;
  padding: 9px;
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  color: rgba(255, 255, 255, 0.58);
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.15s;
}

.logout-btn:hover {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.9);
  border-color: rgba(255, 255, 255, 0.25);
}

.main-content {
  flex: 1;
  margin-left: 248px;
  min-height: 100vh;
}

.main-content--full {
  margin-left: 0;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 80;
  min-height: 76px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 16px 28px;
  border-bottom: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(246, 248, 251, 0.86);
  backdrop-filter: blur(14px);
}

.topbar-title {
  min-width: 0;
}

.topbar-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.topbar h1 {
  margin: 2px 0 0;
  color: #111827;
  font-size: 1.1rem;
  line-height: 1.2;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.quota-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid #dbe3ec;
  border-radius: 999px;
  background: #fff;
  color: #6b7280;
  font-size: 0.8rem;
  text-decoration: none;
}

.quota-pill strong {
  color: #111827;
}

.ghost-btn {
  height: 36px;
  padding: 0 14px;
  border: 1px solid #dbe3ec;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  cursor: pointer;
}

.ghost-btn:hover {
  border-color: #0072b2;
  color: #0072b2;
}

.content-frame {
  padding: 24px;
}

.content-frame--full {
  padding: 0;
}

@media (max-width: 820px) {
  .sidebar {
    width: 216px;
  }

  .main-content {
    margin-left: 216px;
  }

  .topbar {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .content-frame {
    padding: 16px;
  }
}
</style>
