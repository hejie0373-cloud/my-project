<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import { bindWechatByPassword, getWechatQrUrl, getWechatStatus } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const mode = ref<'code' | 'password'>('code')
const loading = ref(false)
const countdown = ref(0)
const phone = ref('')
const code = ref('')
const password = ref('')
const showPwd = ref(false)

const qrSrc = ref('')
const qrTip = ref('微信扫码登录')
const qrExpired = ref(false)
const wechatBinding = ref(false)
const bindLoading = ref(false)
let qrState = ''
let countdownTimer: number | null = null
let pollTimer: number | null = null
let expireTimer: number | null = null
let refreshTimer: number | null = null

function validPhone() {
  return /^1[3-9]\d{9}$/.test(phone.value)
}

async function genQR() {
  qrExpired.value = false
  qrTip.value = '加载中...'
  if (refreshTimer) clearInterval(refreshTimer)
  if (expireTimer) clearTimeout(expireTimer)

  try {
    const { data } = await getWechatQrUrl()
    qrState = data.state
    qrSrc.value = await QRCode.toDataURL(data.qrUrl, { width: 160, margin: 1 })
    qrTip.value = '微信扫码登录'
    startPolling()

    refreshTimer = window.setInterval(async () => {
      if (!qrExpired.value) await genQR()
    }, 120 * 1000)

    expireTimer = window.setTimeout(() => {
      qrExpired.value = true
      qrTip.value = '二维码已过期，点击刷新'
      stopPolling()
      if (refreshTimer) clearInterval(refreshTimer)
    }, Math.max(30, data.expiresIn - 5) * 1000)
  } catch {
    qrTip.value = '加载失败，点击刷新'
    qrExpired.value = true
  }
}

