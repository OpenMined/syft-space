import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface Collective {
  id: string
  name: string
  slug: string
  description: string
  logo?: string
  domain: string
  capabilities: {
    collectiveEndpoint: boolean
    multiTenancyHosting: boolean
    memberVetting: boolean
    collectiveTerms: boolean
  }
  membershipVisibility: 'anyone' | 'invite-only'
  role: 'admin' | 'member'
  createdAt: Date
}

export interface Member {
  id: string
  name: string
  email: string
  role: 'admin' | 'member'
  subdomain?: string // e.g., "irina.harvard.syftbox.net"
  joinedAt: Date
  endpoints: MemberEndpoint[]
}

export interface MemberEndpoint {
  id: string
  name: string
  type: 'data' | 'model'
  usesCollectivePricing: boolean
  usesCollectiveAccess: boolean
  assignedPricingTier?: string // tier id
}

export interface Request {
  id: string
  type: 'join' | 'invite'
  userId: string
  userName: string
  userEmail: string
  collectiveId: string
  collectiveName: string
  status: 'pending' | 'approved' | 'rejected'
  createdAt: Date
  message?: string
}

export interface PricingTier {
  id: string
  name: string
  description: string
  price: number
  priceUnit: 'per_call' | 'per_token'
  isDefault?: boolean
}

export interface AccessRule {
  id: string
  name: string
  description: string
  type: 'public' | 'approved-only' | 'members-only'
}

export interface CollectiveAnalytics {
  collectiveId: string
  totalQueries: number
  totalRevenue: number
  averageResponseTime: number
  queryHistory: QueryHistoryPoint[]
  revenueHistory: RevenueHistoryPoint[]
  topEndpoints: EndpointStat[]
  memberStats: MemberStat[]
}

export interface QueryHistoryPoint {
  date: string
  queries: number
}

export interface RevenueHistoryPoint {
  date: string
  revenue: number
}

export interface EndpointStat {
  endpointId: string
  endpointName: string
  memberName: string
  queries: number
  revenue: number
  avgResponseTime: number
}

export interface MemberStat {
  memberId: string
  memberName: string
  queries: number
  revenue: number
  endpointCount: number
}

