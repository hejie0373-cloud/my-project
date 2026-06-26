import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { TokenResponse, User } from '@/types/auth'
import * as authApi from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('accessToken'))
  const refreshToken = ref<string | null>(sessionStorage.getItem('refreshToken'))

  const isLoggedIn = computed(() => !!accessToken.value)
  const hasStore = computed(() => !!user.value?.storeId)
  const roles = computed(() => user.value?.roles || [])

  async function sendCode(phone: string) {
    await authApi.sendCode(phone)
  }

  async function loginByPhone(phone: string, code: string) {
    const { data } = await authApi.loginByPhone(phone, code)
    // 新用户 → 返回 isNewUser 标记，不设置 tokens
    if ('isNewUser' in data && data.isNewUser) {
      return { isNewUser: true, phone: data.phone }
    }
    // 老用户 → 设置 tokens
    const tokens = data as TokenResponse
    setTokens(tokens.accessToken, tokens.refreshToken)
    await fetchMe()
    return { isNewUser: false }
  }

  async function loginByPassword(phone: string, password: string) {
    const { data } = await authApi.loginByPassword(phone, password)
    setTokens(data.accessToken, data.refreshToken)
    await fetchMe()
  }

  async function registerByPhone(phone: string, code: string, password: string) {
    const { data } = await authApi.registerByPhone(phone, code, password)
    setTokens(data.accessToken, data.refreshToken)
    await fetchMe()
  }

  async function fetchMe() {
    try {
      const { data } = await authApi.getMe()
      user.value = data
    } catch {
      // 未登录或 token 失效
    }
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('accessToken', access)
    sessionStorage.setItem('refreshToken', refresh)
  }

  async function logout() {
    const rt = refreshToken.value
    // 先清本地状态，确保路由守卫立刻生效
    accessToken.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('accessToken')
    sessionStorage.removeItem('refreshToken')
    // 后台通知服务端作废 token（不阻塞跳转）
    if (rt) {
      try { await authApi.logout(rt) } catch { /* ignore */ }
    }
  }

  return {
    user, accessToken, refreshToken, isLoggedIn, hasStore, roles,
    sendCode, registerByPhone, loginByPhone, loginByPassword, fetchMe, setTokens, logout,
  }
})
