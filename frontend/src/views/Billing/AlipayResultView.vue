<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as billingApi from '@/api/billing'
import type { PaymentOrder } from '@/api/billing'

const route = useRoute()
const router = useRouter()
const status = ref<'checking' | 'paid' | 'pending' | 'failed'>('checking')
const message = ref('正在确认支付宝支付结果...')
const order = ref<PaymentOrder | null>(null)
const PAYMENT_RESULT_KEY = 'keliu:alipay-payment-result'

function queryToRecord() {
  const data: Record<string, string> = {}
  for (const [key, value] of Object.entries(route.query)) {
    if (Array.isArray(value)) data[key] = value[0] || ''
    else if (value != null) data[key] = String(value)
  }
  return data
}

function publishPaymentResult(paidOrder: PaymentOrder) {
  localStorage.setItem(PAYMENT_RESULT_KEY, JSON.stringify({ ...paidOrder, syncedAt: Date.now() }))
}

async function confirmPayment() {
  const orderId = typeof route.query.order_id === 'string' ? route.query.order_id : ''
  if (!orderId) {
    status.value = 'failed'
    message.value = '缺少订单号，无法确认支付结果。'
    return
  }

  try {
    const { data } = route.query.sign
      ? await billingApi.confirmAlipayReturn(orderId, queryToRecord())
      : await billingApi.syncAlipayOrder(orderId)
    order.value = data
    if (data.status === 'paid') {
      publishPaymentResult(data)
      status.value = 'paid'
      message.value = '支付成功，原商家端已同步升级套餐。'
      window.opener?.postMessage({ type: 'alipay-payment-result', orderId, status: 'paid' }, window.location.origin)
      setTimeout(() => window.close(), 1200)
      return
    }
    status.value = 'pending'
    message.value = '支付结果暂未同步，请回到原商家端等待自动确认。'
  } catch {
    try {
      const { data } = await billingApi.syncAlipayOrder(orderId)
      order.value = data
      if (data.status === 'paid') {
        publishPaymentResult(data)
        status.value = 'paid'
        message.value = '支付成功，原商家端已同步升级套餐。'
        setTimeout(() => window.close(), 1200)
        return
      }
    } catch {
      // Keep the final failed state below.
    }
    status.value = 'failed'
    message.value = '支付确认失败，请回到原商家端点击刷新状态。'
  }
}

function backToBilling() {
  router.replace('/billing')
}

onMounted(confirmPayment)
</script>

<template>
  <div class="result-page">
    <main class="result-panel">
      <div class="brand-mark">支</div>
      <h1>支付宝支付</h1>
      <div class="status-icon" :class="status">
        <span v-if="status === 'checking'" class="spinner" />
        <span v-else-if="status === 'paid'">✓</span>
        <span v-else-if="status === 'pending'">…</span>
        <span v-else>!</span>
      </div>
      <p class="message">{{ message }}</p>
      <p v-if="order" class="order-line">
        订单 {{ order.id }} · {{ order.planName === 'professional' ? '专业版' : order.planName === 'basic' ? '基础版' : order.planName }}
      </p>
      <button class="primary-btn" @click="backToBilling">返回订阅支付</button>
    </main>
  </div>
</template>

<style scoped>
.result-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #f6f8fb;
  padding: 24px;
}
.result-panel {
  width: min(420px, 100%);
  background: #fff;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.08);
  padding: 32px;
  text-align: center;
}
.brand-mark {
  width: 52px;
  height: 52px;
  margin: 0 auto 12px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: #1677ff;
  color: #fff;
  font-size: 1.5rem;
  font-weight: 800;
}
h1 {
  margin: 0 0 22px;
  font-size: 1.25rem;
  color: #111827;
}
.status-icon {
  width: 64px;
  height: 64px;
  margin: 0 auto 16px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  font-size: 2rem;
  font-weight: 800;
}
.status-icon.checking,
.status-icon.pending {
  background: #eff6ff;
  color: #1677ff;
}
.status-icon.paid {
  background: #ecfdf5;
  color: #009e73;
}
.status-icon.failed {
  background: #fef2f2;
  color: #d55e00;
}
.spinner {
  width: 24px;
  height: 24px;
  border: 3px solid #bfdbfe;
  border-top-color: #1677ff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.message {
  color: #374151;
  font-size: 0.95rem;
  margin: 0;
}
.order-line {
  margin: 10px 0 0;
  color: #9ca3af;
  font-size: 0.78rem;
  word-break: break-all;
}
.primary-btn {
  width: 100%;
  margin-top: 24px;
  padding: 12px 14px;
  border: none;
  border-radius: 8px;
  background: #0072b2;
  color: #fff;
  font-weight: 700;
  cursor: pointer;
}
.primary-btn:hover {
  background: #005f95;
}
</style>
