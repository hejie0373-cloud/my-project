export interface CampaignCreate {
  name: string
  template: string
  channels: ('sms' | 'email' | 'wechat')[]
  scheduledAt: string | null
  targetCustomerIds: string[] | null
  targetRiskLevel: 'high' | 'all' | null
}

export interface CampaignLogSummary {
  total: number
  sent: number
  failed: number
  pending: number
}

export interface Campaign {
  id: string
  storeId: string
  name: string
  template: string
  channels: string[]
  scheduledAt: string | null
  status: 'draft' | 'scheduled' | 'sent' | 'failed'
  createdBy: string | null
  createdAt: string
  logSummary: CampaignLogSummary | null
}

export interface CampaignListResponse {
  items: Campaign[]
  total: number
  page: number
  pageSize: number
}
