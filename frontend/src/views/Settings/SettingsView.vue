<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import http from '@/api/http'
import * as authApi from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const auth = useAuthStore()
const activeTab = ref('profile')
const profileLoading = ref(false)

// ---- 个人信息 ----
const profile = ref({ name: '', phone: '' })
onMounted(() => {
  if (auth.user) {
    profile.value = {
      name: auth.user.name || '',
      phone: auth.user.phone || '',
    }
  }
})
async function saveProfile() {
  profileLoading.value = true
  try {
    await authApi.updateProfile({ name: profile.value.name })
    await auth.fetchMe()
    ElMessage.success('个人信息已更新')
  } finally { profileLoading.value = false }
}

// ---- 修改密码 ----
const pwdForm = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const pwdLoading = ref(false)
async function changePassword() {
  if (!pwdForm.value.oldPassword) { ElMessage.warning('请输入旧密码'); return }
  if (pwdForm.value.newPassword.length < 8) { ElMessage.warning('新密码至少8位'); return }
  if (pwdForm.value.newPassword !== pwdForm.value.confirmPassword) { ElMessage.warning('两次密码不一致'); return }
  pwdLoading.value = true
  try {
    await authApi.changePassword(pwdForm.value.oldPassword, pwdForm.value.newPassword)
    ElMessage.success('密码已修改，即将跳转登录')
    pwdForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
    setTimeout(() => {
      auth.logout()
      router.push('/auth/signin')
    }, 800)
  } finally { pwdLoading.value = false }
}

// ---- 更换手机号 ----
const phoneForm = ref({ phone: '', code: '' })
const phoneLoading = ref(false)
const phoneCountdown = ref(0)
let phoneTimer: number | null = null
async function sendPhoneCode() {
  if (!/^1[3-9]\d{9}$/.test(phoneForm.value.phone)) { ElMessage.warning('请输入正确手机号'); return }
  if (phoneCountdown.value > 0) return
  try { await auth.sendCode(phoneForm.value.phone); phoneCountdown.value = 60
    phoneTimer = window.setInterval(() => { phoneCountdown.value--; if (phoneCountdown.value <= 0 && phoneTimer) clearInterval(phoneTimer) }, 1000)
  } catch { /* */ }
}
async function changePhone() {
  if (!/^\d{6}$/.test(phoneForm.value.code)) { ElMessage.warning('请输入6位验证码'); return }
  phoneLoading.value = true
  try {
    await authApi.changePhone(phoneForm.value.phone, phoneForm.value.code)
    await auth.fetchMe()
    profile.value.phone = auth.user?.phone || ''
    phoneForm.value = { phone: '', code: '' }
    ElMessage.success('手机号已更换')
  } finally { phoneLoading.value = false }
}

// ---- 店铺信息 ----
const store = ref({ name: '', industryType: '', address: '' })
const storeLoading = ref(false)
onMounted(async () => {
  if (!auth.user?.storeId) return
  try {
    const { data } = await http.get(`/stores/${auth.user.storeId}`)
    store.value = {
      name: (data as any).name || '',
      industryType: (data as any).industryType || '',
      address: (data as any).address || '',
    }
  } catch { /* */ }
})
async function saveStore() {
  if (!store.value.name.trim()) { ElMessage.warning('请输入店铺名称'); return }
  storeLoading.value = true
  try {
    await http.put(`/stores/${auth.user!.storeId}`, store.value)
    ElMessage.success('店铺信息已更新')
  } finally { storeLoading.value = false }
}
</script>

