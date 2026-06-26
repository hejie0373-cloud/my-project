<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/api/http'
import * as billingApi from '@/api/billing'
import type { PaymentOrder } from '@/api/billing'

const route = useRoute()
const storeId = route.params.id as string

const store = ref<any>(null)
const orders = ref<PaymentOrder[]>([])
const loading = ref(true)
const saving = ref(false)
const ordersLoading = ref(false)
const orderTotal = ref(0)
const restrictVisible = ref(false)
const restrictionSaving = ref(false)
const restrictions = reactive({
  ai: false,
  campaign: false,
  export: false,
})

const subForm = reactive({
  planName: 'free',
  status: 'active',
  customerLimit: 1000,
  nextBillingDate: null as string | null,
})

const planOpts = [
  { value: 'free', label: '免费版' },
  { value: 'basic', label: '基础版 ¥19.9' },
  { value: 'professional', label: '专业版 ¥49.9' },
]
const statusOpts = [
  { value: 'active', label: '已激活' },
  { value: 'overdue', label: '已过期' },
  { value: 'cancelled', label: '已取消' },
]
const statusLabels: Record<string, string> = {
  pending: '待支付', paid: '已支付', failed: '失败', cancelled: '取消', expired: '过期',
}
function money(c: number) { return `¥${(c / 100).toFixed(2)}` }
function statusType(v: string) {
  if (v === 'paid' || v === 'active') return 'success'
  if (v === 'pending' || v === 'trial') return 'warning'
  if (v === 'failed' || v === 'overdue') return 'danger'
  return 'info'
}

function fillSub(sub: any) {
  subForm.planName = sub?.planName || sub?.plan || 'free'
  subForm.status = sub?.status || 'active'
  subForm.customerLimit = sub?.customerLimit || 1000
  subForm.nextBillingDate = sub?.nextBillingDate || null
  // 解析限制
  const restr = (sub?.restrictions || '').split(',').filter(Boolean)
  restrictions.ai = restr.includes('ai')
  restrictions.campaign = restr.includes('campaign')
  restrictions.export = restr.includes('export')
}

async function saveRestrictions() {
  restrictionSaving.value = true
  try {
    const list = []
    if (restrictions.ai) list.push('ai')
    if (restrictions.campaign) list.push('campaign')
    if (restrictions.export) list.push('export')
    await http.put(`/admin/stores/${storeId}/restrictions`, null, { params: { restrictions: list.join(',') } })
    ElMessage.success('限制已更新')
    await loadStore()
  } finally { restrictionSaving.value = false }
}

async function loadStore() {
  const { data } = await http.get(`/admin/stores/${storeId}`)
  store.value = data
  fillSub(data.subscription)
}
async function loadOrders() {
  ordersLoading.value = true
  try {
    const { data } = await billingApi.listStoreOrders(storeId, { page: 1, pageSize: 10 })
    orders.value = data.items; orderTotal.value = data.total
  } finally { ordersLoading.value = false }
}
async function reload() {
  loading.value = true
  try { await Promise.all([loadStore(), loadOrders()]) } finally { loading.value = false }
}

// 用户管控
async function toggleUser(uid: string) {
  await http.put(`/admin/users/${uid}/toggle`)
  ElMessage.success('用户状态已切换')
  await loadStore()
}
async function deleteUser(uid: string, name: string) {
  await ElMessageBox.confirm(`确定删除用户「${name}」？此操作不可恢复`, '删除用户', { type: 'warning', confirmButtonText: '删除' })
  await http.delete(`/admin/users/${uid}`)
  ElMessage.success('已删除')
  await loadStore()
}

// 订阅保存
async function saveSub() {
  saving.value = true
  try {
    await billingApi.updateStoreSubscription(storeId, {
      planName: subForm.planName as 'free' | 'basic' | 'professional',
      status: subForm.status as 'active' | 'overdue' | 'cancelled',
      customerLimit: subForm.customerLimit,
      nextBillingDate: subForm.nextBillingDate,
    })
    ElMessage.success('已更新')
    await loadStore()
  } finally { saving.value = false }
}

