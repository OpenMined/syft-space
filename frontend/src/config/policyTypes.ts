import { Shield, Gauge, DollarSign } from 'lucide-vue-next'
import type { Component } from 'vue'

export type PolicyTypeId = 'access' | 'rate_limit' | 'pricing'

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
    name: 'Access Control',
    label: 'Who can access?',
    description: 'Control who can use your content - everyone, specific users, or by invitation',
    icon: Shield,
    color: 'blue',
  },
  {
    id: 'rate_limit',
    name: 'Usage Limits',
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
      return 'Access Control'
    case 'rate_limit':
      return 'Usage Limits'
    case 'pricing':
      return 'Pricing'
    default:
      return 'Policy'
  }
}

export const createEmptyPolicyRules = (): PolicyRulesRecord => ({
  access: [],
  rate_limit: [],
  pricing: [],
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

    default:
      return 'Rule configured'
  }
}