function startPolling() {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    if (!qrState || qrExpired.value) return
    try {
      const { data } = await getWechatStatus(qrState)
      if (data.status === 'confirmed' && data.tokens) {
        stopPolling()
        qrTip.value = '登录成功'
        auth.setTokens(data.tokens.accessToken, data.tokens.refreshToken)
        await auth.fetchMe()
        onLoginSuccess()
      } else if (data.status === 'expired') {
        qrExpired.value = true
        qrTip.value = '二维码已过期'
        stopPolling()
      } else if (data.status === 'unbound') {
        wechatBinding.value = true
        qrTip.value = '首次微信登录，请绑定已有手机号'
        stopPolling()
      } else {
        qrTip.value = '请使用微信扫码授权登录'
      }
    } catch {
      // 轮询失败时保持二维码可见，下一次继续尝试。
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function refreshQR() {
  wechatBinding.value = false
  void genQR()
}

async function handleWechatBind() {
  if (!qrState) return
  if (!validPhone()) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (!password.value) {
    ElMessage.warning('请输入该手机号的登录密码')
    return
  }
  bindLoading.value = true
  try {
    const { data } = await bindWechatByPassword(qrState, phone.value, password.value)
    if (data.status === 'confirmed' && data.tokens) {
      auth.setTokens(data.tokens.accessToken, data.tokens.refreshToken)
      await auth.fetchMe()
      ElMessage.success('微信已绑定，登录成功')
      onLoginSuccess()
    }
  } finally {
    bindLoading.value = false
  }
}

async function handleSendCode() {
  if (!validPhone()) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (countdown.value > 0) return
  loading.value = true
  try {
    await auth.sendCode(phone.value)
    ElMessage.success('验证码已发送')
    countdown.value = 60
    countdownTimer = window.setInterval(() => {
      countdown.value -= 1
      if (countdown.value <= 0 && countdownTimer) clearInterval(countdownTimer)
    }, 1000)
  } catch {
    ElMessage.error('验证码发送失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

async function handleSubmit() {
  if (!validPhone()) {
    ElMessage.warning('请输入正确的手机号')
    return
  }

  loading.value = true
  try {
    if (mode.value === 'code') {
      if (!/^\d{6}$/.test(code.value)) {
        ElMessage.warning('请输入 6 位验证码')
        return
      }
      const result = await auth.loginByPhone(phone.value, code.value)
      if (result.isNewUser) {
        router.push(`/auth/signup?phone=${result.phone}&code=${code.value}`)
      } else {
        onLoginSuccess()
      }
    } else {
      if (!password.value) {
        ElMessage.warning('请输入密码')
        return
      }
      await auth.loginByPassword(phone.value, password.value)
      onLoginSuccess()
    }
  } finally {
    loading.value = false
  }
}

function onLoginSuccess() {
  const redirect = router.currentRoute.value.query.redirect as string
  if (redirect) {
    router.push(redirect)
  } else if (auth.roles.includes('super_admin')) {
    router.push('/admin')
  } else if (auth.hasStore) {
    router.push('/dashboard')
  } else {
    router.push('/onboarding')
  }
}

onMounted(() => {
  void genQR()
})

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
  if (expireTimer) clearTimeout(expireTimer)
  if (refreshTimer) clearInterval(refreshTimer)
  stopPolling()
})
</script>

<template>
  <div class="auth-page">
    <section class="auth-visual">
      <div class="brand-row">
        <img src="@/assets/keliu.png" alt="客留" class="brand-logo" />
        <span class="brand-name">客留</span>
      </div>
      <div class="visual-copy">
        <span class="eyebrow">Customer retention workspace</span>
        <h1>把客户风险、营销动作和经营数据放在同一个工作台。</h1>
        <p>适合门店每天反复使用的客户运营系统，登录后即可继续处理客户跟进、AI 评分和营销活动。</p>
      </div>
      <div class="visual-metrics">
        <div>
          <strong>AI</strong>
          <span>流失预警</span>
        </div>
        <div>
          <strong>CRM</strong>
          <span>客户跟进</span>
        </div>
        <div>
          <strong>Pay</strong>
          <span>订阅管理</span>
        </div>
      </div>
    </section>

    <section class="auth-panel">
      <div class="panel-head">
        <span class="panel-kicker">欢迎回来</span>
        <h2>登录客留</h2>
        <p>使用手机号或微信扫码进入你的商家后台。</p>
      </div>

      <div class="mode-tabs">
        <button :class="{ active: mode === 'code' }" type="button" @click="mode = 'code'">验证码</button>
        <button :class="{ active: mode === 'password' }" type="button" @click="mode = 'password'">密码</button>
      </div>

      <div class="form-card">
        <label class="field-label">手机号</label>
        <div class="input-row">
          <span class="prefix">+86</span>
          <input v-model="phone" type="tel" maxlength="11" placeholder="请输入手机号" @keyup.enter="handleSubmit" />
        </div>

        <template v-if="mode === 'code'">
          <label class="field-label">验证码</label>
          <div class="input-row code-row">
            <input v-model="code" type="text" maxlength="6" placeholder="6 位验证码" @keyup.enter="handleSubmit" />
            <button type="button" :disabled="countdown > 0" @click="handleSendCode">
              {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
            </button>
          </div>
        </template>

        <template v-else>
          <label class="field-label">密码</label>
          <div class="input-row pwd-row">
            <input v-model="password" :type="showPwd ? 'text' : 'password'" placeholder="请输入密码" @keyup.enter="handleSubmit" />
            <button class="eye" type="button" @click="showPwd = !showPwd">{{ showPwd ? '隐藏' : '显示' }}</button>
          </div>
        </template>

        <button class="primary-btn" type="button" :disabled="loading" @click="handleSubmit">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </div>

      <div class="qr-card">
        <div class="qr-box" :class="{ expired: qrExpired }">
          <img v-if="qrSrc && !qrExpired && !wechatBinding" :src="qrSrc" alt="微信登录二维码" />
          <button v-if="qrExpired" class="qr-overlay" type="button" @click="refreshQR">刷新二维码</button>
          <div v-if="wechatBinding" class="qr-loading">待绑定</div>
          <div v-if="!qrSrc && !qrExpired && !wechatBinding" class="qr-loading">加载中...</div>
        </div>
        <div>
          <strong>微信扫码登录</strong>
          <span>{{ qrTip }}</span>
        </div>
      </div>

      <div v-if="wechatBinding" class="wechat-bind-card">
        <label class="field-label">绑定手机号</label>
        <div class="input-row">
          <span class="prefix">+86</span>
          <input v-model="phone" type="tel" maxlength="11" placeholder="请输入已注册手机号" />
        </div>
        <label class="field-label">登录密码</label>
        <div class="input-row pwd-row">
          <input v-model="password" :type="showPwd ? 'text' : 'password'" placeholder="输入该账号密码" @keyup.enter="handleWechatBind" />
          <button class="eye" type="button" @click="showPwd = !showPwd">{{ showPwd ? '隐藏' : '显示' }}</button>
        </div>
        <button class="primary-btn" type="button" :disabled="bindLoading" @click="handleWechatBind">
          {{ bindLoading ? '绑定中...' : '绑定并登录' }}
        </button>
      </div>

      <div class="panel-actions">
        <span>还没有账号？</span>
        <button type="button" @click="router.push('/auth/signup')">创建账号</button>
      </div>

      <p class="agree-text">
        登录即代表已阅读并同意 <a href="#">用户协议</a> 和 <a href="#">隐私政策</a>
      </p>
    </section>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(360px, 1.05fr) minmax(420px, 0.95fr);
  background: #f6f8fb;
  color: #111827;
}

.auth-visual {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 48px;
  background:
    linear-gradient(135deg, rgba(0, 114, 178, 0.12), transparent 42%),
    linear-gradient(160deg, #102033 0%, #182c3a 48%, #143529 100%);
  color: #fff;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-logo {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  object-fit: cover;
  background: #fff;
}

.brand-name {
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: 0;
}

.visual-copy {
  max-width: 620px;
}

.eyebrow,
.panel-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  color: #7dd3fc;
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0;
  text-transform: uppercase;
}

.visual-copy h1 {
  margin: 0;
  font-size: clamp(2rem, 4vw, 4.2rem);
  line-height: 1.05;
  letter-spacing: 0;
}

.visual-copy p {
  max-width: 540px;
  margin: 22px 0 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 1rem;
  line-height: 1.8;
}

.visual-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  max-width: 560px;
}

.visual-metrics div {
  min-height: 86px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.07);
}

.visual-metrics strong,
.visual-metrics span {
  display: block;
}

.visual-metrics strong {
  font-size: 1.15rem;
}

.visual-metrics span {
  margin-top: 6px;
  color: rgba(255, 255, 255, 0.62);
  font-size: 0.82rem;
}

.auth-panel {
  align-self: center;
  width: min(440px, calc(100% - 48px));
  margin: 0 auto;
  padding: 40px 0;
}

.panel-head {
  margin-bottom: 24px;
}

.panel-kicker {
  color: #0072b2;
}

.panel-head h2 {
  margin: 0;
  font-size: 1.8rem;
  line-height: 1.2;
}

.panel-head p {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 0.95rem;
}

.mode-tabs {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
  padding: 4px;
  margin-bottom: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #eef2f7;
}

.mode-tabs button {
  height: 38px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: #6b7280;
  font-weight: 600;
  cursor: pointer;
}

.mode-tabs button.active {
  background: #fff;
  color: #0072b2;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.form-card,
.qr-card,
.wechat-bind-card {
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
}

.form-card {
  padding: 22px;
}

.wechat-bind-card {
  padding: 18px;
  margin-top: 14px;
}

.field-label {
  display: block;
  margin-bottom: 8px;
  color: #374151;
  font-size: 0.82rem;
  font-weight: 700;
}

.input-row {
  display: flex;
  align-items: center;
  height: 46px;
  margin-bottom: 16px;
  border: 1px solid #dbe3ec;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.input-row:focus-within {
  border-color: #0072b2;
  box-shadow: 0 0 0 3px rgba(0, 114, 178, 0.12);
}

.prefix {
  display: flex;
  align-items: center;
  height: 100%;
  padding: 0 12px;
  border-right: 1px solid #e5e7eb;
  color: #6b7280;
  background: #f9fafb;
  font-size: 0.9rem;
}

.input-row input {
  flex: 1;
  min-width: 0;
  height: 100%;
  padding: 0 14px;
  border: 0;
  outline: none;
  background: transparent;
  color: #111827;
  font-size: 0.95rem;
}

.code-row button,
.pwd-row .eye {
  height: 100%;
  padding: 0 14px;
  border: 0;
  border-left: 1px solid #e5e7eb;
  background: #fff;
  color: #0072b2;
  font-size: 0.82rem;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
}

.code-row button:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}

.primary-btn {
  width: 100%;
  height: 46px;
  border: 0;
  border-radius: 8px;
  background: #0072b2;
  color: #fff;
  font-size: 0.95rem;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 10px 22px rgba(0, 114, 178, 0.22);
}

.primary-btn:hover {
  background: #005f95;
}

.primary-btn:disabled {
  opacity: 0.58;
  cursor: not-allowed;
}

.qr-card {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 16px;
  align-items: center;
  padding: 16px;
  margin-top: 14px;
}

.qr-card strong,
.qr-card span {
  display: block;
}

.qr-card strong {
  color: #1f2937;
  font-size: 0.92rem;
}

.qr-card span {
  margin-top: 4px;
  color: #6b7280;
  font-size: 0.82rem;
}

.qr-box {
  width: 96px;
  height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.qr-box img {
  width: 88px;
  height: 88px;
}

.qr-overlay {
  position: absolute;
  inset: 0;
  border: 0;
  background: rgba(255, 255, 255, 0.92);
  color: #0072b2;
  font-size: 0.82rem;
  font-weight: 700;
  cursor: pointer;
}

.qr-loading {
  color: #6b7280;
  font-size: 0.82rem;
}

.panel-actions {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
  color: #6b7280;
  font-size: 0.88rem;
}

.panel-actions button {
  padding: 0;
  border: 0;
  background: transparent;
  color: #0072b2;
  font-weight: 700;
  cursor: pointer;
}

.agree-text {
  margin: 16px 0 0;
  color: #8a94a3;
  font-size: 0.76rem;
  line-height: 1.7;
  text-align: center;
}

@media (max-width: 900px) {
  .auth-page {
    grid-template-columns: 1fr;
  }

  .auth-visual {
    min-height: 320px;
    padding: 32px;
  }

  .visual-metrics {
    display: none;
  }

  .auth-panel {
    width: min(460px, calc(100% - 32px));
    padding: 32px 0 48px;
  }
}

@media (max-width: 520px) {
  .auth-visual {
    min-height: 240px;
    padding: 24px;
  }

  .visual-copy h1 {
    font-size: 1.8rem;
  }

  .visual-copy p {
    font-size: 0.9rem;
  }

  .form-card {
    padding: 18px;
  }
}
</style>
