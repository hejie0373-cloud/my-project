<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import * as billingApi from '@/api/billing'
import type { PaymentOrder, Plan, Subscription } from '@/api/billing'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const plans = ref<Plan[]>([])
const subscription = ref<Subscription | null>(null)
const loading = ref(false)
const payingPlan = ref<string | null>(null)
const payDialog = ref(false)
const payOrder = ref<PaymentOrder | null>(null)
const payStatus = ref<'pending' | 'paying' | 'paid'>('pending')
const PAYMENT_RESULT_KEY = 'keliu:alipay-payment-result'
let paymentPollTimer: ReturnType<typeof window.setInterval> | null = null
let paymentPollCount = 0

function formatPrice(cents: number) {
  if (cents <= 0) return '¥0'
  return `¥${(cents / 100).toFixed(1)}`
}

function aiLabel(plan: Plan) {
  if (plan.aiDailyLimit < 0) return '无上限'
  return `${plan.aiDailyLimit} 次/天`
}

function campaignLabel(plan: Plan) {
  if (plan.campaignDailyLimit < 0) return '无上限'
  return `${plan.campaignDailyLimit} 次/天`
}

function aiUsedLabel(s: Subscription) {
  if (s.aiDailyLimit < 0) return '无上限'
  return `${s.aiUsedToday}/${s.aiDailyLimit} 次`
}

function campaignUsedLabel(s: Subscription) {
  if (s.campaignDailyLimit < 0) return '无上限'
  return `${s.campaignUsedToday}/${s.campaignDailyLimit} 次`
}

function isCurrentPlan(p: Plan) {
  return subscription.value?.planName === p.code
}

const currentPlanMeta = computed(() => {
  if (!subscription.value) return null
  const s = subscription.value
  return {
    name: s.planDisplayName || s.planName,
    status: s.isActive ? '已激活' : '已过期',
    active: s.isActive,
    ai: aiUsedLabel(s),
    campaign: campaignUsedLabel(s),
    export: s.hasExport ? '支持' : '不支持',
    billing: s.nextBillingDate || '—',
  }
})

async function load() {
  loading.value = true
  try {
    const [pr, sr] = await Promise.all([billingApi.getPlans(), billingApi.getSubscription()])
    plans.value = pr.data
    subscription.value = sr.data
  } finally { loading.value = false }
}

async function reloadIfCurrentStore(order: PaymentOrder) {
  if (auth.user?.storeId !== order.storeId) return
  await load()
}

function stopPaymentPolling() {
  if (paymentPollTimer) {
    window.clearInterval(paymentPollTimer)
    paymentPollTimer = null
  }
  paymentPollCount = 0
}

function startPaymentPolling(orderId: string) {
  stopPaymentPolling()
  paymentPollTimer = window.setInterval(async () => {
    paymentPollCount += 1
    if (paymentPollCount > 120) {
      stopPaymentPolling()
      return
    }
    await refreshPaymentOrder(orderId, false, true, true)
  }, 3000)
}

function publishPaymentResult(order: PaymentOrder) {
  localStorage.setItem(PAYMENT_RESULT_KEY, JSON.stringify({ ...order, syncedAt: Date.now() }))
}

function showPaidOrder(order: PaymentOrder, broadcast = false) {
  stopPaymentPolling()
  payOrder.value = order
  payDialog.value = true
  payStatus.value = 'paid'
  if (broadcast) publishPaymentResult(order)
  ElMessage.success('支付成功，套餐已升级')
  setTimeout(async () => {
    payDialog.value = false
    clearPaymentQuery()
    await reloadIfCurrentStore(order)
  }, 1000)
}

function handlePaymentResultMessage(event: StorageEvent) {
  if (event.key !== PAYMENT_RESULT_KEY || !event.newValue || !payOrder.value) return
  try {
    const order = JSON.parse(event.newValue) as PaymentOrder
    if (order.id === payOrder.value.id && order.status === 'paid') {
      showPaidOrder(order)
    }
  } catch {
    // Ignore unrelated localStorage data.
  }
}

async function upgrade(plan: Plan) {
  if (plan.priceCents <= 0 || isCurrentPlan(plan)) return
  payingPlan.value = plan.code
  try {
    const { data: order } = await billingApi.createOrder(plan.code, 'alipay')
    if (!order.checkoutUrl) {
      throw new Error('支付宝收银台地址生成失败')
    }
    payOrder.value = order
    payStatus.value = order.status === 'paid' ? 'paid' : 'pending'
    payDialog.value = true
    startPaymentPolling(order.id)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '创建订单失败')
  } finally { payingPlan.value = null }
}

