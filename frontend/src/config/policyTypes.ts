import { Shield, Gauge, DollarSign } from 'lucide-vue-next'
import type { Component } from 'vue'

export type PolicyTypeId = 'access' | 'rate_limit' | 'pricing' | 'xendit'

export interface PolicyConfig {
  id: string
  [key: string]: string | number
}

export interface PolicyRule {
  id: string
  config: PolicyConfig
  isEditing: boolean
}

export interface PolicyType {
  id: PolicyTypeId
  name: string
  label: string
  description: string
  icon: Component
  color: string
}

export type PolicyRulesRecord = Record<PolicyTypeId, PolicyRule[]>

export const POLICY_TYPES: PolicyType[] = [
  {
    id: 'access',
    name: 'Authorization',
    label: 'Who can access?',
    description: 'Control who can use your content - everyone, specific users, or by invitation',
    icon: Shield,
    color: 'blue',
  },
  {
    id: 'rate_limit',
    name: 'Rate Limiter',
    label: 'Prevent overuse',
    description: 'Limit how many queries each user can make per day or hour',
    icon: Gauge,
    color: 'green',
  },
  {
    id: 'pricing',
    name: 'Pricing',
    label: 'Set your price',
    description: 'Charge per query or make it free - you decide',
    icon: DollarSign,
    color: 'yellow',
  },
]

export const getPolicyTypeLabel = (type: string): string => {
  switch (type) {
    case 'access':
      return 'Authorization'
    case 'rate_limit':
      return 'Rate Limiting'
    case 'pricing':
      return 'Pricing'
    case 'xendit':
      return 'Bundle Payment'
    default:
      return 'Policy'
  }
}

export const createEmptyPolicyRules = (): PolicyRulesRecord => ({
  access: [],
  rate_limit: [],
  pricing: [],
  xendit: [],
})

export const generateRuleId = (): string => {
  return 'rule_' + Math.random().toString(36).substr(2, 9)
}

export const getRuleSummary = (policyId: PolicyTypeId, config: PolicyConfig): string => {
  switch (policyId) {
    case 'access':
      if (!config.users) return 'No users configured'
      {
        const ruleType = config.ruleType === 'allow' ? 'Allow' : 'Deny'
        const userList = (config.users as string)
          .split(',')
          .map((u) => u.trim())
          .filter((u) => u)
        if (userList.length === 0) {
          return 'No users configured'
        }
        return `${ruleType} access for ${userList.join(', ')}`
      }

    case 'rate_limit':
      if (!config.limit) return 'No limit configured'
      {
        const scope = config.scope === 'global' ? 'for this endpoint' : 'per user'
        return `${config.limit} requests per ${config.windowUnit} ${scope}`
      }

    case 'pricing':
      if (config.provider === 'xendit') {
        if (!config.tierCount && !config.tiers) return 'No tiers configured'
        const tiers = config.tiers as Array<Record<string, unknown>> | undefined
        const tierCount = tiers?.length || config.tierCount || 0
        return `${tierCount} bundle tier(s) in ${config.currency || 'IDR'} (Xendit)`
      }
      if (config.price === undefined || config.price === null || config.price === '')
        return 'No price configured'
      {
        const price = parseFloat(config.price as string)

        if (isNaN(price)) return 'Invalid price configured'

        if (price === 0) {
          if (config.userType === 'all') {
            return 'Free for all users'
          } else {
            const userList = config.users
              ? (config.users as string)
                  .split(',')
                  .map((u) => u.trim())
                  .filter((u) => u)
              : []
            if (userList.length === 0) {
              return 'Free for specific users (none configured)'
            }
            return `Free for ${userList.join(', ')}`
          }
        }

        const formattedPrice = price.toFixed(8).replace(/\.?0+$/, '')
        if (config.userType === 'all') {
          return `$${formattedPrice} per query for all users`
        } else {
          const userList = config.users
            ? (config.users as string)
                .split(',')
                .map((u) => u.trim())
                .filter((u) => u)
            : []
          if (userList.length === 0) {
            return `$${formattedPrice} per query for specific users (none configured)`
          }
          return `$${formattedPrice} per query for ${userList.join(', ')}`
        }
      }

    case 'xendit':
      if (!config.tierCount) return 'No tiers configured'
      return `${config.tierCount} bundle tier(s) in ${config.currency || 'IDR'}`

    default:
      return 'Rule configured'
  }
}

export const XENDIT_CURRENCIES = [
  { value: 'IDR', label: 'IDR - Indonesian Rupiah' },
  { value: 'USD', label: 'USD - US Dollar' },
  { value: 'PHP', label: 'PHP - Philippine Peso' },
  { value: 'SGD', label: 'SGD - Singapore Dollar' },
  { value: 'MYR', label: 'MYR - Malaysian Ringgit' },
  { value: 'THB', label: 'THB - Thai Baht' },
  { value: 'VND', label: 'VND - Vietnamese Dong' },
] as const

export const XENDIT_COUNTRIES = [
  { value: 'ID', label: 'Indonesia' },
  { value: 'PH', label: 'Philippines' },
  { value: 'SG', label: 'Singapore' },
  { value: 'MY', label: 'Malaysia' },
  { value: 'TH', label: 'Thailand' },
  { value: 'VN', label: 'Vietnam' },
] as const
