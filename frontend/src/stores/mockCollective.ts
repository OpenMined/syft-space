export interface CollectiveMember {
  id: string
  name: string
  email: string
  role: 'Admin' | 'Member'
  status: 'Active' | 'Inactive'
  lastActive: string
}

export interface CollectiveStatsSummary {
  name: string
  slug: string
  totalRevenue: number
  monthlyRevenue: number
  totalMembers: number
  activeMembers: number
  earningMembers: number
}

export interface RevenueByDate {
  date: string
  label: string
  revenue: number
}

export interface MemberUsageStat {
  id: string
  name: string
  email: string
  revenue: number
  requests: number
}

export interface CollectiveApiStat {
  id: string
  name: string
  detail: string
  revenue: number
  requests: number
}

// Wallet provided by the collective host; members can route payouts here
// instead of setting up their own. Demo UI only.
export const collectiveWalletAddress = '0xC011ec71Ve5af7000Demo000Wa11e700000Aa42'

export const collectiveStatsSummary: CollectiveStatsSummary = {
  name: 'Open Science Collective',
  slug: 'open_science_collective',
  totalRevenue: 847,
  monthlyRevenue: 243,
  totalMembers: 300,
  activeMembers: 47,
  earningMembers: 10,
}

export const collectiveMembers: CollectiveMember[] = [
  {
    id: 'member-1',
    name: 'Maya Chen',
    email: 'maya@open-science.example',
    role: 'Admin',
    status: 'Active',
    lastActive: '12 minutes ago',
  },
  {
    id: 'member-2',
    name: 'Jon Bell',
    email: 'jon@open-science.example',
    role: 'Member',
    status: 'Active',
    lastActive: '1 hour ago',
  },
  {
    id: 'member-3',
    name: 'Amina Yusuf',
    email: 'amina@open-science.example',
    role: 'Member',
    status: 'Active',
    lastActive: 'today',
  },
  {
    id: 'member-4',
    name: 'Theo Martin',
    email: 'theo@open-science.example',
    role: 'Member',
    status: 'Inactive',
    lastActive: '3 weeks ago',
  },
  {
    id: 'member-5',
    name: 'Priya Nair',
    email: 'priya@open-science.example',
    role: 'Member',
    status: 'Inactive',
    lastActive: '5 days ago',
  },
]

// Daily values sum to 847 (total collective revenue)
export const revenueByDate: RevenueByDate[] = [
  { date: '2026-05-22', label: 'May 22', revenue: 61 },
  { date: '2026-05-23', label: 'May 23', revenue: 58 },
  { date: '2026-05-24', label: 'May 24', revenue: 63 },
  { date: '2026-05-25', label: 'May 25', revenue: 57 },
  { date: '2026-05-26', label: 'May 26', revenue: 62 },
  { date: '2026-05-27', label: 'May 27', revenue: 59 },
  { date: '2026-05-28', label: 'May 28', revenue: 64 },
  { date: '2026-05-29', label: 'May 29', revenue: 56 },
  { date: '2026-05-30', label: 'May 30', revenue: 61 },
  { date: '2026-05-31', label: 'May 31', revenue: 58 },
  { date: '2026-06-01', label: 'Jun 1', revenue: 63 },
  { date: '2026-06-02', label: 'Jun 2', revenue: 60 },
  { date: '2026-06-03', label: 'Jun 3', revenue: 62 },
  { date: '2026-06-04', label: 'Jun 4', revenue: 63 },
]

export const collectiveApiStats: CollectiveApiStat[] = [
  {
    id: 'api-1',
    name: 'open_science_collective/clinical_notes_api',
    detail: 'Document retrieval across member datasets',
    revenue: 214,
    requests: 1840,
  },
  {
    id: 'api-2',
    name: 'open_science_collective/research_embeddings',
    detail: 'Vector search on shared corpora',
    revenue: 168,
    requests: 980,
  },
  {
    id: 'api-3',
    name: 'open_science_collective/protocol_summarizer',
    detail: 'Multi-resource summarization endpoint',
    revenue: 127,
    requests: 410,
  },
  {
    id: 'api-4',
    name: 'open_science_collective/shared_data_browser',
    detail: 'Cross-tenant dataset exploration',
    revenue: 89,
    requests: 273,
  },
]

export const memberUsageStats: MemberUsageStat[] = [
  { id: 'u-1', name: 'Maya Chen', email: 'maya@open-science.example', revenue: 89, requests: 142 },
  { id: 'u-2', name: 'Jon Bell', email: 'jon@open-science.example', revenue: 84, requests: 138 },
  { id: 'u-3', name: 'Amina Yusuf', email: 'amina@open-science.example', revenue: 91, requests: 151 },
  { id: 'u-4', name: 'Priya Nair', email: 'priya@open-science.example', revenue: 76, requests: 124 },
  { id: 'u-5', name: 'Leo Hart', email: 'leo@open-science.example', revenue: 82, requests: 129 },
  { id: 'u-6', name: 'Sara Okonkwo', email: 'sara@open-science.example', revenue: 88, requests: 145 },
  { id: 'u-7', name: 'Diego Ruiz', email: 'diego@open-science.example', revenue: 79, requests: 133 },
  { id: 'u-8', name: 'Elena Vogt', email: 'elena@open-science.example', revenue: 86, requests: 140 },
  { id: 'u-9', name: 'Noah Park', email: 'noah@open-science.example', revenue: 81, requests: 127 },
  { id: 'u-10', name: 'Iris Malik', email: 'iris@open-science.example', revenue: 83, requests: 131 },
  { id: 'u-11', name: 'Theo Martin', email: 'theo@open-science.example', revenue: 0, requests: 0 },
  { id: 'u-12', name: 'Camille Dubois', email: 'camille@open-science.example', revenue: 0, requests: 7 },
  { id: 'u-13', name: 'Raj Patel', email: 'raj@open-science.example', revenue: 0, requests: 4 },
  { id: 'u-14', name: 'Hannah Lee', email: 'hannah@open-science.example', revenue: 0, requests: 11 },
]
