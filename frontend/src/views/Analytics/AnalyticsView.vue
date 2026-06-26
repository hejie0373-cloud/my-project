<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { getReport, exportCSV } from '@/api/analytics'
import type { VisitReportItem, RevenueReportItem, AiReportData } from '@/types/analytics'
import VChart from 'vue-echarts'
import * as echarts from 'echarts'
echarts.use([])
import dayjs from 'dayjs'

const COLORS = {
  blue: '#0072B2',
  orange: '#E69F00',
  green: '#009E73',
  red: '#D55E00',
  ink: '#374151',
  muted: '#9CA3AF',
  light: '#F3F4F6',
}

const reportType = ref<'visits' | 'revenue' | 'ai'>('visits')
const granularity = ref<'day' | 'week' | 'month'>('day')
const startDate = ref(dayjs().subtract(30, 'day').format('YYYY-MM-DD'))
const endDate = ref(dayjs().format('YYYY-MM-DD'))

const visitData = ref<VisitReportItem[]>([])
const revenueData = ref<RevenueReportItem[]>([])
const aiData = ref<AiReportData | null>(null)
const loading = ref(false)

const visitTotal = computed(() => visitData.value.reduce((sum, item) => sum + item.visitCount, 0))
const uniqueTotal = computed(() => visitData.value.reduce((sum, item) => sum + item.uniqueCustomers, 0))
const revenueTotal = computed(() => revenueData.value.reduce((sum, item) => sum + item.totalAmount, 0))
const avgRevenue = computed(() => {
  if (!revenueData.value.length) return 0
  const total = revenueData.value.reduce((sum, item) => sum + item.avgAmount, 0)
  return total / revenueData.value.length
})

async function load() {
  loading.value = true
  try {
    const params: any = { type: reportType.value, startDate: startDate.value, endDate: endDate.value }
    if (reportType.value !== 'ai') params.granularity = granularity.value
    const { data } = await getReport(params)
    if (reportType.value === 'visits') visitData.value = data as VisitReportItem[]
    if (reportType.value === 'revenue') revenueData.value = data as RevenueReportItem[]
    if (reportType.value === 'ai') aiData.value = data as AiReportData
  } finally { loading.value = false }
}

onMounted(() => load())

const visitOption = computed(() => ({
  tooltip: { trigger: 'axis' as const, backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: COLORS.ink, fontSize: 13 } },
  legend: { data: ['到店量', '客户数'], bottom: 0, textStyle: { color: COLORS.muted, fontSize: 12 }, icon: 'roundRect' },
  grid: { left: 16, right: 16, top: 16, bottom: 36 },
  xAxis: {
    type: 'category',
    data: visitData.value.map((d) => d.period),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: COLORS.muted, fontSize: 11 },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    splitLine: { lineStyle: { color: COLORS.light, type: 'dashed' } },
    axisLabel: { color: COLORS.muted, fontSize: 11 },
  },
  series: [
    { name: '到店量', type: 'bar', data: visitData.value.map((d) => d.visitCount), barWidth: 14, itemStyle: { color: COLORS.blue, borderRadius: [4, 4, 0, 0] }, barGap: '30%' },
    { name: '客户数', type: 'line', data: visitData.value.map((d) => d.uniqueCustomers), smooth: true, symbol: 'circle', symbolSize: 5, lineStyle: { color: COLORS.orange, width: 2 }, itemStyle: { color: COLORS.orange } },
  ],
}))

const revenueOption = computed(() => ({
  tooltip: { trigger: 'axis' as const, backgroundColor: '#fff', borderColor: '#E5E7EB', textStyle: { color: COLORS.ink, fontSize: 13 } },
  grid: { left: 16, right: 16, top: 16, bottom: 8 },
  xAxis: {
    type: 'category',
    data: revenueData.value.map((d) => d.period),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: { color: COLORS.muted, fontSize: 11 },
  },
  yAxis: { type: 'value', splitLine: { lineStyle: { color: COLORS.light, type: 'dashed' } }, axisLabel: { color: COLORS.muted, fontSize: 11 } },
  series: [{
    name: '营收',
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 4,
    data: revenueData.value.map((d) => d.totalAmount),
    lineStyle: { color: COLORS.green, width: 2.5 },
    itemStyle: { color: COLORS.green },
    areaStyle: {
      color: {
        type: 'linear',
        x: 0,
        y: 0,
        x2: 0,
        y2: 1,
        colorStops: [
          { offset: 0, color: 'rgba(0,158,115,0.12)' },
          { offset: 1, color: 'rgba(0,158,115,0.0)' },
        ],
      },
    },
  }],
}))

