<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import http from '@/api/http'
import { ElMessage } from 'element-plus'
import { ElMessageBox } from 'element-plus'

const router = useRouter()
const stores = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const loading = ref(false)

const restrictVisible = ref(false)
const restrictStoreId = ref('')
const restrictStoreName = ref('')
const restrictStoreActive = ref(true)
const restrictionSaving = ref(false)
const restrictions = reactive({ ai: false, campaign: false, export: false })

async function loadStores() {
  loading.value = true
  try {
    const { data } = await http.get('/admin/stores', { params: { search: search.value || undefined, page: page.value, page_size: pageSize } })
    stores.value = (data as any).items || []
    total.value = (data as any).total || 0
  } finally { loading.value = false }
}

function openRestrict(row: any) {
  restrictStoreId.value = row.id
  restrictStoreName.value = row.name
  restrictStoreActive.value = row?.subscription?.isActive ?? true
  const restr = (row.subscription?.restrictions || '').split(',').filter(Boolean)
  restrictions.ai = restr.includes('ai')
  restrictions.campaign = restr.includes('campaign')
  restrictions.export = restr.includes('export')
  restrictVisible.value = true
}

async function saveRestrictions() {
  restrictionSaving.value = true
  try {
    const list = []
    if (restrictions.ai) list.push('ai')
    if (restrictions.campaign) list.push('campaign')
    if (restrictions.export) list.push('export')
    await http.put(`/admin/stores/${restrictStoreId.value}/restrictions`, null, { params: { restrictions: list.join(',') } })
    restrictVisible.value = false
    await loadStores()
    ElMessage.success('限制已保存')
  } finally { restrictionSaving.value = false }
}

async function toggleFullDisable() {
  const sid = restrictStoreId.value
  if (restrictStoreActive.value) {
    await ElMessageBox.confirm('将禁用该店铺所有人员登录并限制全部功能。确定？', '完全禁用', { type: 'warning', confirmButtonText: '确认禁用' })
    await http.put(`/admin/stores/${sid}/restrictions`, null, { params: { restrictions: 'ai,campaign,export' } })
    await http.put(`/admin/stores/${sid}/toggle`)
  } else {
    await http.put(`/admin/stores/${sid}/restrictions`, null, { params: { restrictions: '' } })
    await http.put(`/admin/stores/${sid}/toggle`)
  }
  restrictStoreActive.value = !restrictStoreActive.value
  restrictVisible.value = false
  await loadStores()
  ElMessage.success(restrictStoreActive.value ? '店铺已启用' : '店铺已完全禁用')
}

function restrictState(sub: any): 'none' | 'partial' | 'full' {
  if (!sub?.restrictions) return 'none'
  const list = sub.restrictions.split(',').filter(Boolean)
  if (list.length === 0) return 'none'
  if (list.length >= 3) return 'full'
  return 'partial'
}
function restrictLabel(s: string) {
  return { none: '无禁用', partial: '部分限制', full: '完全禁用' }[s] || s
}
function planLabel(sub: any) {
  if (!sub) return '免费版'
  return sub.planDisplayName || sub.plan || '免费版'
}

onMounted(() => loadStores())
watch([page, search], () => { page.value = search.value ? 1 : page.value; loadStores() })
</script>

