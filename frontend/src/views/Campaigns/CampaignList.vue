<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { listCampaigns } from '@/api/campaigns'
import type { Campaign } from '@/types/campaign'
import dayjs from 'dayjs'

const router = useRouter()
const items = ref<Campaign[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const pageSize = 20

const sentCount = computed(() => items.value.filter((item) => item.status === 'sent').length)
const scheduledCount = computed(() => items.value.filter((item) => item.status === 'scheduled').length)
const totalDelivered = computed(() => items.value.reduce((sum, item) => sum + (item.logSummary?.sent || 0), 0))
const totalFailed = computed(() => items.value.reduce((sum, item) => sum + (item.logSummary?.failed || 0), 0))

async function load() {
  loading.value = true
  try {
    const { data } = await listCampaigns({ page: page.value, pageSize })
    items.value = data.items
    total.value = data.total
  } finally { loading.value = false }
}

onMounted(() => load())
watch(page, () => load())

function statusTag(status: string) {
  const map: Record<string, { type: string; label: string }> = {
    draft: { type: 'info', label: '草稿' },
    scheduled: { type: 'warning', label: '已排期' },
    sent: { type: 'success', label: '已发送' },
    failed: { type: 'danger', label: '失败' },
  }
  return map[status] || { type: 'info', label: status }
}

function channelLabel(channel: string) {
  return { sms: '短信', email: '邮件', wechat: '微信' }[channel] || channel
}
</script>

<template>
  <div class="campaign-shell">
    <header class="campaign-hero">
      <div>
        <span class="hero-kicker">营销活动</span>
        <h1>面向客户分层的触达任务。</h1>
        <p>查看召回、复购和通知类活动的发送状态，用活动结果反推下一轮客户运营动作。</p>
      </div>
      <el-button type="primary" @click="router.push('/campaigns/new')">新建活动</el-button>
    </header>

    <section class="metric-grid">
      <article class="metric-card">
        <span>活动总数</span>
        <strong>{{ total }}</strong>
        <small>当前店铺累计创建</small>
      </article>
      <article class="metric-card metric-card--success">
        <span>本页已发送</span>
        <strong>{{ sentCount }}</strong>
        <small>已完成触达任务</small>
      </article>
      <article class="metric-card metric-card--warning">
        <span>本页排期中</span>
        <strong>{{ scheduledCount }}</strong>
        <small>等待后续发送</small>
      </article>
      <article class="metric-card metric-card--danger">
        <span>发送结果</span>
        <strong>{{ totalDelivered }}/{{ totalFailed }}</strong>
        <small>成功 / 失败</small>
      </article>
    </section>

    <section class="campaign-panel">
      <div class="panel-head">
        <div>
          <h2>活动列表</h2>
          <p>共 {{ total }} 个活动，按创建时间排序。</p>
        </div>
        <el-button @click="load">刷新</el-button>
      </div>

      <el-table :data="items" v-loading="loading" class="campaign-table">
        <el-table-column label="活动" min-width="220">
          <template #default="{ row }">
            <div class="campaign-name">
              <strong>{{ row.name }}</strong>
              <small>{{ dayjs(row.createdAt).format('YYYY-MM-DD HH:mm') }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="渠道" width="180">
          <template #default="{ row }">
            <el-tag v-for="ch in row.channels" :key="ch" size="small" class="channel-tag">
              {{ channelLabel(ch as string) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status).type" size="small">{{ statusTag(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="发送统计" width="180">
          <template #default="{ row }">
            <span v-if="row.logSummary" class="send-summary">
              共 {{ row.logSummary.total }} · 成功 {{ row.logSummary.sent }} · 失败 {{ row.logSummary.failed }}
            </span>
            <span v-else class="muted-text">暂无统计</span>
          </template>
        </el-table-column>
        <el-table-column label="发送时间" min-width="150">
          <template #default="{ row }">
            <span class="muted-text">{{ row.scheduledAt ? dayjs(row.scheduledAt).format('MM-DD HH:mm') : '立即发送' }}</span>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row" v-if="total > pageSize">
        <el-pagination v-model:current-page="page" :total="total" :page-size="pageSize" background layout="prev, pager, next" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.campaign-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.campaign-hero {
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

.campaign-hero h1 {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.campaign-hero p {
  max-width: 660px;
  margin: 10px 0 0;
  color: #6b7280;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 0 24px;
}

.metric-card {
  min-height: 116px;
  padding: 18px;
  border: 1px solid #e3e8ef;
  border-top: 3px solid #0072b2;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.metric-card--success { border-top-color: #009e73; }
.metric-card--warning { border-top-color: #e69f00; }
.metric-card--danger { border-top-color: #d55e00; }

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

.campaign-panel {
  margin: 0 24px 24px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px;
  border-bottom: 1px solid #eef2f7;
}

.panel-head h2 {
  margin: 0;
  color: #111827;
  font-size: 0.98rem;
}

.panel-head p {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 0.8rem;
}

.campaign-name strong,
.campaign-name small {
  display: block;
}

.campaign-name strong {
  color: #111827;
}

.campaign-name small,
.muted-text,
.send-summary {
  color: #9ca3af;
  font-size: 0.82rem;
}

.channel-tag {
  margin-right: 4px;
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding: 16px;
  border-top: 1px solid #eef2f7;
}

@media (max-width: 980px) {
  .campaign-hero {
    flex-direction: column;
  }

  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .campaign-hero,
  .metric-grid {
    padding-left: 16px;
    padding-right: 16px;
  }

  .campaign-panel {
    margin-left: 16px;
    margin-right: 16px;
  }
}
</style>
