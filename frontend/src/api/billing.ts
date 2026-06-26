import http from './http'

export interface Plan {
  code: 'free' | 'basic' | 'professional'
  name: string
  priceCents: number
  customerLimit: number
  aiDailyLimit: number
  campaignDailyLimit: number
  hasExport: boolean
}

export interface Subscription {
  storeId: string
  planName: string
  planDisplayName: string | null
  status: string
  customerLimit: number
  aiUsedToday: number
  aiDailyLimit: number
  campaignUsedToday: number
  campaignDailyLimit: number
  hasExport: boolean
  nextBillingDate: string | null
  paymentMethod: string | null
  isActive: boolean
}

export interface PaymentOrder {
  id: string
  storeId: string
  storeName?: string | null
  planName: string
  provider: string
  status: string
  amountCents: number
  currency: string
  checkoutUrl: string | null
  providerOrderId: string | null
  paidAt: string | null
  expiresAt: string
  createdAt: string
}

export interface AdminPaymentSummary {
  todayRevenueCents: number
  monthRevenueCents: number
  paidOrders: number
  pendingOrders: number
  failedOrders: number
  planCounts: Record<string, number>
  statusCounts: Record<string, number>
}

export interface AdminSubscriptionUpdate {
  planName?: 'free' | 'basic' | 'professional'
  status?: 'active' | 'overdue' | 'cancelled'
  customerLimit?: number
  nextBillingDate?: string | null
}

export const getPlans = () =>
  http.get<Plan[]>('/billing/plans')

export const getSubscription = () =>
  http.get<Subscription>('/billing/subscription')

export const createOrder = (planName: string, provider = 'mock') =>
  http.post<PaymentOrder>('/billing/orders', { planName, provider })

export const getOrder = (orderId: string) =>
  http.get<PaymentOrder>(`/billing/orders/${orderId}`)

export const confirmAlipayReturn = (orderId: string, params: Record<string, string>) =>
  http.post<PaymentOrder>(`/payment/alipay/return/${orderId}`, params)

export const syncAlipayOrder = (orderId: string) =>
  http.post<PaymentOrder>(`/payment/alipay/sync/${orderId}`)

export const mockPay = (orderId: string) =>
  http.post<PaymentOrder>(`/billing/orders/${orderId}/mock-pay`)

export const listAdminOrders = (params?: { page?: number; pageSize?: number; status?: string }) =>
  http.get<{ items: PaymentOrder[]; total: number; page: number; pageSize: number }>('/admin/payment-orders', { params })

export const getAdminPaymentSummary = () =>
  http.get<AdminPaymentSummary>('/admin/payment-summary')

export const listStoreOrders = (storeId: string, params?: { page?: number; pageSize?: number }) =>
  http.get<{ items: PaymentOrder[]; total: number; page: number; pageSize: number }>(`/admin/stores/${storeId}/payment-orders`, { params })

export const updateStoreSubscription = (storeId: string, data: AdminSubscriptionUpdate) =>
  http.put<Subscription>(`/admin/stores/${storeId}/subscription`, data)
