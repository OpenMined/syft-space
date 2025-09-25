import { Clock, Calculator, Activity, Users, Gauge } from 'lucide-vue-next'
import type { Component } from 'vue'

export interface PolicyData {
  id: string
  name: string
  badge: string
  type: 'rate-limiter' | 'usage-tracking' | 'observability' | 'security'
  color: 'blue' | 'green' | 'purple' | 'red' | 'orange'
  icon: Component
  serviceCount: number
  description: string
  configs: string[]
  usageCount: number
  dateAdded: Date
  isActive?: boolean
}

export const AVAILABLE_POLICIES: PolicyData[] = [
  {
    id: 'rateLimiting',
    name: 'Rate Limiting Policy',
    badge: 'Rate Limiter',
    type: 'rate-limiter',
    color: 'blue',
    icon: Clock,
    serviceCount: 3,
    description: 'Controls request rates to prevent abuse and ensure fair resource usage',
    configs: ['Limit: 1000 req/min', 'Scope: Per User', 'Type: Sliding Window'],
    usageCount: 3,
    dateAdded: new Date('2024-01-15'),
    isActive: true
  },
  {
    id: 'burstRateLimiting',
    name: 'Burst Rate Limiting Policy',
    badge: 'Rate Limiter',
    type: 'rate-limiter',
    color: 'blue',
    icon: Gauge,
    serviceCount: 2,
    description: 'Controls short bursts while keeping sustained traffic within safe bounds',
    configs: ['Limit: 200 req/min', 'Scope: Per Service', 'Type: Token Bucket'],
    usageCount: 2,
    dateAdded: new Date('2024-01-20'),
    isActive: true
  },
  {
    id: 'accounting',
    name: 'Accounting Policy',
    badge: 'Usage Tracking',
    type: 'usage-tracking',
    color: 'green',
    icon: Calculator,
    serviceCount: 5,
    description: 'Tracks resource usage, costs, and generates billing reports for services',
    configs: ['Request: $0.001/request', 'Tokens: $0.02/1K tokens'],
    usageCount: 5,
    dateAdded: new Date('2024-01-10'),
    isActive: true
  },
  {
    id: 'telemetry',
    name: 'OpenTelemetry Observability Policy',
    badge: 'OTel',
    type: 'observability',
    color: 'purple',
    icon: Activity,
    serviceCount: 2,
    description: 'Collects traces, metrics, and logs for system monitoring and debugging',
    configs: ['Sampling: 10%', 'Backend: Jaeger', 'Endpoint: http://jaeger:4317', 'Batch Size: 512'],
    usageCount: 2,
    dateAdded: new Date('2024-02-01'),
    isActive: true
  },
  {
    id: 'humanInTheLoop',
    name: 'Human-in-the-Loop Policy',
    badge: 'HITL',
    type: 'security',
    color: 'orange',
    icon: Users,
    serviceCount: 0,
    description: 'Requires human approval for sensitive operations and decisions',
    configs: ['Alert Destination: Inbox', 'Approval Timeout: 30min'],
    usageCount: 0,
    dateAdded: new Date('2024-03-01'),
    isActive: false
  }
]

export const getActivePolicies = () => AVAILABLE_POLICIES.filter(policy => policy.isActive)
export const getInactivePolicies = () => AVAILABLE_POLICIES.filter(policy => !policy.isActive)