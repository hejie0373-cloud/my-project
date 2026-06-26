<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { qrConfirm, qrStatus } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const status = ref<'loading' | 'need_login' | 'ready' | 'confirming' | 'success' | 'failed'>('loading')
const qrId = route.params.qrId as string
const userName = ref('')

onMounted(async () => {
  if (!qrId) {
    ElMessage.error('无效的二维码')
    status.value = 'failed'
    return
  }

  try {
    const { data } = await qrStatus(qrId)
    if (data.status === 'expired') {
      status.value = 'failed'
      return
    }
  } catch {
    status.value = 'failed'
    return
  }

  if (auth.isLoggedIn) {
    if (!auth.user) await auth.fetchMe()
    userName.value = auth.user?.name || auth.user?.phone || '用户'
    status.value = 'ready'
  } else {
    status.value = 'need_login'
  }
})

async function handleConfirm() {
  status.value = 'confirming'
  try {
    await qrConfirm(qrId)
    status.value = 'success'
    ElMessage.success('已确认登录，请查看电脑屏幕')
  } catch (e: any) {
    status.value = 'failed'
    ElMessage.error(e?.response?.data?.detail || '确认失败，请重新扫码')
  }
}

function handleGoLogin() {
  router.push({ path: '/auth/signin', query: { redirect: `/auth/qr-confirm/${qrId}` } })
}
</script>

<template>
  <div class="confirm-page">
    <div class="confirm-header">
      <span class="header-logo">客留</span>
      <span class="header-desc">扫码登录确认</span>
    </div>

    <div class="confirm-card">
      <div v-if="status === 'loading'" class="confirm-state">
        <div class="spinner" />
        <p class="state-text">正在加载...</p>
      </div>

      <div v-else-if="status === 'need_login'" class="confirm-state">
        <div class="state-icon">登</div>
        <p class="state-title">需要先登录</p>
        <p class="state-desc">请先在手机上登录客留平台，再确认电脑端登录。</p>
        <button class="confirm-btn" @click="handleGoLogin">去登录</button>
      </div>

      <div v-else-if="status === 'ready'" class="confirm-state">
        <div class="state-icon success-icon">✓</div>
        <p class="state-title">确认登录</p>
        <p class="state-desc">检测到你正在电脑上尝试登录客留平台。</p>
        <div class="user-tag">
          <span class="user-avatar">{{ userName.charAt(0) }}</span>
          <span class="user-name">{{ userName }}</span>
        </div>
        <button class="confirm-btn" @click="handleConfirm">确认登录</button>
        <button class="cancel-btn" @click="status = 'failed'">取消</button>
      </div>

      <div v-else-if="status === 'confirming'" class="confirm-state">
        <div class="spinner" />
        <p class="state-text">正在确认...</p>
      </div>

      <div v-else-if="status === 'success'" class="confirm-state">
        <div class="state-icon success-icon">✓</div>
        <p class="state-title">确认成功</p>
        <p class="state-desc">电脑端正在自动登录。</p>
        <p class="state-hint">此页面可以关闭</p>
      </div>

      <div v-else class="confirm-state">
        <div class="state-icon">!</div>
        <p class="state-title">确认失败</p>
        <p class="state-desc">二维码已过期或网络异常。</p>
        <p class="state-hint">请在电脑上刷新二维码后重试</p>
      </div>
    </div>

    <p class="footer-text">客留 · 客户留得住，生意做得久</p>
  </div>
</template>

<style scoped>
.confirm-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: #f5f5f5;
  padding: 20px;
}

.confirm-header {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 24px;
}

.header-logo {
  font-size: 1.6rem;
  font-weight: 700;
  color: #2563eb;
}

.header-desc {
  font-size: 0.9rem;
  color: #999;
  margin-top: 4px;
}

.confirm-card {
  width: 100%;
  max-width: 340px;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
  padding: 32px 24px;
}

.confirm-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #eee;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-bottom: 16px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.state-icon {
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: #eef2ff;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.7rem;
  font-weight: 700;
  margin-bottom: 14px;
}

.success-icon {
  background: #ecfdf5;
  color: #059669;
}

.state-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 8px;
}

.state-desc {
  font-size: 0.9rem;
  color: #666;
  margin-bottom: 4px;
}

.state-hint {
  font-size: 0.82rem;
  color: #999;
  margin-top: 12px;
}

.user-tag {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #f3f4f6;
  padding: 10px 16px;
  border-radius: 8px;
  margin: 16px 0 24px;
}

.user-avatar {
  width: 36px;
  height: 36px;
  background: #2563eb;
  color: #fff;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1rem;
  font-weight: 600;
}

.user-name {
  font-size: 0.95rem;
  color: #333;
}

.state-text {
  font-size: 0.95rem;
  color: #666;
}

.confirm-btn,
.cancel-btn {
  width: 100%;
  height: 44px;
  border-radius: 8px;
  font-size: 1rem;
  cursor: pointer;
}

.confirm-btn {
  background: #2563eb;
  color: #fff;
  border: none;
  margin-top: 16px;
}

.cancel-btn {
  background: none;
  border: 1px solid #ddd;
  color: #777;
  margin-top: 10px;
}

.footer-text {
  margin-top: 24px;
  font-size: 0.78rem;
  color: #999;
}
</style>
