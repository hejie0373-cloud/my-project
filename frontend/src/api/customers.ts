import http from './http'
import type { CustomerListResponse, CustomerDetail, Visit, ImportProgress } from '@/types/customer'

export const listCustomers = (params: {
  search?: string
  riskLevel?: string
  page?: number
  pageSize?: number
}) => http.get<CustomerListResponse>('/customers', { params })

export const createCustomer = (data: Record<string, unknown>) =>
  http.post<CustomerDetail>('/customers', data)

export const getCustomer = (id: string) =>
  http.get<CustomerDetail>(`/customers/${id}`)

export const updateCustomer = (id: string, data: Record<string, unknown>) =>
  http.put<CustomerDetail>(`/customers/${id}`, data)

export const deleteCustomer = (id: string) =>
  http.delete(`/customers/${id}`)

export const createVisit = (customerId: string, data: Record<string, unknown>) =>
  http.post<Visit>(`/customers/${customerId}/visits`, data)

export const getVisits = (customerId: string, limit = 50) =>
  http.get<Visit[]>(`/customers/${customerId}/visits`, { params: { limit } })

export const importCSV = (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return http.post<{ taskId: string }>('/customers/import', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getImportProgress = (taskId: string) =>
  http.get<ImportProgress>(`/customers/import/${taskId}`)
