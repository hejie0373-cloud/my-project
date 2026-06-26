import http from './http'
import type { CampaignListResponse, Campaign, CampaignCreate } from '@/types/campaign'

export const listCampaigns = (params: { page?: number; pageSize?: number }) =>
  http.get<CampaignListResponse>('/campaigns', { params })

export const createCampaign = (data: CampaignCreate) =>
  http.post<Campaign>('/campaigns', data)

export const getCampaign = (id: string) =>
  http.get<Campaign>(`/campaigns/${id}`)

export const getCampaignLogs = (id: string, params?: { page?: number; pageSize?: number }) =>
  http.get<{ items: unknown[]; total: number }>(`/campaigns/${id}/logs`, { params })
