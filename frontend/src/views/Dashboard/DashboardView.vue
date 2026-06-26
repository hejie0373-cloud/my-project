<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useNotificationStore } from '@/stores/notification'
import { getDashboard } from '@/api/analytics'
import type { DashboardData } from '@/types/analytics'
import VChart from 'vue-echarts'
import * as echarts from 'echarts'
echarts.use([])

const router = useRouter()
const notif = useNotificationStore()
const data = ref<DashboardData | null>(null)
const loading = ref(true)

// Okabe-Ito 色盲安全调色板
const C = {
  orange:  '#E69F00',
  sky:     '#56B4E9',
  green:   '#009E73',
  yellow:  '#F0E442',
  blue:    '#0072B2',
  red:     '#D55E00',
  pink:    '#CC79A7',
  ink:     '#374151',
  muted:   '#9CA3AF',
  light:   '#F3F4F6',
}

onMounted(async () => {
  try {
    const { data: res } = await getDashboard()
    data.value = res
  } catch { /* */ }
  finally { loading.value = false }
})

// 趋势图
const trendOption = computed(() => ({
  tooltip: {
    trigger: 'axis' as const,
    backgroundColor: '#fff',
    borderColor: '#E5E7EB',
    textStyle: { color: C.ink, fontSize: 13 },
    formatter: (params: any) => {
      const p = params[0]
      return `<b>${p.axisValue}</b><br/>到店 <b style="color:${C.blue}">${p.value}</b> 人次`
    },
  },
  grid: { left: 16, right: 16, top: 12, bottom: 8 },
  xAxis: {
    type: 'category' as const,
    data: data.value?.visitTrend?.map((p) => p.date.slice(5)) || [],
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: C.muted, fontSize: 12 },
  },
  yAxis: {
    type: 'value' as const,
    minInterval: 1,
    splitLine: { lineStyle: { color: '#F3F4F6', type: 'dashed' } },
    axisLabel: { color: C.muted, fontSize: 12 },
  },
  series: [{
    data: data.value?.visitTrend?.map((p) => p.count) || [],
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { color: C.blue, width: 2.5 },
    itemStyle: { color: C.blue },
    areaStyle: {
      color: {
        type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0,114,178,0.12)' },
          { offset: 1, color: 'rgba(0,114,178,0.01)' },
        ],
      },
    },
  }],
}))

// 风险分布环形图
const churnPieOption = computed(() => {
  const d = data.value?.churnDistribution
  if (!d) return {}
  return {
    tooltip: { trigger: 'item' as const, backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: C.ink } },
    legend: { show: false },
    series: [{
      type: 'pie',
      radius: ['55%', '80%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 2, borderColor: '#fff', borderWidth: 3 },
      label: { show: false },
      emphasis: { scale: false, label: { show: true, fontSize: 16, fontWeight: 'bold' } },
      data: [
        { value: d.high, name: '高风险', itemStyle: { color: C.red } },
        { value: d.medium, name: '中风险', itemStyle: { color: C.orange } },
        { value: d.low, name: '低风险', itemStyle: { color: C.green } },
      ],
    }],
  }
})

function riskLevel(score: number) {
  if (score > 60) return 'high'
  if (score >= 30) return 'medium'
  return 'low'
}
</script>