// 店铺管控
async function handleRestrict() {
  if (!store.value) return
  const owner = store.value.owner
  const staff = store.value.staff || []
  const allUsers = owner ? [owner, ...staff] : staff

  const activeCount = allUsers.filter((u: any) => u.isActive).length
  const action = activeCount > 0
    ? '禁用后该店铺所有用户将无法登录和操作，确定继续？'
    : '启用后该店铺所有用户将恢复登录权限，确定继续？'

  await ElMessageBox.confirm(action, activeCount ? '禁用店铺' : '启用店铺', {
    type: 'warning',
    confirmButtonText: activeCount ? '确认禁用' : '确认启用',
    cancelButtonText: '取消',
  })
  await http.put(`/admin/stores/${storeId}/toggle`)
  ElMessage.success(activeCount ? '店铺已禁用' : '店铺已启用')
  await loadStore()
}

function activeCount(list: any[]) {
  return list?.filter((u: any) => u.isActive)?.length || 0
}

onMounted(reload)
</script>

<template>
  <div class="store-detail" v-loading="loading">
    <button class="back-btn" @click="$router.push('/admin/stores')">
      ← 返回店铺列表
    </button>

    <template v-if="store">
      <!-- 头部 -->
      <header class="detail-hero">
        <div class="hero-left">
          <div class="hero-icon">{{ store.name[0] }}</div>
          <div>
            <span class="hero-kicker">店铺详情</span>
            <h1 class="hero-name">{{ store.name }}</h1>
            <p class="hero-meta">{{ store.industryType || '未知行业' }} · {{ store.address || '未填地址' }} · {{ store.createdAt?.slice(0,10) }}</p>
          </div>
        </div>
        <div class="hero-right">
          <span class="status-dot" :class="store.subscription?.isActive ? 'on' : 'off'" />
          <span>{{ store.subscription?.isActive ? '正常运营' : '已停用' }}</span>
        </div>
      </header>

      <div class="detail-body">
        <!-- 左：订阅 + 管控 -->
        <div class="detail-left">
          <!-- 订阅 -->
          <section class="panel">
            <h3 class="panel-title">订阅管理</h3>
            <el-form label-position="top" size="large">
              <el-form-item label="套餐">
                <el-select v-model="subForm.planName" style="width:100%">
                  <el-option v-for="o in planOpts" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="状态">
                <el-select v-model="subForm.status" style="width:100%">
                  <el-option v-for="o in statusOpts" :key="o.value" :label="o.label" :value="o.value" />
                </el-select>
              </el-form-item>
              <el-form-item label="客户上限">
                <el-input-number v-model="subForm.customerLimit" :min="0" :max="99999" style="width:100%" />
              </el-form-item>
              <el-form-item label="到期日期">
                <el-date-picker v-model="subForm.nextBillingDate" type="date" value-format="YYYY-MM-DD" style="width:100%" />
              </el-form-item>
              <el-button type="primary" :loading="saving" @click="saveSub" style="width:100%">保存</el-button>
            </el-form>
          </section>

          <!-- 店铺管控 -->
          <section class="panel">
            <div class="panel-title-row">
              <h3 class="panel-title">店铺管控</h3>
              <el-button
                :type="activeCount(store.staff) > 0 || store.owner?.isActive ? 'danger' : 'success'"
                size="small"
                @click="handleRestrict"
              >
                {{ activeCount(store.staff) > 0 || store.owner?.isActive ? '禁用店铺' : '启用店铺' }}
              </el-button>
            </div>
            <p class="panel-desc">禁用后该店铺所有人员将无法登录，客户数据保留。</p>

            <!-- 人员列表 -->
            <div class="user-list">
              <!-- 店主 -->
              <div v-if="store.owner" class="user-row">
                <div class="user-info">
                  <div class="user-avatar">{{ store.owner.name[0] }}</div>
                  <div>
                    <strong>{{ store.owner.name }}</strong>
                    <span class="user-phone">{{ store.owner.phone }}</span>
                  </div>
                </div>
                <div class="user-actions">
                  <el-tag :type="store.owner.isActive ? 'success' : 'danger'" size="small" effect="dark">
                    {{ store.owner.isActive ? '正常' : '禁用' }}
                  </el-tag>
                  <span class="role-tag">店主</span>
                  <el-button text size="small" @click="toggleUser(store.owner.id)">
                    {{ store.owner.isActive ? '禁用' : '启用' }}
                  </el-button>
                </div>
              </div>
              <!-- 店员 -->
              <div v-for="s in store.staff" :key="s.id" class="user-row">
                <div class="user-info">
                  <div class="user-avatar staff-avatar">{{ s.name[0] }}</div>
                  <div>
                    <strong>{{ s.name }}</strong>
                    <span class="user-phone">{{ s.phone }}</span>
                  </div>
                </div>
                <div class="user-actions">
                  <el-tag :type="s.isActive ? 'success' : 'danger'" size="small" effect="dark">
                    {{ s.isActive ? '正常' : '禁用' }}
                  </el-tag>
                  <el-button text size="small" @click="toggleUser(s.id)">
                    {{ s.isActive ? '禁用' : '启用' }}
                  </el-button>
                  <el-button text size="small" type="danger" @click="deleteUser(s.id, s.name)">删除</el-button>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- 右：客户 + 支付 -->
        <div class="detail-right">
          <!-- 客户 -->
          <section class="panel">
            <h3 class="panel-title">客户列表 · {{ store.customerCount }} 人</h3>
            <div v-for="c in store.customers?.slice(0, 20)" :key="c.id" class="customer-row">
              <span class="cust-name">{{ c.name }}</span>
              <span class="cust-meta">{{ c.phone }} · {{ c.gender === 'male' ? '男' : '女' }}</span>
            </div>
            <p v-if="store.customerCount > 20" class="panel-more">... 还有 {{ store.customerCount - 20 }} 位客户</p>
          </section>

          <!-- 支付 -->
          <section class="panel">
            <div class="panel-title-row">
              <h3 class="panel-title">支付历史 · {{ orderTotal }} 条</h3>
              <el-button text size="small" @click="loadOrders">刷新</el-button>
            </div>
            <el-table :data="orders" v-loading="ordersLoading" size="small">
              <el-table-column label="套餐" width="100">
                <template #default="{ row }">{{ planOpts.find(p => p.value === row.planName)?.label || row.planName }}</template>
              </el-table-column>
              <el-table-column label="金额" width="90">
                <template #default="{ row }">{{ money(row.amountCents) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="80">
                <template #default="{ row }">
                  <el-tag :type="statusType(row.status)" size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="时间" min-width="150">
                <template #default="{ row }">{{ row.createdAt?.replace('T',' ').slice(0,19) || '-' }}</template>
              </el-table-column>
            </el-table>
          </section>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.store-detail {
  padding: 24px;
}

