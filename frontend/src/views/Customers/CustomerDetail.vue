<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCustomer, updateCustomer, deleteCustomer, createVisit } from '@/api/customers'
import http from '@/api/http'
import { triggerChurnScore, generateCopy } from '@/api/metrics'
import { ElMessage, ElMessageBox } from 'element-plus'
import dayjs from 'dayjs'

const route = useRoute()
const router = useRouter()
const customerId = route.params.id as string

const customer = ref<any>(null)
const loading = ref(true)
const editMode = ref(false)
const editForm = ref<Record<string, unknown>>({})

// Visit dialog
const visitDialog = ref(false)
const visitForm = ref({
  visitedAt: new Date().toISOString().slice(0, 16),
  serviceType: '', amount: 0, staffName: '', feedback: '',
})

// Copy dialog
const copyDialog = ref(false)
const copyChannel = ref('sms')
const copyText = ref('')
const copyLoading = ref(false)

// Scoring
const scoreLoading = ref(false)
const aiMetric = computed(() => customer.value?.aiMetric || null)
const latestVisit = computed(() => customer.value?.recentVisits?.[0] || null)
const totalSpend = computed(() =>
  (customer.value?.recentVisits || []).reduce((sum: number, visit: any) => sum + Number(visit.amount || 0), 0),
)

async function loadCustomer() {
  loading.value = true
  try {
    const { data } = await getCustomer(customerId)
    customer.value = data
  } catch {
    ElMessage.error('加载客户失败')
    router.push('/customers')
  } finally {
    loading.value = false
  }
}

onMounted(loadCustomer)

// Edit
function startEdit() {
  if (!customer.value) return
  editForm.value = {
    name: customer.value.name,
    phone: customer.value.phone,
    email: customer.value.email,
    address: customer.value.address,
  }
  editMode.value = true
}

async function saveEdit() {
  await updateCustomer(customerId, editForm.value)
  editMode.value = false
  ElMessage.success('已保存')
  await loadCustomer()
}

async function handleDelete() {
  await ElMessageBox.confirm('确定删除该客户？', '确认', { type: 'warning' })
  await deleteCustomer(customerId)
  ElMessage.success('已删除')
  router.push('/customers')
}

async function handleRevokeConsent() {
  await ElMessageBox.confirm('撤回后客户数据将被清理，确定？', '撤回授权', { type: 'warning' })
  await http.post(`/customers/${customerId}/revoke-consent`)
  ElMessage.success('已撤回')
  await loadCustomer()
}

// Visit
async function handleAddVisit() {
  if (!visitForm.value.serviceType) { ElMessage.warning('请输入服务类型'); return }
  await createVisit(customerId, {
    visitedAt: visitForm.value.visitedAt,
    serviceType: visitForm.value.serviceType,
    amount: visitForm.value.amount,
    staffName: visitForm.value.staffName || undefined,
    feedback: visitForm.value.feedback || undefined,
  })
  visitDialog.value = false
  ElMessage.success('已录入')
  await loadCustomer()
}

// AI
async function handleScore() {
  scoreLoading.value = true
  try {
    await triggerChurnScore(customerId)
    await loadCustomer()
    ElMessage.success('评分完成')
  } catch {
    ElMessage.error('评分失败，请确认套餐包含 AI 功能或体验次数未用完')
  } finally { scoreLoading.value = false }
}

async function handleGenerateCopy() {
  copyLoading.value = true
  try {
    const { data } = await generateCopy(customerId, copyChannel.value)
    copyText.value = data.content
    copyDialog.value = true
  } finally { copyLoading.value = false }
}

function goToCampaign() {
  router.push(`/campaigns/new?customerId=${customerId}&copy=${encodeURIComponent(copyText.value)}`)
}

// Risk helpers
function riskColor(score: number | null) {
  if (score == null) return 'var(--ink-muted)'
  if (score > 60) return 'var(--danger)'
  if (score >= 30) return 'var(--warning)'
  return 'var(--success)'
}

