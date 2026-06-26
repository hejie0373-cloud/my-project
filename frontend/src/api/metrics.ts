import http from './http'

export interface ChurnScoreResult {
  customerId: string
  churnScore: number
  clv: number
  recommendation: string
  dimensions: Record<string, number>
  computedAt: string
}

export interface CopyResult {
  customerId: string
  channel: string
  content: string
  requireConfirmation: boolean
  source: string
}

export const triggerChurnScore = (customerId: string) =>
  http.post<ChurnScoreResult>(`/metrics/churn/${customerId}`)

export const getChurnScore = (customerId: string) =>
  http.get<ChurnScoreResult>(`/metrics/churn/${customerId}`)

export const getCLV = (customerId: string) =>
  http.get<{ clv: number; avgMonthlySpend: number; retentionMonths: number }>(
    `/metrics/lifetime-value/${customerId}`,
  )

export const generateCopy = (customerId: string, channel: string) =>
  http.post<CopyResult>('/metrics/copy', { customerId, channel })

export const askInsight = (question: string) =>
  http.post<{ answer: string }>('/metrics/insight', null, { params: { question } })