export const useCollectivesStore = defineStore('collectives', () => {
  const collectives = ref<Collective[]>([
    {
      id: '1',
      name: 'Harvard',
      slug: 'harvard',
      description: 'Harvard University research collective for sharing academic datasets and models',
      domain: 'harvard.syftbox.net',
      capabilities: {
        collectiveEndpoint: true,
        multiTenancyHosting: true,
        memberVetting: true,
        collectiveTerms: true,
      },
      membershipVisibility: 'anyone',
      role: 'admin',
      createdAt: new Date('2024-01-15'),
    },
    {
      id: '2',
      name: 'TCP Collective',
      slug: 'tcp-collective',
      description: 'The Collective Protocol - A community-driven data sharing initiative',
      domain: 'tcp-collective.syftbox.net',
      capabilities: {
        collectiveEndpoint: true,
        multiTenancyHosting: false,
        memberVetting: true,
        collectiveTerms: true,
      },
      membershipVisibility: 'invite-only',
      role: 'member',
      createdAt: new Date('2024-02-20'),
    },
  ])

  const members = ref<Record<string, Member[]>>({
    '1': [
      {
        id: 'm1',
        name: 'Irina Doe',
        email: 'irina@harvard.edu',
        role: 'admin',
        subdomain: 'irina.harvard.syftbox.net',
        joinedAt: new Date('2024-01-15'),
        endpoints: [
          {
            id: 'e1',
            name: 'Legal Documents Store',
            type: 'data',
            usesCollectivePricing: true,
            usesCollectiveAccess: false,
            assignedPricingTier: 'pt1',
          },
          {
            id: 'e2',
            name: 'Research Papers API',
            type: 'data',
            usesCollectivePricing: true,
            usesCollectiveAccess: true,
            assignedPricingTier: 'pt2',
          },
        ],
      },
      {
        id: 'm2',
        name: 'John Smith',
        email: 'john.smith@harvard.edu',
        role: 'member',
        subdomain: 'john.harvard.syftbox.net',
        joinedAt: new Date('2024-02-01'),
        endpoints: [
          {
            id: 'e3',
            name: 'Medical Research Dataset',
            type: 'data',
            usesCollectivePricing: true,
            usesCollectiveAccess: true,
            assignedPricingTier: 'pt1',
          },
        ],
      },
      {
        id: 'm3',
        name: 'Alice Johnson',
        email: 'alice.j@harvard.edu',
        role: 'member',
        subdomain: undefined,
        joinedAt: new Date('2024-02-15'),
        endpoints: [],
      },
    ],
    '2': [
      {
        id: 'm4',
        name: 'Bob Williams',
        email: 'bob@tcp.org',
        role: 'admin',
        subdomain: 'bob.tcp-collective.syftbox.net',
        joinedAt: new Date('2024-02-20'),
        endpoints: [
          {
            id: 'e4',
            name: 'Climate Data Archive',
            type: 'data',
            usesCollectivePricing: false,
            usesCollectiveAccess: false,
          },
        ],
      },
      {
        id: 'm5',
        name: 'Carol Davis',
        email: 'carol@example.com',
        role: 'member',
        subdomain: undefined,
        joinedAt: new Date('2024-03-01'),
        endpoints: [],
      },
    ],
  })

  const requests = ref<Request[]>([
    {
      id: 'r1',
      type: 'join',
      userId: 'u100',
      userName: 'Sarah Miller',
      userEmail: 'sarah.m@example.com',
      collectiveId: '1',
      collectiveName: 'Harvard',
      status: 'pending',
      createdAt: new Date('2024-11-20T10:30:00'),
      message: 'I am a PhD researcher studying machine learning and would like to contribute my datasets.',
    },
    {
      id: 'r2',
      type: 'join',
      userId: 'u101',
      userName: 'Tom Anderson',
      userEmail: 'tom.a@example.com',
      collectiveId: '1',
      collectiveName: 'Harvard',
      status: 'pending',
      createdAt: new Date('2024-11-21T14:15:00'),
      message: 'Working on NLP research, would love to join and share my work.',
    },
  ])

  const pricingTiers = ref<Record<string, PricingTier[]>>({
    '1': [
      {
        id: 'pt1',
        name: 'Standard',
        description: 'Standard pricing for general access',
        price: 0.001,
        priceUnit: 'per_token',
        isDefault: true,
      },
      {
        id: 'pt2',
        name: 'Premium',
        description: 'Premium tier with priority support',
        price: 0.002,
        priceUnit: 'per_token',
        isDefault: false,
      },
    ],
    '2': [
      {
        id: 'pt3',
        name: 'Basic',
        description: 'Basic tier for public data',
        price: 0.0005,
        priceUnit: 'per_call',
        isDefault: true,
      },
    ],
  })

  const accessRules = ref<Record<string, AccessRule[]>>({
    '1': [
      {
        id: 'ar1',
        name: 'Public Access',
        description: 'Open access for anyone',
        type: 'public',
      },
    ],
  })

  const analytics = ref<Record<string, CollectiveAnalytics>>({
    '1': {
      collectiveId: '1',
      totalQueries: 45823,
      totalRevenue: 1247.56,
      averageResponseTime: 342,
      queryHistory: [
        { date: '2024-11-14', queries: 1523 },
        { date: '2024-11-15', queries: 1876 },
        { date: '2024-11-16', queries: 2134 },
        { date: '2024-11-17', queries: 1945 },
        { date: '2024-11-18', queries: 2287 },
        { date: '2024-11-19', queries: 2456 },
        { date: '2024-11-20', queries: 2789 },
        { date: '2024-11-21', queries: 3124 },
      ],
      revenueHistory: [
        { date: '2024-11-14', revenue: 42.15 },
        { date: '2024-11-15', revenue: 51.23 },
        { date: '2024-11-16', revenue: 67.89 },
        { date: '2024-11-17', revenue: 58.45 },
        { date: '2024-11-18', revenue: 73.21 },
        { date: '2024-11-19', revenue: 89.67 },
        { date: '2024-11-20', revenue: 102.34 },
        { date: '2024-11-21', revenue: 118.92 },
      ],
      topEndpoints: [
        {
          endpointId: 'e1',
          endpointName: 'Legal Documents Store',
          memberName: 'Irina Doe',
          queries: 18456,
          revenue: 523.45,
          avgResponseTime: 289,
        },
        {
          endpointId: 'e2',
          endpointName: 'Research Papers API',
          memberName: 'Irina Doe',
          queries: 15234,
          revenue: 445.67,
          avgResponseTime: 312,
        },
        {
          endpointId: 'e3',
          endpointName: 'Medical Research Dataset',
          memberName: 'John Smith',
          queries: 12133,
          revenue: 278.44,
          avgResponseTime: 398,
        },
      ],
      memberStats: [
        {
          memberId: 'm1',
          memberName: 'Irina Doe',
          queries: 33690,
          revenue: 969.12,
          endpointCount: 2,
        },
        {
          memberId: 'm2',
          memberName: 'John Smith',
          queries: 12133,
          revenue: 278.44,
          endpointCount: 1,
        },
      ],
    },
    '2': {
      collectiveId: '2',
      totalQueries: 8934,
      totalRevenue: 234.67,
      averageResponseTime: 412,
      queryHistory: [
        { date: '2024-11-14', queries: 823 },
        { date: '2024-11-15', queries: 956 },
        { date: '2024-11-16', queries: 1087 },
        { date: '2024-11-17', queries: 1145 },
        { date: '2024-11-18', queries: 1234 },
        { date: '2024-11-19', queries: 1356 },
        { date: '2024-11-20', queries: 1489 },
        { date: '2024-11-21', queries: 1844 },
      ],
      revenueHistory: [
        { date: '2024-11-14', revenue: 18.45 },
        { date: '2024-11-15', revenue: 21.32 },
        { date: '2024-11-16', revenue: 24.67 },
        { date: '2024-11-17', revenue: 27.89 },
        { date: '2024-11-18', revenue: 31.23 },
        { date: '2024-11-19', revenue: 35.78 },
        { date: '2024-11-20', revenue: 39.45 },
        { date: '2024-11-21', revenue: 35.88 },
      ],
      topEndpoints: [
        {
          endpointId: 'e4',
          endpointName: 'Climate Data Archive',
          memberName: 'Bob Williams',
          queries: 8934,
          revenue: 234.67,
          avgResponseTime: 412,
        },
      ],
      memberStats: [
        {
          memberId: 'm4',
          memberName: 'Bob Williams',
          queries: 8934,
          revenue: 234.67,
          endpointCount: 1,
        },
      ],
    },
  })

  const getCollectiveBySlug = (slug: string) => {
    return collectives.value.find((c) => c.slug === slug)
  }

  const getMembersByCollectiveId = (collectiveId: string) => {
    return members.value[collectiveId] || []
  }

  const getPendingRequests = () => {
    return requests.value.filter((r) => r.status === 'pending')
  }

  const approveRequest = (requestId: string) => {
    const request = requests.value.find((r) => r.id === requestId)
    if (request) {
      request.status = 'approved'
    }
  }

  const rejectRequest = (requestId: string) => {
    const request = requests.value.find((r) => r.id === requestId)
    if (request) {
      request.status = 'rejected'
    }
  }

  const addCollective = (collective: Omit<Collective, 'id' | 'createdAt'>) => {
    const newCollective: Collective = {
      ...collective,
      id: Math.random().toString(36).substr(2, 9),
      createdAt: new Date(),
    }
    collectives.value.push(newCollective)
    return newCollective
  }

  const addPricingTier = (collectiveId: string, tier: Omit<PricingTier, 'id'>) => {
    const newTier: PricingTier = {
      ...tier,
      id: 'pt_' + Math.random().toString(36).substr(2, 9),
    }
    if (!pricingTiers.value[collectiveId]) {
      pricingTiers.value[collectiveId] = []
    }
    pricingTiers.value[collectiveId].push(newTier)
    return newTier
  }

  const updatePricingTier = (collectiveId: string, tierId: string, updates: Partial<PricingTier>) => {
    const tiers = pricingTiers.value[collectiveId]
    if (tiers) {
      const tier = tiers.find((t) => t.id === tierId)
      if (tier) {
        Object.assign(tier, updates)
      }
    }
  }

  const deletePricingTier = (collectiveId: string, tierId: string) => {
    const tiers = pricingTiers.value[collectiveId]
    if (tiers) {
      const index = tiers.findIndex((t) => t.id === tierId)
      if (index > -1) {
        tiers.splice(index, 1)
      }
    }
  }

  const assignPricingTierToEndpoint = (
    collectiveId: string,
    memberId: string,
    endpointId: string,
    tierId: string
  ) => {
    const memberList = members.value[collectiveId]
    if (memberList) {
      const member = memberList.find((m) => m.id === memberId)
      if (member) {
        const endpoint = member.endpoints.find((e) => e.id === endpointId)
        if (endpoint) {
          endpoint.assignedPricingTier = tierId
        }
      }
    }
  }

  const getAnalytics = (collectiveId: string) => {
    return analytics.value[collectiveId]
  }

  return {
    collectives,
    members,
    requests,
    pricingTiers,
    accessRules,
    analytics,
    getCollectiveBySlug,
    getMembersByCollectiveId,
    getPendingRequests,
    approveRequest,
    rejectRequest,
    addCollective,
    addPricingTier,
    updatePricingTier,
    deletePricingTier,
    assignPricingTierToEndpoint,
    getAnalytics,
  }
})

