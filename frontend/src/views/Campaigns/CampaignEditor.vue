<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createCampaign } from '@/api/campaigns'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()

const name = ref('')
const template = ref((route.query.copy as string) || '')
const channels = ref<string[]>(['sms'])
const sendMode = ref<'now' | 'scheduled'>('now')
const scheduledAt = ref('')
const targetRiskLevel = ref<'high' | 'all' | null>('high')
const targetCustomerIds = ref((route.query.customerId as string) || '')
const loading = ref(false)

const channelOptions = [
  { label: '短信', value: 'sms' },
  { label: '邮件', value: 'email' },
  { label: '微信', value: 'wechat' },
]

function insertTag(tag: string) {
  template.value += tag
}

async function handleSubmit() {
  if (!name.value.trim()) { ElMessage.warning('请输入活动名称'); return }
  if (!template.value.trim()) { ElMessage.warning('请输入消息模板'); return }
  if (!channels.value.length) { ElMessage.warning('请选择发送渠道'); return }
  if (sendMode.value === 'scheduled' && !scheduledAt.value) { ElMessage.warning('请选择预约发送时间'); return }

  loading.value = true
  try {
    await createCampaign({
      name: name.value.trim(),
      template: template.value.trim(),
      channels: channels.value as ('sms' | 'email' | 'wechat')[],
      scheduledAt: sendMode.value === 'scheduled' ? scheduledAt.value : null,
      targetCustomerIds: targetCustomerIds.value
        ? targetCustomerIds.value.split(',').map((s) => s.trim()).filter(Boolean)
        : null,
      targetRiskLevel: targetCustomerIds.value ? null : targetRiskLevel.value,
    })
    ElMessage.success('活动已创建并发送')
    router.push('/campaigns')
  } finally { loading.value = false }
}
</script>

<template>
  <div class="editor-shell">
    <header class="editor-hero">
      <button class="back-link" type="button" @click="router.push('/campaigns')">‹ 返回列表</button>
      <div>
        <span class="hero-kicker">新建活动</span>
        <h1>配置一次客户触达任务。</h1>
        <p>选择目标客户、发送渠道、消息内容和发送时间，创建后会沿用现有营销接口执行。</p>
      </div>
    </header>

    <div class="editor-grid">
      <section class="form-panel">
        <el-form label-position="top">
          <div class="form-block">
            <div class="block-head">
              <span>01</span>
              <div>
                <h2>活动基础信息</h2>
                <p>给这次触达一个便于复盘的名称。</p>
              </div>
            </div>
            <el-form-item label="活动名称" required>
              <el-input v-model="name" placeholder="如：流失客户召回活动" maxlength="200" size="large" />
            </el-form-item>
          </div>

          <div class="form-block">
            <div class="block-head">
              <span>02</span>
              <div>
                <h2>目标客户</h2>
                <p>指定客户 ID 会覆盖风险分层选择。</p>
              </div>
            </div>
            <el-radio-group v-model="targetRiskLevel" class="target-options">
              <el-radio-button value="high">高风险客户</el-radio-button>
              <el-radio-button value="all">所有客户</el-radio-button>
            </el-radio-group>
            <el-input v-model="targetCustomerIds" placeholder="可选，客户 ID 逗号分隔，如：abc123,def456" />
          </div>

          <div class="form-block">
            <div class="block-head">
              <span>03</span>
              <div>
                <h2>渠道与时间</h2>
                <p>选择一个或多个发送渠道。</p>
              </div>
            </div>
            <el-checkbox-group v-model="channels" class="channel-options">
              <el-checkbox v-for="ch in channelOptions" :key="ch.value" :value="ch.value" :label="ch.label" />
            </el-checkbox-group>

            <div class="send-row">
              <el-radio-group v-model="sendMode">
                <el-radio-button value="now">立即发送</el-radio-button>
                <el-radio-button value="scheduled">预约发送</el-radio-button>
              </el-radio-group>
              <el-input v-if="sendMode === 'scheduled'" v-model="scheduledAt" type="datetime-local" class="time-input" />
            </div>
          </div>

          <div class="form-block">
            <div class="block-head">
              <span>04</span>
              <div>
                <h2>消息模板</h2>
                <p>支持变量标签，发送时会替换为客户真实信息。</p>
              </div>
            </div>
            <div class="tag-row">
              <el-button size="small" @click="insertTag('{{客户姓名}}')">客户姓名</el-button>
              <el-button size="small" @click="insertTag('{{服务项目}}')">服务项目</el-button>
              <el-button size="small" @click="insertTag('{{推荐到店日期}}')">推荐日期</el-button>
              <el-button size="small" @click="insertTag('{{店铺名称}}')">店铺名称</el-button>
            </div>
            <el-input v-model="template" type="textarea" :rows="7" placeholder="输入消息内容，支持 {{变量}} 标签" />
          </div>
        </el-form>
      </section>

      <aside class="preview-panel">
        <div class="preview-card">
          <span class="preview-kicker">发送预览</span>
          <h3>{{ name || '未命名活动' }}</h3>
          <div class="preview-line">
            <span>目标</span>
            <strong>{{ targetCustomerIds ? '指定客户' : targetRiskLevel === 'all' ? '所有客户' : '高风险客户' }}</strong>
          </div>
          <div class="preview-line">
            <span>渠道</span>
            <strong>{{ channels.map((ch) => channelOptions.find((item) => item.value === ch)?.label || ch).join('、') || '未选择' }}</strong>
          </div>
          <div class="preview-line">
            <span>时间</span>
            <strong>{{ sendMode === 'scheduled' ? (scheduledAt || '待选择') : '立即发送' }}</strong>
          </div>
          <p class="preview-message">{{ template || '消息内容会显示在这里。' }}</p>
          <el-button type="primary" size="large" :loading="loading" class="submit-btn" @click="handleSubmit">
            创建并发送
          </el-button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.editor-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.editor-hero {
  padding: 24px 24px 0;
}