<template>
  <div class="dashboard-shell">
    <header class="dashboard-hero">
      <div>
        <span class="hero-kicker">经营总览</span>
        <h1>快速看见今天的客户状态。</h1>
        <p>把客户数量、流失风险、到店趋势和高价值客户放在同一个视图里，减少切换成本。</p>
      </div>

      <el-popover placement="bottom-end" :width="320" trigger="click">
        <template #reference>
          <el-badge :value="notif.unreadCount" :hidden="notif.unreadCount === 0">
            <el-button class="notice-btn" circle>🔔</el-button>
          </el-badge>
        </template>
        <p v-if="!notif.messages.length" class="notice-empty">暂无通知</p>
        <div v-else class="notice-list">
          <div v-for="(msg, i) in notif.messages.slice(0, 10)" :key="i" class="notice-item">
            <span v-if="msg.type === 'high_risk_alert'" class="notice-tag notice-tag--danger">高风险预警</span>
            <span v-else class="notice-tag">系统通知</span>
          </div>
          <el-button text size="small" class="notice-read" @click="notif.markAllRead()">全部已读</el-button>
        </div>
      </el-popover>
    </header>

    <el-skeleton :loading="loading" animated :count="4">
      <template v-if="data">
        <section class="metric-grid">
          <article class="metric-card">
            <span class="metric-label">总客户</span>
            <strong class="metric-value">{{ data.totalCustomers }}</strong>
            <span class="metric-note">当前在库客户总量</span>
          </article>
          <article class="metric-card metric-card--danger">
            <span class="metric-label">高风险</span>
            <strong class="metric-value">{{ data.highRiskCount }}</strong>
            <span class="metric-note">需要优先跟进</span>
          </article>
          <article class="metric-card metric-card--success">
            <span class="metric-label">高价值</span>
            <strong class="metric-value">{{ data.highValueCount }}</strong>
            <span class="metric-note">值得做复购与转介绍</span>
          </article>
          <article class="metric-card metric-card--accent">
            <span class="metric-label">今日到店</span>
            <strong class="metric-value">{{ data.todayVisits }}</strong>
            <span class="metric-note">今天新增到店次数</span>
          </article>
        </section>

        <section class="content-grid">
          <article class="panel panel--wide">
            <div class="panel-head">
              <div>
                <h3>到店趋势</h3>
                <p>近 7 天到店人次</p>
              </div>
              <span class="panel-chip">{{ (data.visitTrend || []).reduce((s: number, p: any) => s + p.count, 0) }} 人次</span>
            </div>
            <v-chart v-if="data.visitTrend?.length" :option="trendOption" class="chart chart--line" autoresize />
            <div v-else class="panel-empty">暂无到店数据</div>
          </article>

          <article class="panel">
            <div class="panel-head">
              <div>
                <h3>流失风险</h3>
                <p>最近一次评分分布</p>
              </div>
            </div>
            <v-chart v-if="data.churnDistribution" :option="churnPieOption" class="chart chart--pie" autoresize />
          </article>

          <article class="panel panel--list">
            <div class="panel-head">
              <div>
                <h3>高风险客户</h3>
                <p>优先处理的前 5 位</p>
              </div>
              <router-link to="/customers" class="panel-link">全部查看 →</router-link>
            </div>
            <div v-if="!data.topRiskCustomers?.length" class="panel-empty">暂无高风险客户</div>
            <button
              v-for="c in data.topRiskCustomers"
              :key="c.id"
              class="risk-row"
              type="button"
              @click="router.push(`/customers/${c.id}`)"
            >
              <div class="risk-avatar" :class="`risk-${riskLevel(c.churnScore)}`">{{ c.name[0] }}</div>
              <div class="risk-body">
                <div class="risk-name">{{ c.name }}</div>
                <div class="risk-phone">{{ c.phone }}</div>
              </div>
              <div class="risk-score-wrap">
                <div class="risk-bar-bg">
                  <div class="risk-bar-fill" :class="`risk-${riskLevel(c.churnScore)}`" :style="{ width: `${c.churnScore}%` }" />
                </div>
                <span class="risk-val" :class="`text-${riskLevel(c.churnScore)}`">{{ c.churnScore }}</span>
              </div>
            </button>
          </article>
        </section>
      </template>
    </el-skeleton>
  </div>
</template>

<style scoped>
.dashboard-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.dashboard-hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 24px 24px 0;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.dashboard-hero h1 {
  margin: 8px 0 0;
  font-size: 1.5rem;
  line-height: 1.2;
}

.dashboard-hero p {
  max-width: 620px;
  margin: 10px 0 0;
  color: #6b7280;
}

