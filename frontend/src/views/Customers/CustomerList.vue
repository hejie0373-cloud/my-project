<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDebounceFn } from '@vueuse/core'
import { listCustomers as fetchCustomers, importCSV, getImportProgress, createCustomer } from '@/api/customers'
import http from '@/api/http'
import type { CustomerListItem, ImportProgress } from '@/types/customer'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

const router = useRouter()

function goDetail(id: string) {
  router.push(`/customers/${id}`)
}

// State
const items = ref<CustomerListItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const riskLevel = ref<string>('')
const loading = ref(false)
const riskFilters = [
  { label: '全部', value: '', tone: 'default' },
  { label: '高风险', value: 'high', tone: 'danger' },
  { label: '中风险', value: 'medium', tone: 'warning' },
  { label: '低风险', value: 'low', tone: 'success' },
]

// Create dialog
const createDialog = ref(false)
const createForm = ref({ name: '', phone: '', gender: 'unknown', address: '', preferredContact: 'sms' })
const createLoading = ref(false)
const batchScoring = ref(false)
const visibleHighRisk = computed(() => items.value.filter((item) => riskLabel(item.churnScore) === 'high').length)
const visibleUnscored = computed(() => items.value.filter((item) => item.churnScore === null).length)
const visibleVisits = computed(() => items.value.reduce((sum, item) => sum + item.visitCount, 0))
const activeRiskName = computed(() => riskFilters.find((item) => item.value === riskLevel.value)?.label || '全部')

async function handleBatchScore() {
  batchScoring.value = true
  try {
    await http.post('/metrics/churn/batch')
    ElMessage.success('批量评分任务已提交，请稍后刷新查看结果')
    setTimeout(() => load(), 5000)
  } catch {
    ElMessage.error('批量评分失败，请确认套餐权限')
  } finally { batchScoring.value = false }
}

async function handleCreate() {
  if (!createForm.value.name.trim()) { ElMessage.warning('请输入姓名'); return }
  if (!/^1[3-9]\d{9}$/.test(createForm.value.phone)) { ElMessage.warning('请输入正确的手机号'); return }
  createLoading.value = true
  try {
    await createCustomer({
      name: createForm.value.name,
      phone: createForm.value.phone,
      gender: createForm.value.gender,
      address: createForm.value.address,
      preferredContact: createForm.value.preferredContact,
    })
    ElMessage.success('客户已创建')
    createDialog.value = false
    createForm.value = { name: '', phone: '', gender: 'unknown', address: '', preferredContact: 'sms' }
    load()
  } catch { /* handled */ }
  finally { createLoading.value = false }
}

// Import dialog
const importDialog = ref(false)
const importTaskId = ref('')
const importProgress = ref<ImportProgress | null>(null)
let importTimer: number | null = null

// Load
async function load() {
  loading.value = true
  try {
    const { data } = await fetchCustomers({
      search: search.value || undefined,
      riskLevel: riskLevel.value || undefined,
      page: page.value,
      pageSize,
    })
    items.value = data.items
    total.value = data.total
  } catch { /* handled */ }
  finally { loading.value = false }
}

const debouncedSearch = useDebounceFn(() => { page.value = 1; load() }, 300)
watch(riskLevel, () => { page.value = 1; load() })
watch(page, () => load())
onMounted(() => load())

// Risk filter
function setRisk(level: string) {
  riskLevel.value = riskLevel.value === level ? '' : level
}