function riskLabel(score: number | null) {
  if (score == null) return '未评分'
  if (score > 60) return '高风险'
  if (score >= 30) return '中风险'
  return '低风险'
}

function riskTone(score: number | null) {
  if (score == null) return 'none'
  if (score > 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}

function gaugeColor(score: number) {
  if (score > 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}

const GENDER_MAP: Record<string, string> = { male: '男', female: '女' }
function genderLabel(g: string) {
  return GENDER_MAP[g] || '—'
}
</script>

<template>
  <div class="customer-detail" v-loading="loading">
    <template v-if="customer">
      <header class="detail-hero">
        <button class="back-link" type="button" @click="$router.push('/customers')">
          <span>‹</span>
          返回列表
        </button>

        <div class="hero-main">
          <div class="hero-avatar">{{ customer.name[0] }}</div>
          <div class="hero-copy">
            <span class="hero-kicker">客户档案</span>
            <h1>{{ customer.name }}</h1>
            <div class="hero-meta">
              <span>{{ customer.phone }}</span>
              <span>{{ genderLabel(customer.gender) }}</span>
              <span v-if="customer.address">{{ customer.address }}</span>
              <span>创建于 {{ dayjs(customer.createdAt).format('YYYY-MM-DD') }}</span>
            </div>
          </div>
          <div class="risk-card" :class="`risk-card--${riskTone(aiMetric?.churnScore ?? null)}`">
            <span>流失风险</span>
            <strong>{{ aiMetric?.churnScore ?? '—' }}</strong>
            <small>{{ riskLabel(aiMetric?.churnScore ?? null) }}</small>
          </div>
        </div>

        <div class="hero-actions">
          <el-button v-if="!editMode" @click="startEdit">编辑资料</el-button>
          <el-button @click="visitDialog = true">录入到店</el-button>
          <el-button type="warning" :loading="scoreLoading" @click="handleScore">
            {{ aiMetric?.churnScore != null ? '重新分析' : '开始分析' }}
          </el-button>
          <el-button type="danger" text @click="handleDelete">删除</el-button>
        </div>
      </header>

      <section class="metric-grid">
        <article class="metric-card">
          <span>累计到店</span>
          <strong>{{ customer.visitCount }}</strong>
          <small>最近记录 {{ latestVisit ? dayjs(latestVisit.visitedAt).format('MM-DD HH:mm') : '暂无' }}</small>
        </article>
        <article class="metric-card metric-card--success">
          <span>近期消费</span>
          <strong>¥{{ totalSpend.toLocaleString() }}</strong>
          <small>按最近记录累计</small>
        </article>
        <article class="metric-card metric-card--accent">
          <span>客户价值</span>
          <strong>{{ aiMetric?.clv ? '¥' + aiMetric.clv.toLocaleString() : '—' }}</strong>
          <small>AI 年预估价值</small>
        </article>
        <article class="metric-card metric-card--muted">
          <span>联系方式</span>
          <strong>{{ customer.preferredContact === 'wechat' ? '微信' : customer.preferredContact === 'email' ? '邮件' : '短信' }}</strong>
          <small>{{ customer.email || customer.phone }}</small>
        </article>
      </section>

      <section v-if="editMode" class="edit-section">
        <div class="section-head">
          <div>
            <h2>编辑客户资料</h2>
            <p>只修改当前客户的基础联系信息。</p>
          </div>
        </div>
        <el-form label-position="top">
          <div class="edit-grid">
            <el-form-item label="姓名"><el-input v-model="editForm.name" /></el-form-item>
            <el-form-item label="手机号"><el-input v-model="editForm.phone" /></el-form-item>
            <el-form-item label="邮箱"><el-input v-model="editForm.email" /></el-form-item>
            <el-form-item label="地址"><el-input v-model="editForm.address" /></el-form-item>
          </div>
          <div class="edit-actions">
            <el-button type="primary" @click="saveEdit">保存修改</el-button>
            <el-button @click="editMode = false">取消</el-button>
            <el-button type="danger" text @click="handleRevokeConsent">撤回授权</el-button>
          </div>
        </el-form>
      </section>

      <div class="detail-main">
        <section class="panel visit-panel">
          <div class="section-head">
            <div>
              <h2>到店记录</h2>
              <p>最近 {{ customer.recentVisits?.length || 0 }} 条服务与消费记录。</p>
            </div>
            <el-button size="small" @click="visitDialog = true">新增记录</el-button>
          </div>

          <div v-if="!customer.recentVisits?.length" class="empty-state">
            <p>暂无到店记录</p>
            <el-button size="small" @click="visitDialog = true">录入首条记录</el-button>
          </div>
          <div v-else class="visit-list">
            <article v-for="v in customer.recentVisits" :key="v.id" class="visit-item">
              <div class="visit-date">
                <strong>{{ dayjs(v.visitedAt).format('DD') }}</strong>
                <span>{{ dayjs(v.visitedAt).format('MM月') }}</span>
              </div>
              <div class="visit-body">
                <div class="visit-head">
                  <strong>{{ v.serviceType || '到店服务' }}</strong>
                  <span>¥{{ Number(v.amount || 0).toLocaleString() }}</span>
                </div>
                <div class="visit-sub">
                  {{ dayjs(v.visitedAt).format('YYYY-MM-DD HH:mm') }}
                  <template v-if="v.staffName"> · {{ v.staffName }}</template>
                  <template v-if="v.paymentMethod"> · {{ v.paymentMethod }}</template>
                </div>
                <p v-if="v.feedback" class="visit-feedback">{{ v.feedback }}</p>
              </div>
            </article>
          </div>
        </section>

        <aside class="side-stack">
          <section class="panel ai-panel">
            <div class="section-head">
              <div>
                <h2>AI 流失分析</h2>
                <p>{{ aiMetric?.computedAt ? `更新于 ${dayjs(aiMetric.computedAt).format('MM-DD HH:mm')}` : '尚未生成分析' }}</p>
              </div>
            </div>

            <div v-if="aiMetric?.churnScore == null" class="ai-empty">
              <p>点击顶部「开始分析」获取流失风险评分、客户价值和跟进建议。</p>
            </div>

            <div v-else class="ai-result">
              <div class="score-row">
                <div class="score-main" :style="{ color: riskColor(aiMetric.churnScore) }">
                  {{ aiMetric.churnScore }}<span>分</span>
                </div>
                <div>
                  <strong>{{ riskLabel(aiMetric.churnScore) }}</strong>
                  <p>年预估价值 ¥{{ (aiMetric.clv || 0).toLocaleString() }}</p>
                </div>
              </div>

              <div v-if="aiMetric.dimensions" class="score-gauges">
                <div class="gauge">
                  <div class="gauge-ring" :style="{ '--pct': (aiMetric.dimensions?.recencyScore || 0) / 100 }" :class="'gauge-' + gaugeColor(aiMetric.dimensions?.recencyScore || 0)">
                    <span>{{ aiMetric.dimensions?.recencyScore || 0 }}</span>
                  </div>
                  <label>到店间隔</label>
                </div>
                <div class="gauge">
                  <div class="gauge-ring" :style="{ '--pct': (aiMetric.dimensions?.frequencyScore || 0) / 100 }" :class="'gauge-' + gaugeColor(aiMetric.dimensions?.frequencyScore || 0)">
                    <span>{{ aiMetric.dimensions?.frequencyScore || 0 }}</span>
                  </div>
                  <label>到店频率</label>
                </div>
                <div class="gauge">
                  <div class="gauge-ring" :style="{ '--pct': (aiMetric.dimensions?.trendScore || 0) / 100 }" :class="'gauge-' + gaugeColor(aiMetric.dimensions?.trendScore || 0)">
                    <span>{{ aiMetric.dimensions?.trendScore || 0 }}</span>
                  </div>
                  <label>消费趋势</label>
                </div>
              </div>

              <div class="ai-advice">
                <span>建议</span>
                <p>{{ aiMetric.recommendation || '暂无建议' }}</p>
              </div>
            </div>
          </section>

          <section class="panel follow-panel">
            <div class="section-head">
              <div>
                <h2>跟进文案</h2>
                <p>生成后可直接带入营销活动。</p>
              </div>
            </div>

            <div class="copy-row">
              <el-select v-model="copyChannel" style="width:100px">
                <el-option label="短信" value="sms" />
                <el-option label="微信" value="wechat" />
              </el-select>
              <el-button :loading="copyLoading" @click="handleGenerateCopy">生成文案</el-button>
            </div>
            <div v-if="copyText" class="copy-result">
              <p>{{ copyText }}</p>
              <el-button type="primary" text @click="goToCampaign">发起活动</el-button>
            </div>
          </section>
        </aside>
      </div>
    </template>

    <el-dialog v-model="visitDialog" title="录入到店记录" width="420px">
      <el-form label-position="top">
        <el-form-item label="到店时间">
          <el-input v-model="visitForm.visitedAt" type="datetime-local" />
        </el-form-item>
        <el-form-item label="服务类型" required>
          <el-input v-model="visitForm.serviceType" placeholder="如：剪发、洗车" />
        </el-form-item>
        <el-form-item label="消费金额">
          <el-input-number v-model="visitForm.amount" :min="0" :precision="2" style="width:100%" />
        </el-form-item>
        <el-form-item label="服务员工">
          <el-input v-model="visitForm.staffName" />
        </el-form-item>
        <el-form-item label="客户反馈">
          <el-input v-model="visitForm.feedback" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="visitDialog = false">取消</el-button>
        <el-button type="primary" @click="handleAddVisit">确认录入</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="copyDialog" title="AI 生成跟进文案" width="500px">
      <div class="copy-dialog-body">
        <p>{{ copyText }}</p>
      </div>
      <template #footer>
        <el-button @click="copyDialog = false">关闭</el-button>
        <el-button type="primary" @click="goToCampaign">发起营销活动</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.customer-detail {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-hero {
  padding: 24px 24px 0;
}

.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 14px;
  border: 0;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.88rem;
}

.back-link span {
  font-size: 1.2rem;
  line-height: 1;
}

.back-link:hover {
  color: #0072b2;
}

.hero-main {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
}

.hero-avatar {
  width: 58px;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #e6f2f8;
  color: #0072b2;
  font-size: 1.4rem;
  font-weight: 800;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.hero-copy h1 {
  margin: 5px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.hero-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  margin-top: 9px;
  color: #6b7280;
  font-size: 0.86rem;
}

.risk-card {
  width: 108px;
  min-height: 92px;
  display: grid;
  place-items: center;
  padding: 10px;
  border: 1px solid #e3e8ef;
  border-top: 3px solid #6b7280;
  border-radius: 8px;
  background: #fff;
}

.risk-card span,
.risk-card small {
  color: #6b7280;
  font-size: 0.76rem;
  font-weight: 700;
}

.risk-card strong {
  color: #111827;
  font-size: 1.8rem;
  line-height: 1;
}

.risk-card--high { border-top-color: #d55e00; }
.risk-card--medium { border-top-color: #e69f00; }
.risk-card--low { border-top-color: #009e73; }

.hero-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 18px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 0 24px;
}

.metric-card,
.panel,
.edit-section {
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.metric-card {
  min-height: 116px;
  padding: 18px;
  border-top: 3px solid #0072b2;
}

.metric-card--success { border-top-color: #009e73; }
.metric-card--accent { border-top-color: #56b4e9; }
.metric-card--muted { border-top-color: #6b7280; }

.metric-card span,
.metric-card small {
  display: block;
  color: #6b7280;
  font-size: 0.82rem;
  font-weight: 700;
}

.metric-card strong {
  display: block;
  margin: 8px 0;
  color: #111827;
  font-size: 1.65rem;
  line-height: 1;
}

.metric-card small {
  color: #9ca3af;
  font-size: 0.78rem;
  font-weight: 500;
}

.edit-section {
  margin: 0 24px;
  padding: 20px;
}

.edit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 16px;
}

.edit-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-main {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) minmax(340px, 0.9fr);
  gap: 16px;
  padding: 0 24px 24px;
  align-items: start;
}

.panel {
  padding: 20px;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.section-head h2 {
  margin: 0;
  color: #111827;
  font-size: 0.98rem;
}

.section-head p {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 0.8rem;
}

.empty-state {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 220px;
  color: #9ca3af;
}

.visit-list {
  display: flex;
  flex-direction: column;
}

.visit-item {
  display: flex;
  gap: 14px;
  padding: 14px 0;
  border-top: 1px solid #f1f5f9;
}

.visit-item:first-child {
  border-top: 0;
}

.visit-date {
  width: 48px;
  height: 52px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  border-radius: 8px;
  background: #f8fafc;
}

.visit-date strong {
  color: #111827;
  font-size: 1.05rem;
  line-height: 1;
}

.visit-date span {
  color: #9ca3af;
  font-size: 0.72rem;
}

.visit-body {
  flex: 1;
  min-width: 0;
}

.visit-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.visit-head strong {
  color: #111827;
  font-size: 0.92rem;
}

.visit-head span {
  color: #0072b2;
  font-weight: 800;
}

.visit-sub,
.visit-feedback {
  margin-top: 4px;
  color: #9ca3af;
  font-size: 0.8rem;
}

.visit-feedback {
  color: #6b7280;
}

.side-stack {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.score-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f1f5f9;
}

.score-main {
  font-size: 2.5rem;
  font-weight: 800;
  line-height: 1;
}

.score-main span {
  margin-left: 2px;
  font-size: 1rem;
  font-weight: 600;
}

.score-row strong {
  color: #111827;
}

.score-row p {
  margin: 4px 0 0;
  color: #6b7280;
  font-size: 0.82rem;
}

.ai-empty {
  color: #9ca3af;
  font-size: 0.86rem;
  line-height: 1.7;
}

.score-gauges {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 16px 0;
}

.gauge {
  display: grid;
  place-items: center;
  gap: 6px;
}

.gauge-ring {
  width: 62px;
  height: 62px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: conic-gradient(var(--gc, #d1d5db) calc(var(--pct, 0) * 360deg), #eef2f7 0deg);
}

.gauge-ring span {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #fff;
  color: #111827;
  font-size: 0.82rem;
  font-weight: 800;
}

.gauge-low { --gc: #009e73; }
.gauge-medium { --gc: #e69f00; }
.gauge-high { --gc: #d55e00; }

.gauge label {
  color: #6b7280;
  font-size: 0.74rem;
}

.ai-advice {
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
}

.ai-advice span {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.ai-advice p,
.copy-result p,
.copy-dialog-body p {
  margin: 6px 0 0;
  color: #374151;
  font-size: 0.86rem;
  line-height: 1.65;
}

.copy-row {
  display: flex;
  gap: 8px;
}

.copy-result,
.copy-dialog-body {
  margin-top: 12px;
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
}

@media (max-width: 1060px) {
  .metric-grid,
  .detail-main {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .visit-panel {
    grid-column: span 2;
  }
}

@media (max-width: 720px) {
  .hero-main,
  .metric-grid,
  .detail-main,
  .edit-grid {
    grid-template-columns: 1fr;
  }

  .visit-panel {
    grid-column: span 1;
  }

  .risk-card {
    width: 100%;
  }
}
</style>
