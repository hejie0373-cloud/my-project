<script setup lang="ts">
import { ref, onMounted } from 'vue'
import http from '@/api/http'

const overview = ref({ totalStores: 0, totalUsers: 0, totalCustomers: 0, highRiskCustomers: 0 })

onMounted(async () => {
  const { data } = await http.get('/admin/overview')
  overview.value = data as any
})
</script>

<template>
  <div class="admin-shell">
    <header class="admin-hero">
      <div>
        <span class="hero-kicker">平台管理</span>
        <h1>平台总览</h1>
        <p>查看商家、用户、客户和风险客户的核心规模指标。</p>
      </div>
    </header>

    <section class="metric-grid">
      <article class="metric-card">
        <span>总店铺数</span>
        <strong>{{ overview.totalStores }}</strong>
        <small>已入驻商家</small>
      </article>
      <article class="metric-card metric-card--accent">
        <span>总用户数</span>
        <strong>{{ overview.totalUsers }}</strong>
        <small>平台账号规模</small>
      </article>
      <article class="metric-card metric-card--success">
        <span>总客户数</span>
        <strong>{{ overview.totalCustomers }}</strong>
        <small>商家客户资产</small>
      </article>
      <article class="metric-card metric-card--danger">
        <span>高风险客户</span>
        <strong>{{ overview.highRiskCustomers }}</strong>
        <small>需商家优先跟进</small>
      </article>
    </section>
  </div>
</template>

<style scoped>
.admin-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.admin-hero {
  padding: 24px 24px 0;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.admin-hero h1 {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.admin-hero p {
  max-width: 660px;
  margin: 10px 0 0;
  color: #6b7280;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
  padding: 0 24px 24px;
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

.metric-card--accent { border-top-color: #56b4e9; }
.metric-card--success { border-top-color: #009e73; }
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
  font-size: 1.85rem;
  line-height: 1;
}

.metric-card small {
  color: #9ca3af;
  font-size: 0.78rem;
  font-weight: 500;
}

@media (max-width: 900px) {
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }

  .admin-hero,
  .metric-grid {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
