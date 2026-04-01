export interface StatCard {
  label: string
  value: string
  change: string
  changeType: 'positive' | 'neutral'
  icon: 'check' | 'activity' | 'dollar' | 'users'
}

export interface ActiveUser {
  name: string
  queries: number
  revenue: number
  color: string
}

export const mockStatCards: StatCard[] = [
  {
    label: 'Active Endpoints',
    value: '0',
    change: '+2 from last week',
    changeType: 'positive',
    icon: 'check',
  },
  {
    label: 'Total Queries',
    value: '127.4k',
    change: '+22.4% from last period',
    changeType: 'positive',
    icon: 'activity',
  },
  {
    label: 'Total Revenue',
    value: '$4,285.85',
    change: '$1,125.40 this month',
    changeType: 'positive',
    icon: 'dollar',
  },
  {
    label: 'Active Users',
    value: '486',
    change: '30d',
    changeType: 'neutral',
    icon: 'users',
  },
]

export const mockActiveUsers: ActiveUser[] = [
  { name: 'alice', queries: 2847, revenue: 1247.85, color: 'bg-emerald-500' },
  { name: 'bob', queries: 1923, revenue: 856.4, color: 'bg-amber-500' },
  { name: 'charlie', queries: 1654, revenue: 723.5, color: 'bg-amber-500' },
  { name: 'diana', queries: 1432, revenue: 645.2, color: 'bg-amber-500' },
  { name: 'eve', queries: 1287, revenue: 578.9, color: 'bg-amber-500' },
]

export const mockQueryVolumeLabels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
export const mockQueryVolumeData = [9000, 9500, 12500, 15800]

export const mockUserActivityLabels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
export const mockUserActivityData = [145, 160, 210, 290]

export const mockRevenueLabels = ['Week 1', 'Week 2', 'Week 3', 'Week 4']
export const mockRevenueData = [1850, 2100, 2650, 3400]

export const timeRangeOptions = ['Last 7 days', 'Last 30 days', 'Last 90 days', 'Last year']
export const endpointOptions = ['All Endpoints', 'Document Analysis API', 'Code Review Assistant']
export const datasetOptions = ['All Datasets', 'Training Data v2', 'Customer Records']

// Retention cohort data — each row is a cohort, values are % retained per week
export interface RetentionCohort {
  label: string
  color: string
  data: number[]
}

export const retentionLabels = ['Week 0', 'Week 1', 'Week 2', 'Week 3', 'Week 4', 'Week 5', 'Week 6']

export const mockRetentionCohorts: RetentionCohort[] = [
  { label: 'Jan cohort', color: '#10b981', data: [100, 72, 58, 49, 43, 40, 38] },
  { label: 'Feb cohort', color: '#3b82f6', data: [100, 78, 65, 55, 50, 47, 44] },
  { label: 'Mar cohort', color: '#8b5cf6', data: [100, 81, 70, 62, 57, 53, 51] },
]

// Trending query topics — anonymized, Google-Search-style
export interface TrendingTopic {
  rank: number
  topic: string
  volume: number
  trend: 'up' | 'down' | 'stable'
  changePercent: number
}

export const mockTrendingTopics: TrendingTopic[] = [
  { rank: 1, topic: 'contract clause extraction', volume: 4820, trend: 'up', changePercent: 34 },
  { rank: 2, topic: 'quarterly earnings summary', volume: 3915, trend: 'up', changePercent: 21 },
  { rank: 3, topic: 'compliance policy lookup', volume: 3340, trend: 'stable', changePercent: 2 },
  { rank: 4, topic: 'product spec comparison', volume: 2780, trend: 'up', changePercent: 18 },
  { rank: 5, topic: 'customer sentiment analysis', volume: 2510, trend: 'down', changePercent: 5 },
  { rank: 6, topic: 'technical documentation search', volume: 2190, trend: 'up', changePercent: 12 },
  { rank: 7, topic: 'invoice data extraction', volume: 1870, trend: 'stable', changePercent: 1 },
  { rank: 8, topic: 'meeting transcript Q&A', volume: 1640, trend: 'up', changePercent: 45 },
  { rank: 9, topic: 'patent similarity matching', volume: 1380, trend: 'down', changePercent: 8 },
  { rank: 10, topic: 'HR policy clarification', volume: 1120, trend: 'stable', changePercent: 3 },
]
