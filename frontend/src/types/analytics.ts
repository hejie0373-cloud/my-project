export interface DashboardData {
  totalCustomers: number
  highRiskCount: number
  highValueCount: number
  todayVisits: number
  visitTrend: { date: string; count: number }[]
  topRiskCustomers: { id: string; name: string; phone: string; churnScore: number }[]
  churnDistribution: { high: number; medium: number; low: number }
}

export interface VisitReportItem {
  period: string
  visitCount: number
  uniqueCustomers: number
}

export interface RevenueReportItem {
  period: string
  totalAmount: number
  avgAmount: number
  paymentDistribution: Record<string, number>
}

export interface AiReportData {
  highRiskCount: number
  churnScoreDistribution: Record<string, number>
  clvAvg: number
  copyAdoptionRate: number
  totalCustomersScored: number
}

export interface NotificationMsg {
  type: 'high_risk_alert' | 'campaign_sent' | 'system'
  payload: Record<string, unknown>
  readAt: string | null
}