function reopenAlipayCashier() {
  if (payOrder.value?.checkoutUrl) {
    payStatus.value = 'paying'
    startPaymentPolling(payOrder.value.id)
    window.open(payOrder.value.checkoutUrl, '_blank', 'noopener,noreferrer')
  }
}

async function refreshPaymentOrder(orderId: string, fromReturn = false, syncAlipay = false, silent = false) {
  try {
    const { data } = syncAlipay
      ? await billingApi.syncAlipayOrder(orderId)
      : await billingApi.getOrder(orderId)
    payOrder.value = data
    payDialog.value = true
    if (data.status === 'paid') {
      showPaidOrder(data)
    } else {
      payStatus.value = 'paying'
      if (fromReturn) {
        ElMessage.info('支付结果尚未同步，请稍后刷新状态')
      }
    }
  } catch {
    if (!silent) ElMessage.error('查询失败')
  }
}

async function checkPayStatus() {
  if (!payOrder.value) return
  await refreshPaymentOrder(payOrder.value.id, false, true)
}

function closePay() {
  stopPaymentPolling()
  payDialog.value = false
  clearPaymentQuery()
}

function clearPaymentQuery() {
  if (window.location.search.includes('order_id=')) {
    window.history.replaceState({}, '', window.location.pathname)
  }
}

function searchParamsToRecord(params: URLSearchParams) {
  const data: Record<string, string> = {}
  params.forEach((value, key) => { data[key] = value })
  return data
}

async function confirmAlipayReturn(orderId: string, params: URLSearchParams) {
  if (!params.get('sign')) {
    await refreshPaymentOrder(orderId, true, true)
    return
  }
  try {
    const { data } = await billingApi.confirmAlipayReturn(orderId, searchParamsToRecord(params))
    payOrder.value = data
    payDialog.value = true
    if (data.status === 'paid') {
      showPaidOrder(data, true)
    } else {
      payStatus.value = 'paying'
      ElMessage.info('支付结果尚未同步，请稍后刷新状态')
    }
  } catch {
    await refreshPaymentOrder(orderId, true, true)
  }
}

onMounted(async () => {
  window.addEventListener('storage', handlePaymentResultMessage)
  const params = new URLSearchParams(window.location.search)
  const orderId = params.get('order_id')
  if (params.get('payment') === 'alipay' && orderId) {
    await confirmAlipayReturn(orderId, params)
    return
  }
  await load()
})

onBeforeUnmount(() => {
  stopPaymentPolling()
  window.removeEventListener('storage', handlePaymentResultMessage)
})
</script>

