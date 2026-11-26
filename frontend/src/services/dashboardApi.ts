import { apiRequest } from './authApi'

export interface DashboardSummary {
  total_executions: number
  pass_count: number
  fail_count: number
  error_count: number
  incomplete_count: number
  success_rate_percent: number
  average_duration_seconds: number | null
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return apiRequest<DashboardSummary>('/api/v1/dashboard/summary', {
    cache: 'no-store',
  })
}

export interface NodeStatistics {
  node_name: string
  total_executions: number
  pass_count: number
  fail_count: number
  error_count: number
  incomplete_count: number
  success_rate_percent: number
  average_duration_seconds: number | null
}

export interface NodeStatisticsPage {
  items: NodeStatistics[]
  total_nodes: number
  page: number
  page_size: number
}

export async function fetchDashboardNodes(page = 1, pageSize = 10): Promise<NodeStatisticsPage> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  })

  return apiRequest<NodeStatisticsPage>(`/api/v1/dashboard/nodes?${params.toString()}`, {
    cache: 'no-store',
  })
}

export interface DailyTrend {
  day: string
  total_executions: number
  pass_count: number
  fail_count: number
  error_count: number
  incomplete_count: number
  success_rate_percent: number
}

export interface DailyTrendPage {
  items: DailyTrend[]
  total_days: number
  page: number
  page_size: number
}

export async function fetchDashboardTrends(nodeName?: string): Promise<DailyTrendPage> {
  const startedFrom = new Date()

  startedFrom.setUTCHours(0, 0, 0, 0)
  startedFrom.setUTCDate(startedFrom.getUTCDate() - 29)

  const params = new URLSearchParams({
    page: '1',
    page_size: '30',
    started_from: startedFrom.toISOString(),
  })

  if (nodeName?.trim()) {
    params.set('node_name', nodeName.trim())
  }

  return apiRequest<DailyTrendPage>(`/api/v1/dashboard/trends?${params.toString()}`, {
    cache: 'no-store',
  })
}