<template>
  <div class="settings">
    <!-- 顶部标题栏 -->
    <header class="settings-hero">
      <div class="hero-avatar">
        <span class="avatar-text">{{ (auth.user?.name || '用')[0] }}</span>
      </div>
      <div class="hero-meta">
        <span class="hero-kicker">账号设置</span>
        <h1 class="hero-name">{{ auth.user?.name || auth.user?.phone }}</h1>
        <p class="hero-role">{{ auth.roles.join('、') || '未分配' }}</p>
      </div>
    </header>

    <!-- Tab 导航 -->
    <nav class="settings-tabs">
      <button
        :class="['tab-item', { active: activeTab === 'profile' }]"
        @click="activeTab = 'profile'"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
        </svg>
        个人信息
      </button>
      <button
        :class="['tab-item', { active: activeTab === 'store' }]"
        @click="activeTab = 'store'"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/>
        </svg>
        店铺信息
      </button>
    </nav>

    <!-- 内容区 -->
    <div class="settings-body">
      <!-- ========== 个人信息 ========== -->
      <section v-if="activeTab === 'profile'" class="section">
        <div class="card">
          <div class="card-head">
            <span class="card-badge">基本资料</span>
          </div>
          <el-form label-position="top" class="settings-form">
            <div class="form-row">
              <el-form-item label="显示名称">
                <el-input
                  v-model="profile.name"
                  placeholder="设置你的显示名称"
                  size="large"
                  :prefix-icon="null"
                >
                  <template #prefix>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px">
                      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>
                    </svg>
                  </template>
                </el-input>
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="手机号">
                <el-input
                  :model-value="profile.phone"
                  disabled
                  size="large"
                >
                  <template #prefix>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--ink-muted)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px">
                      <rect x="5" y="2" width="14" height="20" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/>
                    </svg>
                  </template>
                </el-input>
              </el-form-item>
            </div>
            <el-button
              type="primary"
              size="large"
              :loading="profileLoading"
              @click="saveProfile"
              class="submit-btn"
            >
              保存修改
            </el-button>
          </el-form>
        </div>

        <div class="card">
          <div class="card-head">
            <span class="card-badge card-badge--warn">账号安全</span>
          </div>
          <el-form label-position="top" class="settings-form">
            <div class="form-row">
              <el-form-item label="当前密码">
                <el-input v-model="pwdForm.oldPassword" type="password" show-password size="large" placeholder="输入当前密码" />
              </el-form-item>
            </div>
            <div class="form-row form-row--split">
              <el-form-item label="新密码">
                <el-input v-model="pwdForm.newPassword" type="password" show-password size="large" placeholder="至少 8 位字符" />
              </el-form-item>
              <el-form-item label="确认新密码">
                <el-input v-model="pwdForm.confirmPassword" type="password" show-password size="large" placeholder="再次输入新密码" />
              </el-form-item>
            </div>
            <el-button type="primary" size="large" :loading="pwdLoading" @click="changePassword" class="submit-btn">
              修改密码
            </el-button>
          </el-form>
        </div>

        <div class="card">
          <div class="card-head">
            <span class="card-badge card-badge--accent">更换绑定</span>
          </div>
          <el-form label-position="top" class="settings-form">
            <div class="form-row">
              <el-form-item label="新手机号">
                <el-input v-model="phoneForm.phone" size="large" placeholder="输入新手机号" maxlength="11" />
              </el-form-item>
            </div>
            <div class="form-row">
              <el-form-item label="短信验证码">
                <div class="code-group">
                  <el-input v-model="phoneForm.code" size="large" placeholder="6 位验证码" maxlength="6" class="code-input" />
                  <el-button
                    size="large"
                    :disabled="phoneCountdown > 0"
                    @click="sendPhoneCode"
                    class="code-send-btn"
                  >
                    {{ phoneCountdown > 0 ? `${phoneCountdown}s 后重发` : '获取验证码' }}
                  </el-button>
                </div>
              </el-form-item>
            </div>
            <el-button type="primary" size="large" :loading="phoneLoading" @click="changePhone" class="submit-btn">
              更换手机号
            </el-button>
          </el-form>
        </div>
      </section>

      <!-- ========== 店铺信息 ========== -->
      <section v-if="activeTab === 'store'" class="section">
        <div class="card">
          <div class="card-head">
            <span class="card-badge">店铺资料</span>
          </div>
          <p class="card-desc">
            完善店铺信息后，系统将根据行业类型生成更精准的客户跟进与营销方案。
          </p>
          <el-form label-position="top" class="settings-form">
            <div class="form-row">
              <el-form-item label="店铺名称" :required="true">
                <el-input v-model="store.name" size="large" placeholder="如：张老板美容美发" maxlength="200" />
              </el-form-item>
            </div>
            <div class="form-row form-row--split">
              <el-form-item label="行业类型">
                <el-select v-model="store.industryType" placeholder="请选择" size="large" style="width:100%">
                  <el-option v-for="ind in ['餐饮', '美容美发', '零售', '健身', '汽车美容', '教育培训', '宠物', '其他']" :key="ind" :label="ind" :value="ind" />
                </el-select>
              </el-form-item>
              <el-form-item label="店铺地址">
                <el-input v-model="store.address" size="large" placeholder="店铺详细地址" />
              </el-form-item>
            </div>
            <el-button type="primary" size="large" :loading="storeLoading" @click="saveStore" class="submit-btn">
              保存店铺信息
            </el-button>
          </el-form>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
