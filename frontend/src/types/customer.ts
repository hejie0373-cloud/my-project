export interface CustomerListItem {
  id: string
  name: string
  phone: string
  gender: string
  churnScore: number | null
  clv: number | null
  lastVisitedAt: string | null
  visitCount: number
  createdAt: string
}

export interface CustomerListResponse {
  items: CustomerListItem[]
  total: number
  page: number
  pageSize: number
}

export interface Visit {
  id: string
  customerId: string
  storeId: string
  visitedAt: string
  serviceType: string
  staffName: string | null
  amount: number
  paymentMethod: string | null
  feedback: string | null
  source: string
  createdAt: string
}

export interface AiMetricSummary {
  churnScore: number | null
  clv: number | null
  recommendation: string | null
  computedAt: string | null
}

export interface CustomerDetail {
  id: string
  storeId: string
  name: string
  phone: string
  email: string | null
  gender: string
  birthday: string | null
  address: string | null
  preferredContact: string
  isDeleted: boolean
  createdAt: string
  updatedAt: string
  aiMetric: AiMetricSummary | null
  recentVisits: Visit[]
  visitCount: number
}

export interface ImportProgress {
  taskId: string
  total: number
  success: number
  failed: number
  status: 'processing' | 'done' | 'error'
  errors: { row: number; field: string; reason: string }[]
}