async function handleExport() {
  const { data } = await exportCSV({ type: reportType.value === 'ai' ? 'customers' : 'visits', startDate: startDate.value, endDate: endDate.value })
  const url = URL.createObjectURL(data as Blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `export_${reportType.value}_${dayjs().format('YYYYMMDD')}.csv`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="analytics-shell">
    <header class="analytics-hero">
      <div>
        <span class="hero-kicker">数据分析</span>
        <h1>从到店、营收和 AI 指标看经营变化。</h1>
        <p>按时间范围查看客户行为和经营结果，必要时导出 CSV 做进一步分析。</p>
      </div>
      <el-button @click="handleExport">导出 CSV</el-button>
    </header>

    <section class="controls-panel">
      <el-radio-group v-model="reportType" @change="load">
        <el-radio-button value="visits">到店分析</el-radio-button>
        <el-radio-button value="revenue">营收分析</el-radio-button>
        <el-radio-button value="ai">AI 指标</el-radio-button>
      </el-radio-group>

      <div class="controls-right">
        <el-radio-group v-if="reportType !== 'ai'" v-model="granularity" @change="load">
          <el-radio-button value="day">按日</el-radio-button>
          <el-radio-button value="week">按周</el-radio-button>
          <el-radio-button value="month">按月</el-radio-button>
        </el-radio-group>
        <el-date-picker v-model="startDate" type="date" value-format="YYYY-MM-DD" class="date-input" @change="load" />
        <span class="ctrl-sep">—</span>
        <el-date-picker v-model="endDate" type="date" value-format="YYYY-MM-DD" class="date-input" @change="load" />
      </div>
    </section>

    <section v-if="reportType === 'visits'" class="report-section" v-loading="loading">
      <div class="metric-grid metric-grid--compact">
        <article class="metric-card">
          <span>到店量</span>
          <strong>{{ visitTotal }}</strong>
          <small>当前时间范围累计</small>
        </article>
        <article class="metric-card metric-card--success">
          <span>客户数</span>
          <strong>{{ uniqueTotal }}</strong>
          <small>去重客户累计</small>
        </article>
      </div>
      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>到店趋势</h3>
            <p>{{ startDate }} 至 {{ endDate }}</p>
          </div>
        </div>
        <v-chart :option="visitOption" class="chart" autoresize />
      </div>
    </section>

    <section v-if="reportType === 'revenue'" class="report-section" v-loading="loading">
      <div class="metric-grid metric-grid--compact">
        <article class="metric-card metric-card--success">
          <span>营收合计</span>
          <strong>¥{{ revenueTotal.toLocaleString() }}</strong>
          <small>当前时间范围累计</small>
        </article>
        <article class="metric-card metric-card--accent">
          <span>平均消费</span>
          <strong>¥{{ avgRevenue.toFixed(0) }}</strong>
          <small>按报表周期均值</small>
        </article>
      </div>
      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>营收趋势</h3>
            <p>{{ startDate }} 至 {{ endDate }}</p>
          </div>
        </div>
        <v-chart :option="revenueOption" class="chart" autoresize />
      </div>
    </section>

    <section v-if="reportType === 'ai' && aiData" class="report-section" v-loading="loading">
      <div class="metric-grid">
        <article class="metric-card metric-card--danger"><span>高风险客户</span><strong>{{ aiData.highRiskCount }}</strong><small>需要优先跟进</small></article>
        <article class="metric-card metric-card--success"><span>平均 CLV</span><strong>¥{{ (aiData.clvAvg || 0).toLocaleString() }}</strong><small>客户终身价值</small></article>
        <article class="metric-card metric-card--accent"><span>文案采纳率</span><strong>{{ aiData.copyAdoptionRate }}%</strong><small>AI 文案使用情况</small></article>
        <article class="metric-card"><span>已评分客户</span><strong>{{ aiData.totalCustomersScored }}</strong><small>完成 AI 评分</small></article>
      </div>

      <div class="panel">
        <div class="panel-head">
          <div>
            <h3>流失风险分布</h3>
            <p>按最近一次 AI 评分归档。</p>
          </div>
        </div>
        <div class="churn-bars">
          <div v-for="(count, bucket) in aiData.churnScoreDistribution" :key="bucket" class="churn-bar-item">
            <div class="churn-bar-label">{{ bucket }}</div>
            <div class="churn-bar-track">
              <div class="churn-bar-fill" :style="{ width: Math.max(count / (aiData.totalCustomersScored || 1) * 100, 2) + '%' }" :class="'churn-' + bucket">
                <span v-if="count > 0">{{ count }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.analytics-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.analytics-hero {
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

.analytics-hero h1 {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.analytics-hero p {
  max-width: 660px;
  margin: 10px 0 0;
  color: #6b7280;
}

.controls-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin: 0 24px;
  padding: 16px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  flex-wrap: wrap;
}

.controls-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.ctrl-sep {
  color: #d1d5db;
  font-size: 0.85rem;
}

.date-input {
  width: 140px;
}

.report-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 0 24px 24px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.metric-grid--compact {
  grid-template-columns: repeat(2, minmax(0, 1fr));
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
.metric-card--accent { border-top-color: #56b4e9; }
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

.panel {
  padding: 20px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.panel-head {
  margin-bottom: 12px;
}

.panel-head h3 {
  margin: 0;
  color: #111827;
  font-size: 0.98rem;
  font-weight: 700;
}

.panel-head p {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 0.8rem;
}

.chart {
  height: 380px;
}

.churn-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 8px 0;
}

.churn-bar-item {
  display: flex;
  align-items: center;
  gap: 12px;
}

.churn-bar-label {
  width: 80px;
  text-align: right;
  color: #374151;
  font-size: 0.85rem;
  font-weight: 500;
}

.churn-bar-track {
  flex: 1;
  height: 28px;
  border-radius: 6px;
  background: #f3f4f6;
  overflow: hidden;
}

.churn-bar-fill {
  height: 100%;
  min-width: 40px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 8px;
  border-radius: 6px;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
  transition: width 0.5s ease;
}

.churn-高风险 { background: #d55e00; }
.churn-中风险 { background: #e69f00; }
.churn-低风险 { background: #009e73; }

@media (max-width: 900px) {
  .analytics-hero,
  .controls-panel {
    flex-direction: column;
    align-items: stretch;
  }

  .metric-grid,
  .metric-grid--compact {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .metric-grid,
  .metric-grid--compact {
    grid-template-columns: 1fr;
  }

  .analytics-hero,
  .report-section {
    padding-left: 16px;
    padding-right: 16px;
  }

  .controls-panel {
    margin-left: 16px;
    margin-right: 16px;
  }
}
</style>