<template>
  <div class="billing-page" v-loading="loading">
    <header class="page-hero">
      <span class="hero-kicker">订阅支付</span>
      <h1 class="hero-title">订阅与支付</h1>
      <p class="hero-desc">查看当前套餐、每日配额和支付状态，按经营阶段升级功能能力。</p>
    </header>

    <!-- 当前套餐状态条 -->
    <div v-if="currentPlanMeta" class="status-bar">
      <div class="status-main">
        <span class="status-badge" :class="{ active: currentPlanMeta.active }">
          {{ currentPlanMeta.active ? '●' : '○' }} {{ currentPlanMeta.status }}
        </span>
        <span class="status-plan-name">{{ currentPlanMeta.name }}</span>
      </div>
      <div class="status-items">
        <div class="status-item">
          <span class="status-label">AI 用量</span>
          <span class="status-value">{{ currentPlanMeta.ai }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">营销活动</span>
          <span class="status-value">{{ currentPlanMeta.campaign }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">数据导出</span>
          <span class="status-value">{{ currentPlanMeta.export }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">到期时间</span>
          <span class="status-value">{{ currentPlanMeta.billing }}</span>
        </div>
      </div>
    </div>

    <!-- 套餐卡片 -->
    <section class="plan-cards">
      <article
        v-for="plan in plans" :key="plan.code"
        class="plan-card"
        :class="{
          'plan-card--current': isCurrentPlan(plan),
          'plan-card--premium': plan.code === 'professional',
        }"
      >
        <!-- 角标 -->
        <div v-if="plan.code === 'professional'" class="plan-ribbon">推荐</div>
        <div v-if="isCurrentPlan(plan)" class="plan-ribbon plan-ribbon--current">当前</div>

        <!-- 头部 -->
        <div class="plan-header">
          <div class="plan-icon" :class="'plan-icon--' + plan.code">
            {{ { free: '🌟', basic: '⚡', professional: '💎' }[plan.code] }}
          </div>
          <div>
            <h2 class="plan-name">{{ plan.name }}</h2>
            <p class="plan-sub">最多 {{ plan.customerLimit.toLocaleString() }} 位客户</p>
          </div>
        </div>

        <!-- 价格 -->
        <div class="plan-price-row">
          <span class="plan-price">{{ formatPrice(plan.priceCents) }}</span>
          <span v-if="plan.priceCents > 0" class="plan-period">/月</span>
        </div>

        <!-- 功能列表 -->
        <ul class="plan-features">
          <li><span class="feat-dot" />AI 评分+文案：{{ aiLabel(plan) }}</li>
          <li><span class="feat-dot" />营销活动：{{ campaignLabel(plan) }}</li>
          <li><span class="feat-dot" />数据分析：支持</li>
          <li><span :class="plan.hasExport ? 'feat-dot' : 'feat-dot feat-dot--off'" />数据导出：{{ plan.hasExport ? '支持' : '不支持' }}</li>
        </ul>

        <!-- 按钮 -->
        <button
          v-if="isCurrentPlan(plan)"
          class="plan-btn plan-btn--current"
          disabled
        >当前套餐</button>
        <button
          v-else-if="plan.priceCents === 0"
          class="plan-btn plan-btn--free"
          disabled
        >默认套餐</button>
        <button
          v-else
          class="plan-btn plan-btn--upgrade"
          :disabled="payingPlan !== null"
          @click="upgrade(plan)"
        >
          <template v-if="payingPlan === plan.code">处理中...</template>
          <template v-else>立即升级</template>
        </button>
      </article>
    </section>

    <div class="billing-footer">
      <p>升级后每日配额立即生效。</p>
    </div>

    <!-- 支付弹窗 -->
    <el-dialog v-model="payDialog" width="440px" :close-on-click-modal="false" :show-close="false">
      <div class="pay-modal">
        <!-- 支付成功状态 -->
        <div v-if="payStatus === 'paid'" class="pay-success">
          <div class="success-icon">✓</div>
          <h3>支付成功</h3>
          <p>套餐已开通，正在刷新...</p>
        </div>

        <!-- 支付中 -->
        <template v-else>
          <!-- 头部品牌 -->
          <div class="pay-brand">
            <span class="alipay-logo">
              <svg viewBox="0 0 1024 1024" width="22" height="22" fill="#fff"><path d="M230.4 576c128 51.2 281.6 89.6 358.4 51.2 51.2-25.6 89.6-64 115.2-115.2H384v-38.4h179.2v-64H320v-38.4h243.2V256h89.6v76.8H832v38.4H652.8v64H806.4s-12.8 102.4-64 166.4c89.6 38.4 153.6 64 153.6 64V256c0-70.6-57.4-128-128-128H256c-70.6 0-128 57.4-128 128v512c0 70.6 57.4 128 128 128h512c64 0 116.8-47 126.4-108.8 0 0-281.6-115.2-384-153.6-64 76.8-166.4 102.4-256 76.8-115.2-38.4-89.6-204.8 76.8-166.4z"/></svg>
            </span>
            <div>
            <div class="pay-brand-name">支付宝支付</div>
            <div class="pay-brand-sub">安全 · 便捷的在线支付</div>
          </div>
          </div>

          <!-- 订单信息 -->
          <div class="pay-info">
            <div class="pay-plan-name">
              {{ payOrder?.planName === 'basic' ? '基础版' : payOrder?.planName === 'professional' ? '专业版' : payOrder?.planName }}
            </div>
            <div class="pay-amount">¥{{ ((payOrder?.amountCents || 0) / 100).toFixed(2) }}</div>
            <div class="pay-period">/ 月</div>
          </div>

          <!-- 状态提示 -->
          <div class="pay-tip" :class="payStatus">
            <template v-if="payStatus === 'paying'">
              <span class="tip-spin" />等待支付宝异步通知，请稍后刷新支付状态
            </template>
            <template v-else>
              请使用下方沙箱买家账号登录支付宝收银台完成支付
            </template>
          </div>

          <!-- 主按钮 -->
          <button class="pay-main-btn" @click="reopenAlipayCashier">
            {{ payStatus === 'paying' ? '重新打开支付宝收银台' : '打开支付宝沙箱收银台' }}
          </button>

          <!-- 沙箱提示 -->
          <div class="pay-sandbox-hint">
            <div class="hint-title">支付宝沙箱收银台</div>
            <div class="hint-row">请在支付宝官方页面完成登录与付款，支付成功后返回本页会自动同步套餐。</div>
            <div class="hint-row">沙箱买家账号：kgwjyh8559@sandbox.com</div>
            <div class="hint-row">支付密码：111111</div>
          </div>

          <!-- 次要操作 -->
          <div class="pay-sub-actions">
            <button class="sub-btn" @click="checkPayStatus">已完成支付，刷新状态</button>
          </div>

          <button class="pay-cancel" @click="closePay">取消</button>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.billing-page {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 24px 24px 40px;
}

/* Hero */
.page-hero { margin: 0; }
.hero-kicker { color: #0072b2; font-size: 0.78rem; font-weight: 800; }
.hero-title { font-size: 1.5rem; font-weight: 700; color: #111827; margin: 8px 0 0; }
.hero-desc { max-width: 660px; color: #6b7280; font-size: 0.92rem; margin-top: 10px; }

/* Status bar */
.status-bar {
  background: #fff; border: 1px solid #e3e8ef; border-radius: 8px;
  padding: 18px;
  display: flex; align-items: center; gap: 32px; flex-wrap: wrap;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
}
.status-main { display: flex; align-items: center; gap: 10px; }
.status-badge {
  font-size: 0.78rem; font-weight: 700; padding: 4px 10px; border-radius: 999px;
  background: #fef2f2; color: #d55e00;
}
.status-badge.active { background: #ecfdf5; color: #009e73; }
.status-plan-name { font-size: 1.05rem; font-weight: 700; color: #111827; }
.status-items { display: flex; gap: 28px; flex-wrap: wrap; margin-left: auto; }
.status-item { text-align: center; }
.status-label { display: block; font-size: 0.73rem; color: #9CA3AF; margin-bottom: 2px; }
.status-value { font-size: 0.88rem; font-weight: 600; color: #1a1a2e; }

/* Plan cards */
.plan-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-bottom: 0;
}
@media (max-width: 860px) { .plan-cards { grid-template-columns: 1fr; } }

.plan-card {
  background: #fff;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  padding: 32px 26px 28px;
  position: relative;
  overflow: hidden;
  transition: all 0.25s;
  display: flex; flex-direction: column;
}
.plan-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(15,23,42,0.08); }
.plan-card--current {
  border-color: #0072b2;
  box-shadow: 0 0 0 1px #0072b2, 0 4px 16px rgba(0,114,178,0.08);
}
.plan-card--premium {
  background: linear-gradient(180deg, #f8fbfd 0%, #fff 30%);
}

/* Ribbon */
.plan-ribbon {
  position: absolute; top: 14px; right: -32px;
  background: #d55e00; color: #fff;
  font-size: 0.72rem; font-weight: 700;
  padding: 3px 36px;
  transform: rotate(45deg);
  letter-spacing: 0.05em;
  box-shadow: 0 2px 4px rgba(249,115,22,0.3);
}
.plan-ribbon--current { background: #0072b2; box-shadow: 0 2px 4px rgba(0,114,178,0.3); }

/* Header */
.plan-header { display: flex; align-items: center; gap: 14px; margin-bottom: 20px; }
.plan-icon {
  width: 44px; height: 44px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  font-size: 1.3rem; flex-shrink: 0;
}
.plan-icon--free { background: #F3F4F6; }
.plan-icon--basic { background: #e6f2f8; }
.plan-icon--professional { background: linear-gradient(135deg, #e6f2f8 0%, #ecfdf5 100%); }
.plan-name { font-size: 1.05rem; font-weight: 700; color: #111827; margin: 0; }
.plan-sub { font-size: 0.76rem; color: #9CA3AF; margin: 2px 0 0; }

/* Price */
.plan-price-row { margin-bottom: 22px; display: flex; align-items: baseline; gap: 2px; }
.plan-price { font-size: 2rem; font-weight: 800; color: #0072b2; line-height: 1; }
.plan-period { font-size: 0.85rem; color: #9CA3AF; }

/* Features */
.plan-features { list-style: none; padding: 0; margin: 0 0 24px; flex: 1; }
.plan-features li {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 0; border-bottom: 1px solid #F9FAFB;
  font-size: 0.87rem; color: #4B5563;
}
.plan-features li:last-child { border-bottom: none; }
.feat-dot {
  width: 6px; height: 6px; border-radius: 50%; background: #0072b2;
  flex-shrink: 0; margin-right: 2px;
}
.feat-dot--off { background: #D1D5DB; }

/* Buttons */
.plan-btn {
  width: 100%; padding: 13px; border-radius: 8px; border: none;
  font-size: 0.92rem; font-weight: 600; cursor: pointer;
  transition: all 0.2s;
}
.plan-btn--current { background: #F3F4F6; color: #6B7280; }
.plan-btn--free { background: #F9FAFB; color: #9CA3AF; }
.plan-btn--upgrade {
  background: #0072b2; color: #fff;
  box-shadow: 0 4px 12px rgba(0,114,178,0.2);
}
.plan-btn--upgrade:hover { background: #005f95; }
.plan-btn--upgrade:disabled { opacity: 0.6; cursor: not-allowed; }

/* Footer */
.billing-footer { text-align: center; }
.billing-footer p { font-size: 0.82rem; color: #9CA3AF; margin: 0; }

/* Pay modal */
.pay-modal { text-align: center; padding: 8px 4px; }

/* 成功 */
.pay-success { padding: 30px 0; }
.success-icon { width: 64px; height: 64px; border-radius: 50%; background: #16A34A; color: #fff; font-size: 2rem; display: flex; align-items: center; justify-content: center; margin: 0 auto 16px; }
.pay-success h3 { margin: 0 0 6px; font-size: 1.2rem; color: #1a1a2e; }
.pay-success p { color: #9CA3AF; font-size: 0.88rem; margin: 0; }

/* 品牌 */
.pay-brand { display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 24px; }
.alipay-logo { width: 44px; height: 44px; border-radius: 12px; background: #1677FF; display: flex; align-items: center; justify-content: center; }
.pay-brand-name { font-size: 1.05rem; font-weight: 700; color: #1a1a2e; text-align: left; }
.pay-brand-sub { font-size: 0.76rem; color: #9CA3AF; text-align: left; }

/* 订单信息 */
.pay-info { display: flex; align-items: baseline; justify-content: center; gap: 8px; margin-bottom: 20px; padding: 20px; background: linear-gradient(135deg, #EFF6FF, #F5F3FF); border-radius: 14px; }
.pay-plan-name { font-size: 0.95rem; color: #6B7280; font-weight: 600; }
.pay-amount { font-size: 2.2rem; font-weight: 800; color: #1677FF; }
.pay-period { font-size: 0.85rem; color: #9CA3AF; }

/* 状态提示 */
.pay-tip { font-size: 0.85rem; color: #6B7280; margin-bottom: 16px; display: flex; align-items: center; justify-content: center; gap: 8px; min-height: 20px; }
.pay-tip.paying { color: #1677FF; }
.tip-spin { width: 14px; height: 14px; border: 2px solid #DBEAFE; border-top-color: #1677FF; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 主按钮 */
.pay-main-btn {
  width: 100%; padding: 14px; border-radius: 12px; border: none;
  background: #1677FF; color: #fff; font-size: 1rem; font-weight: 600;
  cursor: pointer; transition: background 0.2s; margin-bottom: 16px;
  box-shadow: 0 4px 14px rgba(22,119,255,0.3);
}
.pay-main-btn:hover { background: #0E5FD8; }

/* 沙箱提示 */
.pay-sandbox-hint { background: #F9FAFB; border: 1px dashed #E5E7EB; border-radius: 10px; padding: 12px 16px; margin-bottom: 16px; text-align: left; }
.hint-title { font-size: 0.82rem; font-weight: 600; color: #374151; margin-bottom: 6px; }
.hint-row { font-size: 0.78rem; color: #9CA3AF; line-height: 1.6; font-family: monospace; }

/* 次要操作 */
.pay-sub-actions { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.sub-btn {
  width: 100%; padding: 10px; border-radius: 10px; border: 1px solid #E5E7EB;
  background: #fff; color: #374151; font-size: 0.85rem; cursor: pointer; transition: all 0.2s;
}
.sub-btn:hover { border-color: #1677FF; color: #1677FF; }
.sub-btn--mock { border-style: dashed; color: #9CA3AF; }
.sub-btn--mock:hover { border-color: #16A34A; color: #16A34A; }

.pay-cancel { background: none; border: none; color: #9CA3AF; font-size: 0.82rem; cursor: pointer; padding: 4px; }
.pay-cancel:hover { color: #6B7280; }
</style>
