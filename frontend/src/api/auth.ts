import http from './http'
import type { TokenResponse, User } from '@/types/auth'

export const sendCode = (phone: string) =>
  http.post<{ message: string }>('/auth/send-code', { phone })

export const loginByPhone = (phone: string, code: string) =>
  http.post<TokenResponse | { isNewUser: boolean; phone: string }>('/auth/login/phone', { phone, code })

export const loginByPassword = (phone: string, password: string) =>
  http.post<TokenResponse>('/auth/login/password', { phone, password })

export const registerByPhone = (phone: string, code: string, password: string) =>
  http.post<TokenResponse>('/auth/register/phone', { phone, code, password })

export const refreshToken = (token: string) =>
  http.post<TokenResponse>('/auth/refresh', { refreshToken: token })

export const logout = (token: string) =>
  http.post<{ message: string }>('/auth/logout', { refreshToken: token })

export const getMe = () =>
  http.get<User>('/users/me')

export const updateProfile = (data: { name?: string; avatarUrl?: string }) =>
  http.put<{ message: string }>('/users/me', data)

export const changePassword = (oldPassword: string, newPassword: string) =>
  http.post<{ message: string }>('/users/me/change-password', { oldPassword, newPassword })

export const changePhone = (phone: string, code: string) =>
  http.post<{ message: string }>('/users/me/change-phone', { phone, code })

// ---- QR 扫码登录 ----

export const qrGenerate = () =>
  http.post<{ qrId: string; qrUrl: string; qrImage: string; expiresIn: number }>('/auth/qr/generate')

export const qrStatus = (qrId: string) =>
  http.get<{ status: string; tokens?: TokenResponse; userName?: string }>(`/auth/qr/status/${qrId}`)

export const qrConfirm = (qrId: string) =>
  http.post<{ message: string }>('/auth/qr/confirm', { qrId })

// ---- 微信扫码登录 ----

export const getWechatQrUrl = () =>
  http.get<{ qrUrl: string; state: string; expiresIn: number }>('/auth/wechat/qr-url')

export const getWechatStatus = (state: string) =>
  http.get<{ status: string; tokens?: TokenResponse; message?: string }>(`/auth/wechat/status/${state}`)

export const bindWechatByPassword = (state: string, phone: string, password: string) =>
  http.post<{ status: string; tokens?: TokenResponse; message?: string }>('/auth/wechat/bind-password', {
    state,
    phone,
    password,
  })
