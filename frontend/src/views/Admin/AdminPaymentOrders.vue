<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as billingApi from '@/api/billing'
import type { AdminPaymentSummary, PaymentOrder } from '@/api/billing'

const orders = ref<PaymentOrder[]>([])
const summary = ref<AdminPaymentSummary | null>(null)
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const status = ref('')

const statusOptions = [
  { value: '', label: '全部订单' },
  { value: 'pending', label: '待支付' },
  { value: 'paid', label: '已支付' },
  { value: 'failed', label: '支付失败' },
  { value: 'cancelled', label: '已取消' },
  { value: 'expired', label: '已过期' },
]

const planLabels: Record<string, string> = {
  basic: '基础版',
  professional: '专业版',
  enterprise: '旗舰版',
}

const statusLabels: Record<string, string> = {
  pending: '待支付',
  paid: '已支付',
  failed: '支付失败',
  cancelled: '已取消',
  expired: '已过期',
}

function money(cents: number) {
  return `¥${(cents / 100).toFixed(2)}`
}

function formatDistribution(counts?: Record<string, number>) {
  if (!counts || Object.keys(counts).length === 0) return '-'
  return Object.entries(counts)
    .map(([key, count]) => `${planLabels[key] || statusLabels[key] || key} ${count}`)
    .join(' / ')
}

function statusType(value: string) {
  if (value === 'paid') return 'success'
  if (value === 'pending') return 'warning'
  if (value === 'failed') return 'danger'
  return 'info'
}

function formatTime(value: string | null) {
  return value ? value.replace('T', ' ').slice(0, 19) : '-'
}

async function loadSummary() {
  const { data } = await billingApi.getAdminPaymentSummary()
  summary.value = data
}

async function loadOrders() {
  loading.value = true
  try {
    const { data } = await billingApi.listAdminOrders({
      page: page.value,
      pageSize: pageSize.value,
      status: status.value || undefined,
    })
    orders.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

function handleStatusChange() {
  page.value = 1
  void loadOrders()
}

function handlePageChange(nextPage: number) {
  page.value = nextPage
  void loadOrders()
}

onMounted(() => {
  void loadSummary()
  void loadOrders()
})
</script>

<template>
  <div class="admin-payment-page">
    <div class="page-head">
      <div>
        <span class="hero-kicker">平台管理</span>
        <h1 class="page-title">支付订单</h1>
        <p class="page-subtitle">查看平台收入、订单状态和商家支付记录</p>
      </div>
      <el-button @click="loadOrders">刷新订单</el-button>
    </div>

    <section class="summary-grid">
      <div class="metric-card">
        <div class="metric-label">今日收入</div>
        <div class="metric-value">{{ money(summary?.todayRevenueCents || 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">本月收入</div>
        <div class="metric-value">{{ money(summary?.monthRevenueCents || 0) }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">已支付订单</div>
        <div class="metric-value">{{ summary?.paidOrders || 0 }}</div>
      </div>
      <div class="metric-card">
        <div class="metric-label">待支付订单</div>
        <div class="metric-value">{{ summary?.pendingOrders || 0 }}</div>
      </div>
      <div class="metric-card metric-card--wide">
        <div class="metric-label">套餐分布</div>
        <div class="metric-value metric-value--small">{{ formatDistribution(summary?.planCounts) }}</div>
      </div>
      <div class="metric-card metric-card--wide">
        <div class="metric-label">订阅状态</div>
        <div class="metric-value metric-value--small">{{ formatDistribution(summary?.statusCounts) }}</div>
      </div>
    </section>

    <section class="toolbar">
      <el-select v-model="status" style="width:180px" @change="handleStatusChange">
        <el-option
          v-for="item in statusOptions"
          :key="item.value"
          :label="item.label"
          :value="item.value"
        />
      </el-select>
      <div class="toolbar-meta">共 {{ total }} 条订单</div>
    </section>

    <div class="card table-card">
      <el-table :data="orders" v-loading="loading" stripe>
        <el-table-column prop="id" label="订单号" min-width="220" />
        <el-table-column label="店铺" min-width="160">
          <template #default="{ row }">{{ row.storeName || row.storeId }}</template>
        </el-table-column>
        <el-table-column label="套餐" width="110">
          <template #default="{ row }">{{ planLabels[row.planName] || row.planName }}</template>
        </el-table-column>
        <el-table-column label="金额" width="120">
          <template #default="{ row }">{{ money(row.amountCents) }}</template>
        </el-table-column>
        <el-table-column label="渠道" width="110">
          <template #default="{ row }">{{ row.provider === 'mock' ? '模拟支付' : row.provider }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="支付时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.paidAt) }}</template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-row">
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="handlePageChange"
      />
    </div>
  </div>
</template>

<style scoped>
.admin-payment-page {
  padding: 24px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.page-title {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.page-subtitle {
  margin-top: 8px;
  color: #6b7280;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.metric-card {
  background: #fff;
  border: 1px solid #e3e8ef;
  border-top: 3px solid #0072b2;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.metric-label {
  color: #6b7280;
  font-size: 0.85rem;
  margin-bottom: 8px;
}

.metric-value {
  color: #111827;
  font-size: 1.35rem;
  font-weight: 700;
}

.metric-card--wide {
  grid-column: span 2;
}

.metric-value--small {
  font-size: 0.98rem;
  line-height: 1.5;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  padding: 16px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
}

.toolbar-meta {
  color: #9ca3af;
  font-size: 0.9rem;
}

.table-card {
  padding: 0;
  overflow: hidden;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 900px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .page-head,
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }
}

@media (max-width: 640px) {
  .admin-payment-page {
    padding: 16px;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }

  .metric-card--wide {
    grid-column: span 1;
  }
}
</style>
