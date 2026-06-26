<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const phone = ref((route.query.phone as string) || '')
const code = ref((route.query.code as string) || '')
const password = ref('')
const confirmPassword = ref('')
const showPassword = ref(false)
const showConfirm = ref(false)
const loading = ref(false)
const countdown = ref(0)
let countdownTimer: number | null = null

function validPhone() {
  return /^1[3-9]\d{9}$/.test(phone.value)
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

async function handleRegister() {
  if (!validPhone()) {
    ElMessage.warning('请输入正确的手机号')
    return
  }
  if (!password.value || password.value.length < 8) {
    ElMessage.warning('密码至少 8 位')
    return
  }
  if (password.value !== confirmPassword.value) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }
  if (!/^\d{6}$/.test(code.value)) {
    ElMessage.warning('请输入 6 位验证码')
    return
  }

  loading.value = true
  try {
    await auth.registerByPhone(phone.value, code.value, password.value)
    ElMessage.success('注册成功')
    onSuccess()
  } finally {
    loading.value = false
  }
}

function onSuccess() {
  const redirect = router.currentRoute.value.query.from as string
  if (redirect) {
    router.push(redirect)
  } else if (auth.hasStore) {
    router.push('/dashboard')
  } else {
    router.push('/onboarding')
  }
}

onMounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})

onUnmounted(() => {
  if (countdownTimer) clearInterval(countdownTimer)
})
</script>

<template>
  <div class="signup-page">
    <section class="signup-copy">
      <div class="brand-row">
        <span class="brand-icon">客</span>
        <span class="brand-name">客留</span>
      </div>
      <div>
        <span class="eyebrow">Start your workspace</span>
        <h1>创建账号后，先完成店铺资料，再开始客户运营。</h1>
        <p>注册流程只保留必要信息。后续门店资料、套餐和权限仍沿用当前系统逻辑。</p>
      </div>
      <div class="step-list">
        <span>1. 验证手机号</span>
        <span>2. 设置登录密码</span>
        <span>3. 创建店铺工作台</span>
      </div>
    </section>

    <section class="signup-panel">
      <div class="signup-card">
        <div class="signup-header">
          <span class="panel-kicker">新账号</span>
          <h1>创建客留账号</h1>
          <p>已有账号可以直接返回登录。</p>
        </div>

        <div class="form-area">
          <label class="field-label">手机号</label>
          <div class="input-group">
            <span class="prefix">+86</span>
            <input v-model="phone" type="tel" maxlength="11" placeholder="请输入手机号" class="phone-input" />
          </div>

          <label class="field-label">登录密码</label>
          <div class="pwd-wrap">
            <input
              v-model="password"
              :type="showPassword ? 'text' : 'password'"
              placeholder="至少 8 位"
              class="full-input"
            />
            <button class="pwd-eye" type="button" @click="showPassword = !showPassword">
              {{ showPassword ? '隐藏' : '显示' }}
            </button>
          </div>

          <label class="field-label">确认密码</label>
          <div class="pwd-wrap">
            <input
              v-model="confirmPassword"
              :type="showConfirm ? 'text' : 'password'"
              placeholder="再次输入密码"
              class="full-input"
            />
            <button class="pwd-eye" type="button" @click="showConfirm = !showConfirm">
              {{ showConfirm ? '隐藏' : '显示' }}
            </button>
          </div>

          <label class="field-label">验证码</label>
          <div class="input-group">
            <input v-model="code" type="text" maxlength="6" placeholder="6 位验证码" class="code-input" />
            <button class="send-btn" type="button" :disabled="countdown > 0" @click="handleSendCode">
              {{ countdown > 0 ? `${countdown}s` : '发送验证码' }}
            </button>
          </div>

          <button class="submit-btn" type="button" :disabled="loading" @click="handleRegister">
            {{ loading ? '创建中...' : '创建账号' }}
          </button>

          <p class="agreement">
            注册即代表同意 <a href="#">用户协议</a> 和 <a href="#">隐私政策</a>
          </p>
          <button class="back-link" type="button" @click="router.push('/auth/signin')">返回登录</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.signup-page {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(340px, 0.9fr) minmax(420px, 1.1fr);
  background: #f6f8fb;
}

