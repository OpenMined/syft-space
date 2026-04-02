export type TimeRange = '7d' | '30d' | '90d' | '1y'

export interface StatCard {
  value: number
  change_value: number
  change_label: string
}

export interface SummaryStatsResponse {
  active_endpoints: StatCard
  total_queries: StatCard
  total_revenue: StatCard
  active_users: StatCard
}

export interface TimeSeriesPoint {
  label: string
  value: number
}

export interface TimeSeriesResponse {
  query_volume: TimeSeriesPoint[]
  user_activity: TimeSeriesPoint[]
  revenue: TimeSeriesPoint[]
}

export interface TopUserEntry {
  user_email: string
  query_count: number
  revenue: number
}

export interface TopUsersResponse {
  users: TopUserEntry[]
}

export interface WordCloudEntry {
  word: string
  count: number
}

export interface WordCloudResponse {
  words: WordCloudEntry[]
}

export interface AnalyticsFilters {
  time_range: TimeRange
  endpoint_id?: string
}
