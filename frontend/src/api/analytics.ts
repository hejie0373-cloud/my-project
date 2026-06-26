import http from './http'
import type { DashboardData } from '@/types/analytics'

export const getDashboard = () =>
  http.get<DashboardData>('/analytics/dashboard')

export const getReport = (params: {
  type: string
  startDate: string
  endDate: string
  granularity?: string
}) => http.get('/analytics/reports', { params })

export const exportCSV = (params: { type: string; startDate?: string; endDate?: string }) =>
  http.get('/analytics/export', { params, responseType: 'blob' })