function riskLabel(score: number | null) {
  if (!score && score !== 0) return ''
  if (score > 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}

function riskText(level: string) {
  return { high: '高', medium: '中', low: '低' }[level] || ''
}

function maskPhone(phone: string) {
  if (phone.length >= 7) return phone.slice(0, 3) + '****' + phone.slice(-4)
  return phone
}

// Import
async function handleImport(file: File) {
  try {
    const { data } = await importCSV(file)
    importTaskId.value = data.taskId
    importProgress.value = { taskId: data.taskId, total: 0, success: 0, failed: 0, status: 'processing', errors: [] }

    importTimer = window.setInterval(async () => {
      const { data: prog } = await getImportProgress(importTaskId.value)
      importProgress.value = prog
      if (prog.status === 'done' || prog.status === 'error') {
        if (importTimer) clearInterval(importTimer)
        if (prog.status === 'done') {
          ElMessage.success(`导入完成: ${prog.success} 条成功, ${prog.failed} 条失败`)
          load()
        }
      }
    }, 2000)
  } catch { /* handled */ }
}

function closeImport() {
  importDialog.value = false
  importProgress.value = null
  if (importTimer) clearInterval(importTimer)
}
</script>

<template>
  <div class="customer-shell">
    <header class="customer-hero">
      <div>
        <span class="hero-kicker">客户运营</span>
        <h1>客户列表与流失风险处理。</h1>
        <p>集中查看客户档案、到店次数、AI 风险分和客户价值，优先跟进最需要处理的人。</p>
      </div>

      <div class="hero-actions">
        <el-button @click="importDialog = true">导入 CSV</el-button>
        <el-button type="warning" :loading="batchScoring" @click="handleBatchScore">一键分析</el-button>
        <el-button type="primary" @click="createDialog = true">新建客户</el-button>
      </div>
    </header>

    <section class="summary-grid">
      <article class="summary-card">
        <span>当前筛选</span>
        <strong>{{ activeRiskName }}</strong>
        <small>{{ total }} 位客户</small>
      </article>
      <article class="summary-card summary-card--danger">
        <span>本页高风险</span>
        <strong>{{ visibleHighRisk }}</strong>
        <small>建议优先跟进</small>
      </article>
      <article class="summary-card summary-card--success">
        <span>本页到店</span>
        <strong>{{ visibleVisits }}</strong>
        <small>累计到店次数</small>
      </article>
      <article class="summary-card summary-card--muted">
        <span>待评分</span>
        <strong>{{ visibleUnscored }}</strong>
        <small>可使用一键分析</small>
      </article>
    </section>

    <section class="customer-panel">
      <div class="toolbar">
        <el-input
          v-model="search"
          class="search-input"
          placeholder="搜索姓名或手机号"
          clearable
          @input="debouncedSearch"
        />

        <div class="risk-tabs">
          <button
            v-for="filter in riskFilters"
            :key="filter.value || 'all'"
            type="button"
            :class="['risk-tab', `risk-tab--${filter.tone}`, { active: riskLevel === filter.value }]"
            @click="filter.value ? setRisk(filter.value) : riskLevel = ''"
          >
            {{ filter.label }}
          </button>
        </div>
      </div>

      <el-table :data="items" v-loading="loading" class="customer-table">
        <el-table-column label="客户" min-width="180">
          <template #default="{ row }">
            <button class="customer-cell" type="button" @click="goDetail(row.id)">
              <span class="avatar">{{ row.name?.[0] || '客' }}</span>
              <span>
                <strong>{{ row.name }}</strong>
                <small>{{ maskPhone(row.phone) }}</small>
              </span>
            </button>
          </template>
        </el-table-column>
        <el-table-column label="到店次数" width="110">
          <template #default="{ row }">
            <span class="number-text">{{ row.visitCount }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近到店" min-width="130">
          <template #default="{ row }">
            <span class="muted-text">{{ row.lastVisitedAt ? dayjs(row.lastVisitedAt).format('MM-DD HH:mm') : '暂无记录' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="流失风险" width="150">
          <template #default="{ row }">
            <span v-if="row.churnScore !== null" :class="['risk-badge', `risk-${riskLabel(row.churnScore)}`]">
              {{ row.churnScore }} 分 · {{ riskText(riskLabel(row.churnScore)) }}风险
            </span>
            <span v-else class="unscored">未评分</span>
          </template>
        </el-table-column>
        <el-table-column label="CLV 价值" width="130">
          <template #default="{ row }">
            <span class="number-text">{{ row.clv ? '¥' + row.clv.toLocaleString() : '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="92" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="goDetail(row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row">
        <el-pagination
          v-model:current-page="page"
          :total="total"
          :page-size="pageSize"
          background
          layout="prev, pager, next"
        />
      </div>
    </section>

    <!-- Import Dialog -->
    <el-dialog v-model="importDialog" title="导入 CSV 客户数据" width="500px" @close="closeImport">
      <template v-if="!importProgress">
        <el-upload
          drag
          :auto-upload="false"
          accept=".csv"
          :on-change="(f: any) => handleImport(f.raw)"
        >
          <div style="padding:var(--space-xl)">
            <p style="font-size:2rem;margin-bottom:var(--space-sm)">📁</p>
            <p>拖拽 CSV 文件到此处或点击上传</p>
            <p style="font-size:0.8rem;color:var(--ink-muted)">必填：name, phone</p>
          </div>
        </el-upload>
      </template>
      <template v-else>
        <div style="padding:var(--space-md)">
          <el-progress
            :percentage="importProgress.total ? Math.round((importProgress.success + importProgress.failed) / importProgress.total * 100) : 0"
            :status="importProgress.status === 'done' ? 'success' : importProgress.status === 'error' ? 'exception' : undefined"
          />
          <p style="margin-top:var(--space-md);text-align:center">
            成功 {{ importProgress.success }} / 失败 {{ importProgress.failed }} / 总计 {{ importProgress.total }}
          </p>
          <div v-if="importProgress.errors.length" style="margin-top:var(--space-md);max-height:200px;overflow:auto">
            <div v-for="(err, i) in importProgress.errors" :key="i" style="font-size:0.8rem;color:var(--danger);padding:4px 0">
              行 {{ err.row }}: {{ err.field }} — {{ err.reason }}
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Create Dialog -->
    <el-dialog v-model="createDialog" title="新建客户" width="420px" @closed="createForm = { name: '', phone: '', gender: 'unknown', address: '', preferredContact: 'sms' }">
      <el-form label-position="top">
        <el-form-item label="姓名" required>
          <el-input v-model="createForm.name" placeholder="客户姓名" maxlength="100" />
        </el-form-item>
        <el-form-item label="手机号" required>
          <el-input v-model="createForm.phone" placeholder="11 位手机号" maxlength="11" />
        </el-form-item>
        <el-form-item label="性别">
          <el-radio-group v-model="createForm.gender">
            <el-radio value="male">男</el-radio>
            <el-radio value="female">女</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="createForm.address" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.customer-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.customer-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 24px 24px 0;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.customer-hero h1 {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.customer-hero p {
  max-width: 650px;
  margin: 10px 0 0;
  color: #6b7280;
}

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 0 24px;
}

.summary-card {
  min-height: 116px;
  padding: 18px;
  border: 1px solid #e3e8ef;
  border-top: 3px solid #0072b2;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.summary-card--danger { border-top-color: #d55e00; }
.summary-card--success { border-top-color: #009e73; }
.summary-card--muted { border-top-color: #6b7280; }

.summary-card span,
.summary-card small {
  display: block;
  color: #6b7280;
  font-size: 0.82rem;
  font-weight: 700;
}

.summary-card strong {
  display: block;
  margin: 8px 0 8px;
  color: #111827;
  font-size: 1.85rem;
  line-height: 1;
}

.summary-card small {
  color: #9ca3af;
  font-size: 0.78rem;
  font-weight: 500;
}

.customer-panel {
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
  justify-content: space-between;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid #eef2f7;
}

.search-input {
  width: min(320px, 100%);
}

.risk-tabs {
  display: inline-flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 4px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #f8fafc;
}

.risk-tab {
  min-height: 32px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 700;
}

.risk-tab.active {
  background: #fff;
  color: #111827;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.risk-tab--danger.active { color: #d55e00; }
.risk-tab--warning.active { color: #b7791f; }
.risk-tab--success.active { color: #009e73; }

.customer-table {
  width: 100%;
}

.customer-cell {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: 0;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.customer-cell:hover strong {
  color: #0072b2;
}

.avatar {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 50%;
  background: #e6f2f8;
  color: #0072b2;
  font-weight: 800;
}

.customer-cell strong,
.customer-cell small {
  display: block;
}

.customer-cell strong {
  color: #111827;
  font-size: 0.92rem;
}

.customer-cell small,
.muted-text {
  color: #9ca3af;
  font-size: 0.82rem;
}

.number-text {
  color: #111827;
  font-weight: 700;
}

.unscored {
  color: #9ca3af;
  font-size: 0.82rem;
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding: 16px;
  border-top: 1px solid #eef2f7;
}

@media (max-width: 980px) {
  .customer-hero,
  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }

  .customer-hero,
  .summary-grid {
    padding-left: 16px;
    padding-right: 16px;
  }

  .customer-panel {
    margin-left: 16px;
    margin-right: 16px;
  }
}
</style>