.back-link {
  margin-bottom: 14px;
  border: 0;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  font-size: 0.88rem;
}

.back-link:hover {
  color: #0072b2;
}

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.editor-hero h1 {
  margin: 8px 0 0;
  color: #111827;
  font-size: 1.5rem;
  line-height: 1.2;
}

.editor-hero p {
  max-width: 680px;
  margin: 10px 0 0;
  color: #6b7280;
}

.editor-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: 16px;
  padding: 0 24px 24px;
  align-items: start;
}

.form-panel,
.preview-card {
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.03);
}

.form-panel {
  padding: 20px;
}

.form-block {
  padding: 18px 0;
  border-top: 1px solid #eef2f7;
}

.form-block:first-child {
  padding-top: 0;
  border-top: 0;
}

.block-head {
  display: flex;
  gap: 12px;
  margin-bottom: 14px;
}

.block-head > span {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 8px;
  background: #e6f2f8;
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.block-head h2 {
  margin: 0;
  color: #111827;
  font-size: 0.98rem;
}

.block-head p {
  margin: 4px 0 0;
  color: #9ca3af;
  font-size: 0.8rem;
}

.target-options,
.channel-options,
.send-row,
.tag-row {
  margin-bottom: 12px;
}

.send-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.time-input {
  max-width: 240px;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preview-panel {
  position: sticky;
  top: 18px;
}

.preview-card {
  padding: 20px;
}

.preview-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.preview-card h3 {
  margin: 8px 0 16px;
  color: #111827;
  font-size: 1.1rem;
}

.preview-line {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid #eef2f7;
}

.preview-line span {
  color: #9ca3af;
}

.preview-line strong {
  color: #111827;
  text-align: right;
}

.preview-message {
  min-height: 120px;
  margin: 16px 0;
  padding: 14px;
  border-radius: 8px;
  background: #f8fafc;
  color: #374151;
  font-size: 0.86rem;
  line-height: 1.7;
  white-space: pre-wrap;
}

.submit-btn {
  width: 100%;
}

@media (max-width: 900px) {
  .editor-grid {
    grid-template-columns: 1fr;
  }

  .preview-panel {
    position: static;
  }
}

@media (max-width: 640px) {
  .editor-hero,
  .editor-grid {
    padding-left: 16px;
    padding-right: 16px;
  }
}
</style>