/* ============================================
   Settings Page — Clean, Refined Layout
   ============================================ */

.settings {
  max-width: 920px;
  margin: 0 auto;
  padding: 24px 24px 40px;
  font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", system-ui, -apple-system, sans-serif;
}

/* ---- 顶部用户卡片 ---- */
.settings-hero {
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 24px;
  background: #fff;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  margin-bottom: 18px;
}

.hero-avatar {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  background: #0072b2;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 4px 12px rgba(0, 114, 178, 0.2);
}

.avatar-text {
  color: #fff;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.hero-meta { min-width: 0; }

.hero-kicker {
  color: #0072b2;
  font-size: 0.78rem;
  font-weight: 800;
}

.hero-name {
  margin: 6px 0 4px;
  font-size: 1.3rem;
  font-weight: 700;
  color: #111827;
  letter-spacing: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hero-role {
  margin: 0;
  font-size: 0.88rem;
  color: #6b7280;
}

/* ---- Tab 导航 ---- */
.settings-tabs {
  display: flex;
  gap: 4px;
  background: #f8fafc;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  padding: 4px;
  margin-bottom: 18px;
}

.tab-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 11px 16px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #6b7280;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-item:hover { color: #374151; background: rgba(255,255,255,0.6); }

.tab-item.active {
  background: #fff;
  color: #0072b2;
  font-weight: 600;
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

/* ---- 内容区 ---- */
.settings-body { display: flex; flex-direction: column; gap: 16px; }
.section { display: flex; flex-direction: column; gap: 16px; }

/* ---- 卡片 ---- */
.card {
  background: #fff;
  border: 1px solid #e3e8ef;
  border-radius: 8px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.03);
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.06); }

.card-head { display: flex; align-items: center; margin-bottom: 18px; }

.card-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
  color: #0072b2;
  background: #e6f2f8;
  letter-spacing: 0;
}
.card-badge--warn  { color: #d97706; background: #fffbeb; }
.card-badge--accent { color: #009e73; background: #ecfdf5; }

.card-desc {
  color: #6b7280;
  font-size: 0.9rem;
  line-height: 1.6;
  margin: 0 0 24px;
}

/* ---- 表单 ---- */
.settings-form :deep(.el-form-item) { margin-bottom: 0; }
.settings-form :deep(.el-form-item__label) {
  font-size: 0.85rem;
  font-weight: 600;
  color: #374151;
  padding-bottom: 6px;
}
.settings-form :deep(.el-input__wrapper) {
  border-radius: 8px;
  box-shadow: 0 0 0 1px #e5e7eb inset;
  transition: box-shadow 0.2s;
}
.settings-form :deep(.el-input__wrapper:hover) { box-shadow: 0 0 0 1px #d1d5db inset; }
.settings-form :deep(.el-input.is-disabled .el-input__wrapper) {
  background: #f9fafb;
  box-shadow: 0 0 0 1px #e5e7eb inset;
}

.form-row { margin-bottom: 20px; }
.form-row--split { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }

/* ---- 验证码组 ---- */
.code-group { display: flex; gap: 10px; }
.code-input { flex: 2; }
.code-send-btn {
  flex: 1;
  border-radius: 8px;
  font-size: 0.85rem;
  white-space: nowrap;
  border-color: #d1d5db;
  color: #374151;
}
.code-send-btn:hover { border-color: #2563eb; color: #2563eb; }

/* ---- 提交按钮 ---- */
.submit-btn {
  margin-top: 8px;
  width: 100%;
  height: 44px;
  border-radius: 9px;
  font-size: 0.95rem;
  font-weight: 600;
  letter-spacing: 0;
  background: #0072b2;
  border-color: #0072b2;
  transition: all 0.2s;
}
.submit-btn:hover { background: #005f95; border-color: #005f95; }

@media (max-width: 480px) {
  .form-row--split { grid-template-columns: 1fr; }
  .card { padding: 20px 18px; }
  .settings-hero { padding: 24px 18px; flex-direction: column; text-align: center; }
}
</style>
