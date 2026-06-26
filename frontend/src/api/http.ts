import axios from 'axios'
import camelcaseKeys from 'camelcase-keys'
import snakecaseKeys from 'snakecase-keys'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：camelCase → snake_case + 附加 Token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  if (config.data && typeof config.data === 'object' && !(config.data instanceof FormData)) {
    config.data = snakecaseKeys(config.data, { deep: true })
  }
  if (config.params && typeof config.params === 'object') {
    config.params = snakecaseKeys(config.params, { deep: true })
  }
  return config
})

// 响应拦截器：snake_case → camelCase + 401 自动刷新
let isRefreshing = false
let refreshSubscribers: ((token: string) => void)[] = []

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token))
  refreshSubscribers = []
}

http.interceptors.response.use(
  (response) => {
    if (response.data && typeof response.data === 'object') {
      response.data = camelcaseKeys(response.data, { deep: true })
    }
    return response
  },
  async (error) => {
    const { config, response } = error

    // 401 → 尝试刷新 Token
    if (response?.status === 401 && !config._retry) {
      const refreshToken = sessionStorage.getItem('refreshToken')
      if (!refreshToken) {
        // 没有 refreshToken 说明还未登录，直接显示错误
        ElMessage.error(response?.data?.detail || '登录失败')
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve) => {
          refreshSubscribers.push((token: string) => {
            config.headers.Authorization = `Bearer ${token}`
            resolve(http(config))
          })
        })
      }

      config._retry = true
      isRefreshing = true

      try {
        const { data } = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
        const newAccess = data.access_token || data.accessToken
        const newRefresh = data.refresh_token || data.refreshToken

        localStorage.setItem('accessToken', newAccess)
        if (newRefresh) sessionStorage.setItem('refreshToken', newRefresh)

        onRefreshed(newAccess)
        isRefreshing = false

        config.headers.Authorization = `Bearer ${newAccess}`
        return http(config)
      } catch {
        isRefreshing = false
        redirectToLogin()
        return Promise.reject(error)
      }
    }

    // 错误提示
    const detail = response?.data?.detail || error.message || '请求失败'
    if (response?.status === 402) {
      const paymentMessage =
        detail === 'TRIAL_CREDITS_EXHAUSTED'
          ? '免费体验次数已用完，请开通套餐后继续使用'
          : detail === 'FEATURE_REQUIRES_UPGRADE'
            ? '当前套餐不包含此功能，请升级套餐后继续使用'
            : '请先开通套餐后继续使用'
      ElMessage.warning(paymentMessage)
      if (!window.location.pathname.startsWith('/billing')) {
        window.location.href = '/billing'
      }
      return Promise.reject(error)
    }

    if (response?.status !== 401) {
      ElMessage.error(detail)
    }
    return Promise.reject(error)
  },
)

function redirectToLogin() {
  localStorage.removeItem('accessToken')
  sessionStorage.removeItem('refreshToken')
  if (!window.location.pathname.startsWith('/auth/')) {
    window.location.href = '/auth/signin'
  }
}

export default http