.notice-btn {
  width: 40px;
  height: 40px;
  border: 1px solid #dbe3ec;
  background: #fff;
}

.notice-empty {
  padding: 12px;
  color: #9ca3af;
}

.notice-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.notice-item {
  padding: 8px 0;
  border-bottom: 1px solid #f1f5f9;
}

.notice-tag {
  display: inline-flex;
  padding: 3px 8px;
  border-radius: 999px;
  background: #eef2f7;
  color: #334155;
  font-size: 0.78rem;
}

.notice-tag--danger {
  background: #fef2f2;
  color: #b42318;
}

.notice-read {
  width: 100%;
  margin-top: 8px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 0 24px;
}

.metric-card {
  min-height: 132px;
  padding: 20px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.metric-card--danger { border-top: 3px solid #d55e00; }
.metric-card--success { border-top: 3px solid #009e73; }
.metric-card--accent { border-top: 3px solid #0072b2; }

.metric-label {
  color: #6b7280;
  font-size: 0.82rem;
  font-weight: 700;
}

.metric-value {
  display: block;
  margin-top: 8px;
  color: #111827;
  font-size: 2rem;
  line-height: 1;
}

.metric-note {
  display: block;
  margin-top: 10px;
  color: #9ca3af;
  font-size: 0.8rem;
}

.content-grid {
  display: grid;
  grid-template-columns: 1.8fr 1fr 1.1fr;
  gap: 16px;
  padding: 0 24px 24px;
}

@media (max-width: 1180px) {
  .metric-grid,
  .content-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .panel--wide,
  .panel--list {
    grid-column: span 2;
  }
}

@media (max-width: 720px) {
  .metric-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .panel--wide,
  .panel--list {
    grid-column: span 1;
  }
}

.panel {
  min-height: 320px;
  padding: 20px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.panel-head h3 {
  margin: 0;
  color: #111827;
  font-size: 0.98rem;
}

.panel-head p {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 0.8rem;
}

.panel-chip {
  flex-shrink: 0;
  padding: 4px 10px;
  border-radius: 999px;
  background: #eef2f7;
  color: #334155;
  font-size: 0.78rem;
  font-weight: 700;
}

.panel-link {
  color: #0072b2;
  font-size: 0.82rem;
  text-decoration: none;
}

.panel-link:hover {
  text-decoration: underline;
}

.panel-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  color: #9ca3af;
  font-size: 0.9rem;
}

.chart {
  width: 100%;
}

.chart--line {
  height: 280px;
}

.chart--pie {
  height: 280px;
}

.risk-row {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 0;
  border: 0;
  border-top: 1px solid #f1f5f9;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.risk-row:first-of-type {
  border-top: 0;
}

.risk-row:hover {
  background: #f8fafc;
}

.risk-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 0.85rem;
  font-weight: 700;
  flex-shrink: 0;
}

.risk-avatar.risk-high { background: #d55e00; }
.risk-avatar.risk-medium { background: #e69f00; }
.risk-avatar.risk-low { background: #009e73; }

.risk-body {
  flex: 1;
  min-width: 0;
}

.risk-name {
  color: #111827;
  font-size: 0.9rem;
  font-weight: 700;
}

.risk-phone {
  color: #9ca3af;
  font-size: 0.78rem;
}

.risk-score-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.risk-bar-bg {
  width: 62px;
  height: 6px;
  border-radius: 999px;
  background: #eef2f7;
  overflow: hidden;
}

.risk-bar-fill {
  height: 100%;
  border-radius: 999px;
}

.risk-bar-fill.risk-high { background: #d55e00; }
.risk-bar-fill.risk-medium { background: #e69f00; }
.risk-bar-fill.risk-low { background: #009e73; }

.risk-val {
  width: 28px;
  color: #111827;
  font-size: 0.85rem;
  font-weight: 700;
  text-align: right;
}

.text-high { color: #d55e00; }
.text-medium { color: #e69f00; }
.text-low { color: #009e73; }
</style>