.back-btn {
  background: none;
  border: none;
  color: #6b7280;
  cursor: pointer;
  padding: 0;
  margin-bottom: 16px;
  font-size: 0.9rem;
}

.back-btn:hover { color: #0072b2; }

/* Hero */
.detail-hero {
  display: flex; align-items: center; justify-content: space-between;
  background: #fff; border: 1px solid #e3e8ef; border-radius: 8px;
  padding: 24px; margin-bottom: 18px; box-shadow: 0 1px 3px rgba(15,23,42,0.03);
}
.hero-left { display: flex; align-items: center; gap: 16px; }
.hero-icon {
  width: 52px; height: 52px; border-radius: 50%;
  background: #0072b2;
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 1.3rem; font-weight: 700;
}
.hero-kicker { color: #0072b2; font-size: 0.78rem; font-weight: 800; }
.hero-name { font-size: 1.25rem; font-weight: 700; color: #111827; margin: 5px 0 0; }
.hero-meta { font-size: 0.85rem; color: #9ca3af; margin: 4px 0 0; }
.hero-right { display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: #374151; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; }
.status-dot.on { background: #009e73; }
.status-dot.off { background: #d55e00; }

/* Body */
.detail-body { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }
@media (max-width: 860px) { .detail-body { grid-template-columns: 1fr; } }

/* Panel */
.panel { background: #fff; border: 1px solid #e3e8ef; border-radius: 8px; padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(15,23,42,0.03); }
.panel-title { font-size: 0.98rem; font-weight: 700; color: #111827; margin: 0; }
.panel-title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.panel-title-row .panel-title { margin-bottom: 0; }
.panel-desc { font-size: 0.82rem; color: #9CA3AF; margin: 8px 0 16px; line-height: 1.5; }
.panel-more { text-align: center; font-size: 0.82rem; color: #9CA3AF; padding-top: 8px; }

/* User list */
.user-list { border-top: 1px solid #F3F4F6; }
.user-row { display: flex; align-items: center; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid #F3F4F6; gap: 12px; }
.user-row:last-child { border-bottom: none; }
.user-info { display: flex; align-items: center; gap: 12px; min-width: 0; }
.user-avatar {
  width: 36px; height: 36px; border-radius: 50%; background: #e6f2f8; color: #0072b2;
  display: flex; align-items: center; justify-content: center; font-size: 0.85rem; font-weight: 700; flex-shrink: 0;
}
.staff-avatar { background: #F3F4F6; color: #6B7280; }
.user-info strong { font-size: 0.9rem; color: #1a1a2e; display: block; }
.user-phone { font-size: 0.78rem; color: #9CA3AF; }
.user-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.role-tag { font-size: 0.72rem; color: #0072b2; background: #e6f2f8; padding: 1px 8px; border-radius: 4px; font-weight: 600; }

/* Customer */
.customer-row { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #F9FAFB; }
.customer-row:last-child { border-bottom: none; }
.cust-name { font-weight: 600; font-size: 0.88rem; color: #111827; }
.cust-meta { font-size: 0.8rem; color: #9CA3AF; }

/* Restrict section */
.restrict-section { border-top: 1px solid #F3F4F6; padding-top: 16px; margin-top: 16px; }
.restrict-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.restrict-label { font-weight: 600; font-size: 0.9rem; color: #1a1a2e; }
.restrict-desc { font-size: 0.78rem; color: #9CA3AF; margin: 0 0 14px; line-height: 1.5; }
.restrict-checks { display: flex; flex-direction: column; gap: 8px; }
.restrict-item {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px;
  border: 1px solid #E8ECF1; border-radius: 10px; cursor: pointer;
  transition: all 0.2s;
}
.restrict-item:hover { border-color: #D1D5DB; background: #FAFBFC; }
.restrict-item.on { border-color: #DC2626; background: #FEF2F2; }
.restrict-item input[type="checkbox"] { display: none; }
.check-box {
  width: 20px; height: 20px; border-radius: 6px; border: 2px solid #D1D5DB;
  flex-shrink: 0; margin-top: 2px; transition: all 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.restrict-item.on .check-box { border-color: #DC2626; background: #DC2626; }
.restrict-item.on .check-box::after { content: '✕'; color: #fff; font-size: 11px; font-weight: 700; }
.check-text strong { display: block; font-size: 0.88rem; color: #1a1a2e; }
.check-text small { display: block; font-size: 0.76rem; color: #9CA3AF; margin-top: 2px; }
.restrict-item.on .check-text strong { color: #991B1B; }

@media (max-width: 640px) {
  .store-detail {
    padding: 16px;
  }

  .detail-hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .user-row,
  .customer-row {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