.signup-copy {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 48px;
  padding: 48px;
  background: #102033;
  color: #fff;
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.brand-icon {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: #0072b2;
  color: #fff;
  font-weight: 800;
}

.brand-name {
  font-size: 1.15rem;
  font-weight: 700;
}

.eyebrow,
.panel-kicker {
  display: inline-flex;
  margin-bottom: 14px;
  color: #7dd3fc;
  font-size: 0.78rem;
  font-weight: 700;
  text-transform: uppercase;
}

.signup-copy h1 {
  max-width: 620px;
  margin: 0;
  font-size: clamp(2rem, 3.6vw, 3.8rem);
  line-height: 1.08;
  letter-spacing: 0;
}

.signup-copy p {
  max-width: 500px;
  margin: 20px 0 0;
  color: rgba(255, 255, 255, 0.7);
  line-height: 1.8;
}

.step-list {
  display: grid;
  gap: 10px;
  max-width: 420px;
}

.step-list span {
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.78);
  font-size: 0.9rem;
}

.signup-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
}

.signup-card {
  width: min(430px, 100%);
  padding: 30px;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  background: #fff;
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
}

.signup-header {
  margin-bottom: 24px;
}

.panel-kicker {
  color: #0072b2;
}

.signup-header h1 {
  margin: 0;
  color: #111827;
  font-size: 1.65rem;
  line-height: 1.2;
}

.signup-header p {
  margin: 8px 0 0;
  color: #6b7280;
  font-size: 0.92rem;
}

.form-area {
  display: flex;
  flex-direction: column;
}

.field-label {
  margin-bottom: 8px;
  color: #374151;
  font-size: 0.82rem;
  font-weight: 700;
}

.input-group,
.full-input {
  height: 46px;
  border: 1px solid #dbe3ec;
  border-radius: 8px;
  background: #fff;
}

.input-group {
  display: flex;
  overflow: hidden;
  margin-bottom: 16px;
}

.input-group:focus-within,
.full-input:focus {
  border-color: #0072b2;
  box-shadow: 0 0 0 3px rgba(0, 114, 178, 0.12);
}

.prefix {
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-right: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #6b7280;
  font-size: 0.9rem;
}

.phone-input,
.code-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  padding: 0 14px;
  color: #111827;
  font-size: 0.95rem;
}

.send-btn {
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

.send-btn:disabled {
  color: #9ca3af;
  cursor: not-allowed;
}

.pwd-wrap {
  position: relative;
  margin-bottom: 16px;
}

.full-input {
  width: 100%;
  outline: none;
  padding: 0 62px 0 14px;
  font-size: 0.95rem;
  box-sizing: border-box;
}

.pwd-eye {
  position: absolute;
  right: 14px;
  top: 13px;
  border: 0;
  background: transparent;
  color: #0072b2;
  cursor: pointer;
  font-size: 0.82rem;
  font-weight: 700;
}

.submit-btn {
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

.submit-btn:hover {
  background: #005f95;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.agreement {
  margin: 16px 0 0;
  color: #8a94a3;
  font-size: 0.76rem;
  line-height: 1.7;
  text-align: center;
}

.back-link {
  display: block;
  margin: 18px auto 0;
  padding: 0;
  border: none;
  background: none;
  color: #0072b2;
  font-size: 0.88rem;
  font-weight: 700;
  cursor: pointer;
}

@media (max-width: 900px) {
  .signup-page {
    grid-template-columns: 1fr;
  }

  .signup-copy {
    min-height: 300px;
    padding: 32px;
  }

  .step-list {
    display: none;
  }
}

@media (max-width: 520px) {
  .signup-copy {
    min-height: 240px;
    padding: 24px;
  }

  .signup-card {
    padding: 22px;
  }
}
</style>