<template>
  <div class="stores-shell">
    <header class="stores-hero">
      <div>
        <span class="hero-kicker">平台管理</span>
        <h1>店铺管理</h1>
        <p>检索商家店铺、查看套餐状态，并对功能权限进行平台侧管控。</p>
      </div>
    </header>

    <section class="stores-panel">
      <div class="toolbar">
        <el-input v-model="search" class="search-input" placeholder="搜索店铺名、店主或手机号" clearable @clear="loadStores" @keyup.enter="loadStores" />
        <el-button type="primary" @click="loadStores">搜索</el-button>
        <span class="toolbar-meta">共 {{ total }} 家店铺</span>
      </div>

      <el-table :data="stores" v-loading="loading" stripe>
        <el-table-column label="店铺" min-width="180">
          <template #default="{ row }">
            <div class="store-cell">
              <strong>{{ row.name }}</strong>
              <small>{{ row.ownerName || '未填店主' }} · {{ row.ownerPhone || '未填手机号' }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="套餐" width="100">
          <template #default="{ row }">
            <el-tag size="small">{{ planLabel(row.subscription) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="限制状态" width="100">
          <template #default="{ row }">
            <el-tag :type="restrictState(row.subscription) === 'full' ? 'danger' : restrictState(row.subscription) === 'partial' ? 'warning' : 'success'" size="small">
              {{ restrictLabel(restrictState(row.subscription)) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="router.push(`/admin/stores/${row.id}`)">详情</el-button>
            <el-button text size="small" @click="openRestrict(row)">管控</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" background layout="prev,pager,next" />
      </div>
    </section>

    <!-- 管控弹窗 -->
    <el-dialog v-model="restrictVisible" :title="`店铺管控 · ${restrictStoreName}`" width="460px" destroy-on-close>
      <!-- 功能限制 -->
      <p style="color:#6B7280;font-size:0.85rem;margin:0 0 14px">选择要限制的功能，勾选后商家端对应操作将被拦截。</p>
      <div style="display:flex;flex-direction:column;gap:8px;margin-bottom:20px">
        <label :class="['restrict-item', { on: restrictions.ai }]">
          <input type="checkbox" v-model="restrictions.ai" />
          <span class="check-box" />
          <div><strong>AI 评分/文案</strong><small>禁止流失分析和文案生成</small></div>
        </label>
        <label :class="['restrict-item', { on: restrictions.campaign }]">
          <input type="checkbox" v-model="restrictions.campaign" />
          <span class="check-box" />
          <div><strong>营销活动</strong><small>禁止创建和发送营销活动</small></div>
        </label>
        <label :class="['restrict-item', { on: restrictions.export }]">
          <input type="checkbox" v-model="restrictions.export" />
          <span class="check-box" />
          <div><strong>数据导出</strong><small>禁止导出 CSV 文件</small></div>
        </label>
      </div>
      <el-button type="primary" :loading="restrictionSaving" @click="saveRestrictions" style="width:100%">保存限制</el-button>

      <el-divider />

      <!-- 完全禁用 -->
      <div style="display:flex;justify-content:space-between;align-items:center">
        <div>
          <strong style="font-size:0.9rem">{{ restrictStoreActive ? '完全禁用店铺' : '重新启用店铺' }}</strong>
          <p style="color:#9CA3AF;font-size:0.8rem;margin:2px 0 0">{{ restrictStoreActive ? '禁用所有人员登录，限制全部功能' : '恢复登录权限，清除所有限制' }}</p>
        </div>
        <el-button :type="restrictStoreActive ? 'danger' : 'success'" size="small" @click="toggleFullDisable">
          {{ restrictStoreActive ? '完全禁用' : '启用' }}
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.stores-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.stores-hero {
  padding: 24px 24px 0;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.stores-hero h1 {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.stores-hero p {
  max-width: 660px;
  margin: 10px 0 0;
  color: #6b7280;
}

.stores-panel {
  margin: 0 24px 24px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 16px;
  border-bottom: 1px solid #eef2f7;
  flex-wrap: wrap;
}

.search-input {
  width: min(320px, 100%);
}

.toolbar-meta {
  margin-left: auto;
  color: #9ca3af;
  font-size: 0.86rem;
}

.store-cell strong,
.store-cell small {
  display: block;
}

.store-cell strong {
  color: #111827;
}

.store-cell small {
  color: #9ca3af;
  font-size: 0.8rem;
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding: 16px;
  border-top: 1px solid #eef2f7;
}

.restrict-item {
  display: flex; align-items: flex-start; gap: 12px; padding: 12px 14px;
  border: 1px solid #E8ECF1; border-radius: 10px; cursor: pointer;
  transition: all 0.2s;
}
.restrict-item:hover { border-color: #D1D5DB; background: #FAFBFC; }
.restrict-item.on { border-color: #DC2626; background: #FEF2F2; }
.restrict-item input { display: none; }
.check-box {
  width: 20px; height: 20px; border-radius: 6px; border: 2px solid #D1D5DB;
  flex-shrink: 0; margin-top: 1px; transition: all 0.2s;
  display: flex; align-items: center; justify-content: center;
}
.restrict-item.on .check-box { border-color: #DC2626; background: #DC2626; }
.restrict-item.on .check-box::after { content: '✕'; color: #fff; font-size: 11px; font-weight: 700; }
.restrict-item strong { display: block; font-size: 0.88rem; color: #1a1a2e; }
.restrict-item small { display: block; font-size: 0.76rem; color: #9CA3AF; margin-top: 2px; }
.restrict-item.on strong { color: #991B1B; }

@media (max-width: 640px) {
  .stores-hero {
    padding-left: 16px;
    padding-right: 16px;
  }

  .stores-panel {
    margin-left: 16px;
    margin-right: 16px;
  }

  .toolbar-meta {
    margin-left: 0;
    width: 100%;
  }
}
</style>
